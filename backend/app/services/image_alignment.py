from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass
class AlignmentResult:
    aligned_test: np.ndarray | None
    diagnostics: dict[str, Any]


def _gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    raise ValueError("Images must be grayscale, BGR, or BGRA arrays.")


def _resize_for_features(
    image: np.ndarray, max_dimension: int
) -> tuple[np.ndarray, float, float]:
    height, width = image.shape[:2]
    scale = min(1.0, max_dimension / max(height, width))
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    if (resized_width, resized_height) == (width, height):
        return image, 1.0, 1.0
    resized = cv2.resize(
        image,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA,
    )
    return resized, resized_width / width, resized_height / height


def _transform_is_plausible(
    transform: np.ndarray,
    test_shape: tuple[int, int],
    reference_shape: tuple[int, int],
) -> tuple[bool, str | None]:
    if transform.shape != (3, 3) or not np.isfinite(transform).all():
        return False, "Estimated homography is malformed or non-finite."

    scale = transform[2, 2]
    if abs(scale) < 1e-8:
        return False, "Estimated homography cannot be normalized."
    transform = transform / scale

    test_height, test_width = test_shape
    reference_height, reference_width = reference_shape
    corners = np.float32(
        [[0, 0], [test_width - 1, 0],
         [test_width - 1, test_height - 1], [0, test_height - 1]]
    ).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, transform).reshape(-1, 2)
    if not np.isfinite(projected).all():
        return False, "Homography maps image corners to non-finite coordinates."

    x_min, y_min = projected.min(axis=0)
    x_max, y_max = projected.max(axis=0)
    if (
        x_min < -0.5 * reference_width
        or y_min < -0.5 * reference_height
        or x_max > 1.5 * reference_width
        or y_max > 1.5 * reference_height
    ):
        return False, "Homography projects image corners outside safe bounds."

    projected_area = abs(cv2.contourArea(projected.astype(np.float32)))
    reference_area = reference_width * reference_height
    area_ratio = projected_area / reference_area
    if not 0.15 <= area_ratio <= 6.0:
        return False, "Homography produces an implausible image-area scale."
    return True, None


def align_test_to_reference(
    reference: np.ndarray,
    test: np.ndarray,
    *,
    max_features: int = 4000,
    max_dimension: int = 1600,
    ratio_threshold: float = 0.75,
    min_good_matches: int = 12,
    min_inliers: int = 10,
    min_inlier_ratio: float = 0.25,
    min_feature_coverage: float = 0.01,
    ransac_reprojection_threshold: float = 4.0,
) -> AlignmentResult:
    """Align test to reference; return no warped image when confidence is low."""
    started = time.perf_counter()
    if reference is None or test is None or reference.size == 0 or test.size == 0:
        raise ValueError("Reference and test images must be non-empty.")
    if reference.ndim not in (2, 3) or test.ndim not in (2, 3):
        raise ValueError("Images must be 2D grayscale or 3D color arrays.")
    if max_features < 1 or max_dimension < 1:
        raise ValueError("max_features and max_dimension must be positive.")

    reference_height, reference_width = reference.shape[:2]
    test_height, test_width = test.shape[:2]
    diagnostics: dict[str, Any] = {
        "method": "ORB + Hamming ratio test + RANSAC homography",
        "success": False,
        "reference_dimensions": {
            "width": reference_width,
            "height": reference_height,
        },
        "test_dimensions": {"width": test_width, "height": test_height},
        "output_dimensions": {
            "width": reference_width,
            "height": reference_height,
        },
        "parameters": {
            "max_features": max_features,
            "max_dimension": max_dimension,
            "ratio_threshold": ratio_threshold,
            "min_good_matches": min_good_matches,
            "min_inliers": min_inliers,
            "min_inlier_ratio": min_inlier_ratio,
            "min_feature_coverage": min_feature_coverage,
            "ransac_reprojection_threshold": ransac_reprojection_threshold,
        },
        "reference_keypoints": 0,
        "test_keypoints": 0,
        "knn_match_count": 0,
        "good_match_count": 0,
        "inlier_count": 0,
        "inlier_ratio": 0.0,
        "reference_inlier_coverage": 0.0,
        "test_inlier_coverage": 0.0,
        "homography_test_to_reference": None,
        "failure_reason": None,
    }

    def failed(reason: str) -> AlignmentResult:
        diagnostics["failure_reason"] = reason
        diagnostics["alignment_time_ms"] = round(
            (time.perf_counter() - started) * 1000, 2
        )
        return AlignmentResult(None, diagnostics)

    reference_gray, reference_scale_x, reference_scale_y = (
        _resize_for_features(_gray(reference), max_dimension)
    )
    test_gray, test_scale_x, test_scale_y = _resize_for_features(
        _gray(test), max_dimension
    )

    orb = cv2.ORB_create(
        nfeatures=max_features,
        scaleFactor=1.2,
        nlevels=8,
        edgeThreshold=15,
        fastThreshold=12,
    )
    reference_keypoints, reference_descriptors = orb.detectAndCompute(
        reference_gray, None
    )
    test_keypoints, test_descriptors = orb.detectAndCompute(test_gray, None)
    diagnostics["reference_keypoints"] = len(reference_keypoints)
    diagnostics["test_keypoints"] = len(test_keypoints)

    if reference_descriptors is None or test_descriptors is None:
        return failed("ORB found no usable descriptors in one or both images.")

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn_matches = matcher.knnMatch(test_descriptors, reference_descriptors, k=2)
    good_matches = [
        best
        for neighbors in knn_matches
        if len(neighbors) == 2
        for best, second in [neighbors]
        if best.distance < ratio_threshold * second.distance
    ]
    diagnostics["knn_match_count"] = len(knn_matches)
    diagnostics["good_match_count"] = len(good_matches)
    if len(good_matches) < min_good_matches:
        return failed(
            f"Too few ratio-tested matches: {len(good_matches)} "
            f"(minimum {min_good_matches})."
        )

    test_points = np.float32(
        [test_keypoints[match.queryIdx].pt for match in good_matches]
    ).reshape(-1, 1, 2)
    reference_points = np.float32(
        [reference_keypoints[match.trainIdx].pt for match in good_matches]
    ).reshape(-1, 1, 2)
    feature_homography, inlier_mask = cv2.findHomography(
        test_points,
        reference_points,
        cv2.RANSAC,
        ransac_reprojection_threshold,
    )
    if feature_homography is None or inlier_mask is None:
        return failed("RANSAC could not estimate a homography.")

    inlier_flags = inlier_mask.ravel().astype(bool)
    inlier_count = int(np.count_nonzero(inlier_flags))
    inlier_ratio = inlier_count / len(good_matches)
    diagnostics["inlier_count"] = inlier_count
    diagnostics["inlier_ratio"] = round(inlier_ratio, 4)
    if inlier_count < min_inliers or inlier_ratio < min_inlier_ratio:
        return failed(
            "RANSAC support is insufficient: "
            f"{inlier_count} inliers ({inlier_ratio:.3f} ratio)."
        )

    reference_inliers = reference_points[inlier_flags].reshape(-1, 2)
    test_inliers = test_points[inlier_flags].reshape(-1, 2)
    reference_area = reference_gray.shape[0] * reference_gray.shape[1]
    test_area = test_gray.shape[0] * test_gray.shape[1]
    reference_coverage = (
        cv2.contourArea(cv2.convexHull(reference_inliers.astype(np.float32)))
        / reference_area
    )
    test_coverage = (
        cv2.contourArea(cv2.convexHull(test_inliers.astype(np.float32)))
        / test_area
    )
    diagnostics["reference_inlier_coverage"] = round(
        float(reference_coverage), 4
    )
    diagnostics["test_inlier_coverage"] = round(float(test_coverage), 4)
    if min(reference_coverage, test_coverage) < min_feature_coverage:
        return failed(
            "RANSAC inliers do not cover enough of both images."
        )

    # Convert the feature-resolution mapping into original image coordinates.
    full_resolution_homography = (
        np.diag([1.0 / reference_scale_x, 1.0 / reference_scale_y, 1.0])
        @ feature_homography
        @ np.diag([test_scale_x, test_scale_y, 1.0])
    )

    plausible, reason = _transform_is_plausible(
        full_resolution_homography,
        (test_height, test_width),
        (reference_height, reference_width),
    )
    if not plausible:
        return failed(reason or "Estimated homography failed validation.")

    full_resolution_homography /= full_resolution_homography[2, 2]
    aligned = cv2.warpPerspective(
        test,
        full_resolution_homography,
        (reference_width, reference_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    diagnostics["success"] = True
    diagnostics["homography_test_to_reference"] = (
        full_resolution_homography.tolist()
    )
    diagnostics["alignment_time_ms"] = round(
        (time.perf_counter() - started) * 1000, 2
    )
    return AlignmentResult(aligned, diagnostics)
