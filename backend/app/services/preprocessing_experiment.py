from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from app.services.inspection_baseline import preprocess


CONFIGURATION = {"threshold": 25, "min_area": 80}
VARIANTS = (
    "baseline",
    "gaussian_7x7",
    "median_5x5",
    "morphology_open_5_close_3_once",
)


def _preprocess_variant(image: np.ndarray, variant: str) -> np.ndarray:
    if variant == "baseline":
        return preprocess(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    if variant == "gaussian_7x7":
        return cv2.GaussianBlur(enhanced, (7, 7), 0)
    if variant == "median_5x5":
        return cv2.medianBlur(enhanced, 5)
    if variant == "morphology_open_5_close_3_once":
        return cv2.GaussianBlur(enhanced, (5, 5), 0)
    raise ValueError(f"Unknown preprocessing variant: {variant}")


def _morphology(mask: np.ndarray, variant: str) -> np.ndarray:
    if variant == "morphology_open_5_close_3_once":
        opening_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (5, 5)
        )
        closing_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (3, 3)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, opening_kernel)
        return cv2.morphologyEx(
            mask, cv2.MORPH_CLOSE, closing_kernel, iterations=1
        )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, kernel, iterations=2
    )


def inspect_variant(
    reference: np.ndarray,
    test: np.ndarray,
    *,
    variant: str,
    threshold: int = CONFIGURATION["threshold"],
    min_area: int = CONFIGURATION["min_area"],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if reference is None or test is None or reference.size == 0 or test.size == 0:
        raise ValueError("Reference and test images must be non-empty.")
    if variant not in VARIANTS:
        raise ValueError(f"Unknown preprocessing variant: {variant}")
    if not 0 <= threshold <= 255:
        raise ValueError("Threshold must be between 0 and 255.")
    if min_area < 1:
        raise ValueError("Minimum contour area must be positive.")

    height, width = reference.shape[:2]
    if test.shape[:2] != reference.shape[:2]:
        test = cv2.resize(test, (width, height), interpolation=cv2.INTER_AREA)

    started = time.perf_counter()
    reference_gray = _preprocess_variant(reference, variant)
    test_gray = _preprocess_variant(test, variant)
    difference = cv2.absdiff(reference_gray, test_gray)
    _, threshold_mask = cv2.threshold(
        difference, threshold, 255, cv2.THRESH_BINARY
    )
    mask = _morphology(threshold_mask, variant)
    component_count, _, component_stats, _ = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    regions = []
    annotated = test.copy()
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, box_width, box_height = cv2.boundingRect(contour)
        region = {
            "x": int(x),
            "y": int(y),
            "width": int(box_width),
            "height": int(box_height),
            "area": area,
            "status": "suspicious_difference",
        }
        regions.append(region)
        cv2.rectangle(
            annotated,
            (x, y),
            (x + box_width, y + box_height),
            (0, 0, 255),
            2,
        )
    processing_time_ms = round((time.perf_counter() - started) * 1000, 2)

    foreground_pixels = int(cv2.countNonZero(mask))
    result = {
        "variant": variant,
        "configuration": {"threshold": threshold, "min_area": min_area},
        "image_dimensions": {"width": width, "height": height},
        "coordinate_system": "reference image pixel coordinates",
        "candidate_count": len(regions),
        "foreground_mask_pixels": foreground_pixels,
        "foreground_mask_percentage": round(
            foreground_pixels / (width * height) * 100, 6
        ),
        "connected_component_count": int(component_count - 1),
        "connected_component_pixel_area": {
            "median": float(np.median(component_stats[1:, cv2.CC_STAT_AREA]))
            if component_count > 1 else None,
            "max": int(np.max(component_stats[1:, cv2.CC_STAT_AREA]))
            if component_count > 1 else None,
        },
        "processing_time_ms": processing_time_ms,
        "processing_time_scope": (
            "Both image preprocessings through difference threshold, "
            "morphology, connected-component analysis, and contour filtering; "
            "excludes image I/O and artifact writes."
        ),
        "preprocessing": {
            "baseline": (
                "grayscale, CLAHE clipLimit=2.0 tileGridSize=(8,8), "
                "GaussianBlur 5x5"
            ),
            "gaussian_7x7": (
                "same grayscale and CLAHE as baseline; GaussianBlur 7x7"
            ),
            "median_5x5": (
                "same grayscale and CLAHE as baseline; medianBlur 5x5 "
                "replaces GaussianBlur 5x5"
            ),
            "morphology_open_5_close_3_once": (
                "baseline image preprocessing; rectangular opening 5x5 once "
                "and rectangular closing 3x3 once"
            ),
        }[variant],
        "morphology": (
            "rectangular opening 5x5 once, then rectangular closing 3x3 once"
            if variant == "morphology_open_5_close_3_once"
            else "rectangular opening 3x3 once, then rectangular closing "
            "3x3 twice"
        ),
        "regions": regions,
    }
    return result, {
        "annotated.jpg": annotated,
        "difference.png": difference,
        "mask.png": mask,
    }
