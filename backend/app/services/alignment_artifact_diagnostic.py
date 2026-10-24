from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from app.services.inspection_baseline import preprocess


def _distribution(values: list[int] | np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
            "bins": {},
        }
    bins = {
        "area_le_100": int(np.count_nonzero(array <= 100)),
        "area_101_500": int(np.count_nonzero((array > 100) & (array <= 500))),
        "area_501_1000": int(np.count_nonzero((array > 500) & (array <= 1000))),
        "area_1001_10000": int(np.count_nonzero((array > 1000) & (array <= 10000))),
        "area_gt_10000": int(np.count_nonzero(array > 10000)),
    }
    return {
        "count": int(array.size),
        "min": float(np.min(array)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
        "bins": bins,
    }


def warp_with_valid_source_mask(
    source: np.ndarray,
    homography: np.ndarray,
    output_size: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Warp image and mark only output pixels fully sampled from source pixels."""
    width, height = output_size
    warped = cv2.warpPerspective(
        source,
        homography,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    source_support = np.full(source.shape[:2], 255, dtype=np.uint8)
    warped_support = cv2.warpPerspective(
        source_support,
        homography,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    valid_support = np.where(warped_support == 255, 255, 0).astype(np.uint8)
    return warped, valid_support


def _component_count(mask: np.ndarray) -> tuple[int, list[int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA].astype(int).tolist()
    return count - 1, areas


def _candidate_regions(mask: np.ndarray, min_area: int) -> list[dict[str, int]]:
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    regions = []
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        regions.append({
            "x": int(x),
            "y": int(y),
            "width": int(width),
            "height": int(height),
            "contour_area": area,
            "bbox_area": int(width * height),
        })
    return regions


def _mask_statistics(
    binary_mask: np.ndarray,
    support_mask: np.ndarray,
    min_area: int,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    valid = support_mask > 0
    invalid = ~valid
    foreground = binary_mask > 0
    valid_mask = np.where(valid, binary_mask, 0).astype(np.uint8)
    border_mask = np.where(invalid, binary_mask, 0).astype(np.uint8)
    full_components, full_component_areas = _component_count(binary_mask)
    valid_components, valid_component_areas = _component_count(valid_mask)
    border_components, border_component_areas = _component_count(border_mask)
    regions = _candidate_regions(binary_mask, min_area)
    valid_regions = _candidate_regions(valid_mask, min_area)
    border_regions = _candidate_regions(border_mask, min_area)

    integral_invalid = cv2.integral(invalid.astype(np.uint8))
    border_candidate_count = 0
    for region in regions:
        x1, y1 = region["x"], region["y"]
        x2 = x1 + region["width"]
        y2 = y1 + region["height"]
        invalid_pixels_in_box = (
            integral_invalid[y2, x2]
            - integral_invalid[y1, x2]
            - integral_invalid[y2, x1]
            + integral_invalid[y1, x1]
        )
        region["touches_invalid_source"] = bool(invalid_pixels_in_box > 0)
        border_candidate_count += int(region["touches_invalid_source"])

    image_pixels = int(binary_mask.size)
    valid_pixels = int(np.count_nonzero(valid))
    foreground_pixels = int(np.count_nonzero(foreground))
    valid_foreground = int(np.count_nonzero(foreground & valid))
    border_foreground = int(np.count_nonzero(foreground & invalid))
    stats = {
        "image_pixels": image_pixels,
        "valid_source_pixels": valid_pixels,
        "valid_source_percentage": round(valid_pixels / image_pixels * 100, 4),
        "foreground_pixels": foreground_pixels,
        "foreground_percentage_of_full_image": round(
            foreground_pixels / image_pixels * 100, 4
        ),
        "valid_foreground_pixels": valid_foreground,
        "foreground_percentage_of_valid_source": round(
            valid_foreground / valid_pixels * 100, 4
        ) if valid_pixels else None,
        "invalid_border_foreground_pixels": border_foreground,
        "foreground_percentage_of_invalid_border": round(
            border_foreground / max(image_pixels - valid_pixels, 1) * 100, 4
        ),
        "connected_components": {
            "full_mask_count": full_components,
            "full_mask_pixel_area": _distribution(full_component_areas),
            "valid_source_count": valid_components,
            "valid_source_pixel_area": _distribution(valid_component_areas),
            "invalid_border_count": border_components,
            "invalid_border_pixel_area": _distribution(border_component_areas),
        },
        "candidate_count": len(regions),
        "valid_source_filtered_candidate_count": len(valid_regions),
        "invalid_border_only_candidate_count": len(border_regions),
        "valid_source_filtered_candidate_contour_area": _distribution(
            [region["contour_area"] for region in valid_regions]
        ),
        "invalid_border_only_candidate_contour_area": _distribution(
            [region["contour_area"] for region in border_regions]
        ),
        "candidate_contour_area": _distribution(
            [region["contour_area"] for region in regions]
        ),
        "candidate_bbox_area": _distribution(
            [region["bbox_area"] for region in regions]
        ),
        "candidate_boxes_touching_invalid_source": border_candidate_count,
        "candidate_boxes_interior_only": len(regions) - border_candidate_count,
        "regions": regions,
    }
    return stats, valid_mask, border_mask, np.asarray(regions, dtype=object)


def analyze_comparison(
    reference: np.ndarray,
    test: np.ndarray,
    support_mask: np.ndarray,
    *,
    threshold: int = 25,
    min_area: int = 80,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Apply the baseline preprocessing/morphology and expose support statistics."""
    height, width = reference.shape[:2]
    if test.shape[:2] != (height, width):
        raise ValueError("Test image must already use reference dimensions.")
    if support_mask.shape != (height, width):
        raise ValueError("Support mask must match reference dimensions.")

    started = time.perf_counter()
    difference = cv2.absdiff(preprocess(reference), preprocess(test))
    _, threshold_mask = cv2.threshold(
        difference, threshold, 255, cv2.THRESH_BINARY
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    post_morphology_mask = cv2.morphologyEx(
        threshold_mask, cv2.MORPH_OPEN, kernel
    )
    post_morphology_mask = cv2.morphologyEx(
        post_morphology_mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2,
    )
    stats, valid_mask, border_mask, _ = _mask_statistics(
        post_morphology_mask, support_mask, min_area
    )
    processing_time_ms = round((time.perf_counter() - started) * 1000, 2)

    annotated = test.copy()
    for region in stats["regions"]:
        x, y = region["x"], region["y"]
        box_width, box_height = region["width"], region["height"]
        cv2.rectangle(
            annotated,
            (x, y),
            (x + box_width, y + box_height),
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
    stats["processing_time_ms"] = processing_time_ms
    stats["parameters"] = {"threshold": threshold, "min_area": min_area}
    stats["coordinate_system"] = "reference image pixel coordinates"
    stats["image_dimensions"] = {"width": width, "height": height}
    stats["timing_scope"] = (
        "Preprocessing through morphology and diagnostic statistics; excludes "
        "input loading and output writes."
    )
    return stats, {
        "difference.png": difference,
        "mask.png": post_morphology_mask,
        "valid_source_mask.png": support_mask,
        "valid_source_foreground.png": valid_mask,
        "invalid_border_foreground.png": border_mask,
        "annotated.jpg": annotated,
    }


def compare_masks(
    left: np.ndarray,
    right: np.ndarray,
    support_mask: np.ndarray,
) -> dict[str, Any]:
    left_foreground = left > 0
    right_foreground = right > 0
    changed = left_foreground != right_foreground
    support = support_mask > 0
    valid_changed = int(np.count_nonzero(changed & support))
    border_changed = int(np.count_nonzero(changed & ~support))
    return {
        "changed_foreground_decisions": int(np.count_nonzero(changed)),
        "changed_percentage_of_full_image": round(
            float(changed.mean()) * 100, 4
        ),
        "changed_valid_source_pixels": valid_changed,
        "changed_invalid_border_pixels": border_changed,
        "left_only_foreground_pixels": int(
            np.count_nonzero(left_foreground & ~right_foreground)
        ),
        "right_only_foreground_pixels": int(
            np.count_nonzero(right_foreground & ~left_foreground)
        ),
    }
