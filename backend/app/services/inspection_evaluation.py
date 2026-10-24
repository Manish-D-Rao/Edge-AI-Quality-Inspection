from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from app.services.inspection_baseline import preprocess


def candidate_bbox_ranges(
    regions: list[dict[str, Any]],
) -> dict[str, list[int] | None]:
    if not regions:
        return {"x": None, "y": None}
    return {
        "x": [
            min(int(region["x"]) for region in regions),
            max(int(region["x"]) for region in regions),
        ],
        "y": [
            min(int(region["y"]) for region in regions),
            max(int(region["y"]) for region in regions),
        ],
    }


def synthetic_edit_boxes() -> list[dict[str, Any]]:
    """Derive exact edit bounds from the demo generator's drawing operations."""
    edit_mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.line(edit_mask, (370, 70), (420, 82), 255, 5)
    cv2.circle(edit_mask, (520, 150), 9, 255, -1)

    edits = []
    for name, region in (
        ("scratch_like_line", edit_mask[40:110, 340:450]),
        ("circular_mark", edit_mask[125:175, 495:545]),
    ):
        points = cv2.findNonZero(region)
        if points is None:
            raise ValueError(f"Could not derive synthetic edit bounds: {name}")
        x, y, width, height = cv2.boundingRect(points)
        x_offset, y_offset = (340, 40) if name == "scratch_like_line" else (495, 125)
        edits.append({
            "name": name,
            "x": x + x_offset,
            "y": y + y_offset,
            "width": width,
            "height": height,
        })
    return edits


def evaluate_edit_coverage(
    edits: list[dict[str, Any]],
    regions: list[dict[str, Any]],
) -> dict[str, Any]:
    per_edit = []
    matched_region_indexes: set[int] = set()
    for edit in edits:
        edit_x1 = int(edit["x"])
        edit_y1 = int(edit["y"])
        edit_x2 = edit_x1 + int(edit["width"])
        edit_y2 = edit_y1 + int(edit["height"])
        covered = np.zeros(
            (int(edit["height"]), int(edit["width"])), dtype=bool
        )
        intersections = []
        for index, region in enumerate(regions):
            region_x1 = int(region["x"])
            region_y1 = int(region["y"])
            region_x2 = region_x1 + int(region["width"])
            region_y2 = region_y1 + int(region["height"])
            x1 = max(edit_x1, region_x1)
            y1 = max(edit_y1, region_y1)
            x2 = min(edit_x2, region_x2)
            y2 = min(edit_y2, region_y2)
            if x1 >= x2 or y1 >= y2:
                continue
            covered[y1 - edit_y1:y2 - edit_y1, x1 - edit_x1:x2 - edit_x1] = True
            matched_region_indexes.add(index)
            intersections.append({
                "candidate_index": index,
                "intersection_area": (x2 - x1) * (y2 - y1),
            })
        coverage_ratio = float(covered.mean())
        per_edit.append({
            **edit,
            "covered": coverage_ratio >= 1.0,
            "bbox_coverage_ratio": round(coverage_ratio, 4),
            "intersections": intersections,
        })
    return {
        "edits": per_edit,
        "additional_candidate_count": len(regions) - len(matched_region_indexes),
        "additional_candidate_indexes": [
            index for index in range(len(regions))
            if index not in matched_region_indexes
        ],
        "coverage_basis": (
            "Union of candidate-box pixels intersecting the full artificial-edit "
            "bounding box; an edit is covered only at 100% bounding-box coverage."
        ),
    }


def inspect_pair(
    reference: np.ndarray,
    test: np.ndarray,
    *,
    reference_path: str,
    test_path: str,
    threshold: int,
    min_area: int,
    alignment_time_ms: float = 0.0,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run the baseline comparison stages and retain their image products."""
    if reference is None or test is None or reference.size == 0 or test.size == 0:
        raise ValueError("Reference and test images must be non-empty.")
    height, width = reference.shape[:2]
    if test.shape[:2] != reference.shape[:2]:
        test = cv2.resize(test, (width, height), interpolation=cv2.INTER_AREA)

    started = time.perf_counter()
    reference_gray = preprocess(reference)
    test_gray = preprocess(test)
    difference = cv2.absdiff(reference_gray, test_gray)
    _, mask = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, kernel, iterations=2
    )
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    annotated = test.copy()
    regions = []
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, region_width, region_height = cv2.boundingRect(contour)
        regions.append({
            "x": int(x),
            "y": int(y),
            "width": int(region_width),
            "height": int(region_height),
            "area": area,
            "status": "suspicious_difference",
        })
        cv2.rectangle(
            annotated,
            (x, y),
            (x + region_width, y + region_height),
            (0, 0, 255),
            2,
        )
        cv2.putText(
            annotated,
            "Candidate",
            (x, max(y - 8, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    processing_time_ms = round((time.perf_counter() - started) * 1000, 2)
    result = {
        "method": "opencv_reference_difference",
        "reference_image": reference_path,
        "test_image": test_path,
        "coordinate_system": "reference image pixel coordinates",
        "image_width": width,
        "image_height": height,
        "candidate_count": len(regions),
        "candidate_bbox_top_left_ranges": candidate_bbox_ranges(regions),
        "processing_time_ms": processing_time_ms,
        "processing_time_scope": (
            "Preprocessing through contour filtering; excludes image file I/O "
            "and output writes."
        ),
        "alignment_time_ms": round(alignment_time_ms, 2),
        "total_processing_time_ms": round(
            processing_time_ms + alignment_time_ms, 2
        ),
        "parameters": {"threshold": threshold, "min_area": min_area},
        "regions": regions,
        "warning": (
            "Candidates indicate image differences, not confirmed defects."
        ),
    }
    return result, {
        "annotated.jpg": annotated,
        "difference.jpg": difference,
        "mask.jpg": mask,
    }
