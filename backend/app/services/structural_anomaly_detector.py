from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from app.services.detector_protocol import (
    DetectorConfig,
    DetectorOutput,
    DetectorProtocol,
)
from app.services.image_alignment import align_test_to_reference


class StructuralAnomalyDetector(DetectorProtocol):
    """Experimental intensity-and-gradient candidate detector."""

    def __init__(self, config: DetectorConfig | None = None):
        self._config = config or DetectorConfig()

    @property
    def config(self) -> DetectorConfig:
        return self._config

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> StructuralAnomalyDetector:
        return cls(DetectorConfig(**config))

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return image
        if image.ndim != 3:
            raise ValueError("Images must be grayscale, BGR, or BGRA arrays.")
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        raise ValueError("Images must have 1, 3, or 4 channels.")

    def detect(self, reference: np.ndarray, test: np.ndarray) -> DetectorOutput:
        started = time.perf_counter()
        if (
            reference is None
            or test is None
            or not isinstance(reference, np.ndarray)
            or not isinstance(test, np.ndarray)
            or reference.size == 0
            or test.size == 0
        ):
            return DetectorOutput(
                candidates=[],
                success=False,
                failure_reason="Reference and test images must be non-empty arrays.",
            )

        try:
            reference_gray = self._to_gray(reference)
            test_gray = self._to_gray(test)
            ref_height, ref_width = reference_gray.shape
            test_height, test_width = test_gray.shape
            diagnostics: dict[str, Any] = {
                "registration": (
                    "enabled"
                    if self._config.use_registration
                    else "disabled"
                )
            }

            if self._config.use_registration:
                alignment = align_test_to_reference(reference, test)
                diagnostics["alignment"] = alignment.diagnostics
                if alignment.aligned_test is None:
                    return DetectorOutput(
                        candidates=[],
                        success=False,
                        failure_reason=(
                            "Image registration failed: "
                            f"{alignment.diagnostics['failure_reason']}"
                        ),
                        processing_time_ms=round(
                            (time.perf_counter() - started) * 1000, 2
                        ),
                        diagnostics=diagnostics,
                    )
                test_gray = self._to_gray(alignment.aligned_test)
                if self._config.use_source_masking:
                    homography = np.asarray(
                        alignment.diagnostics["homography_test_to_reference"],
                        dtype=np.float64,
                    )
                    source = np.full((test_height, test_width), 255, np.uint8)
                    valid_source_mask = cv2.warpPerspective(
                        source,
                        homography,
                        (ref_width, ref_height),
                        flags=cv2.INTER_NEAREST,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                else:
                    valid_source_mask = np.full(
                        (ref_height, ref_width), 255, np.uint8
                    )
            else:
                if test_gray.shape != reference_gray.shape:
                    test_gray = cv2.resize(
                        test_gray,
                        (ref_width, ref_height),
                        interpolation=cv2.INTER_AREA,
                    )
                    diagnostics["test_resized_to_reference"] = True
                valid_source_mask = np.full(
                    (ref_height, ref_width), 255, np.uint8
                )

            valid_source_pixels = cv2.countNonZero(valid_source_mask)
            valid_source_fraction = valid_source_pixels / (ref_height * ref_width)
            diagnostics["valid_source_pixels"] = valid_source_pixels
            diagnostics["valid_source_fraction"] = valid_source_fraction
            if (
                self._config.use_source_masking
                and valid_source_fraction
                < self._config.min_valid_source_fraction
            ):
                return DetectorOutput(
                    candidates=[],
                    valid_source_mask=valid_source_mask,
                    success=False,
                    failure_reason=(
                        "Registration has insufficient valid-source support: "
                        f"{valid_source_fraction:.3f} is below "
                        f"{self._config.min_valid_source_fraction:.3f}."
                    ),
                    processing_time_ms=round(
                        (time.perf_counter() - started) * 1000, 2
                    ),
                    diagnostics=diagnostics,
                )

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            reference_gray = cv2.GaussianBlur(
                clahe.apply(reference_gray), (5, 5), 0
            )
            test_gray = cv2.GaussianBlur(clahe.apply(test_gray), (5, 5), 0)

            intensity_map = cv2.absdiff(reference_gray, test_gray)
            ref_gradient_x = cv2.Sobel(
                reference_gray, cv2.CV_32F, 1, 0, ksize=3
            )
            ref_gradient_y = cv2.Sobel(
                reference_gray, cv2.CV_32F, 0, 1, ksize=3
            )
            test_gradient_x = cv2.Sobel(test_gray, cv2.CV_32F, 1, 0, ksize=3)
            test_gradient_y = cv2.Sobel(test_gray, cv2.CV_32F, 0, 1, ksize=3)
            gradient_difference = cv2.magnitude(
                cv2.absdiff(ref_gradient_x, test_gradient_x),
                cv2.absdiff(ref_gradient_y, test_gradient_y),
            )
            gradient_map = np.clip(gradient_difference, 0, 255).astype(np.uint8)

            weight_total = (
                self._config.intensity_weight + self._config.gradient_weight
            )
            combined_map = cv2.addWeighted(
                intensity_map,
                self._config.intensity_weight / weight_total,
                gradient_map,
                self._config.gradient_weight / weight_total,
                0,
            )
            _, binary_mask = cv2.threshold(
                combined_map,
                self._config.threshold,
                255,
                cv2.THRESH_BINARY,
            )
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary_mask = cv2.morphologyEx(
                binary_mask, cv2.MORPH_OPEN, kernel
            )
            binary_mask = cv2.morphologyEx(
                binary_mask, cv2.MORPH_CLOSE, kernel, iterations=2
            )
            if self._config.use_source_masking:
                binary_mask = cv2.bitwise_and(binary_mask, valid_source_mask)

            contours, _ = cv2.findContours(
                binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            candidates: list[dict[str, int | str]] = []
            for contour in contours:
                area = int(cv2.contourArea(contour))
                if area < self._config.min_area:
                    continue
                x, y, width, height = cv2.boundingRect(contour)
                candidates.append(
                    {
                        "x": int(x),
                        "y": int(y),
                        "width": int(width),
                        "height": int(height),
                        "area": area,
                        "status": "structural_anomaly",
                    }
                )
            candidates.sort(key=lambda box: (box["y"], box["x"]))

            return DetectorOutput(
                candidates=candidates,
                gradient_map=gradient_map,
                intensity_map=intensity_map,
                combined_map=combined_map,
                binary_mask=binary_mask,
                valid_source_mask=valid_source_mask,
                processing_time_ms=round(
                    (time.perf_counter() - started) * 1000, 2
                ),
                success=True,
                diagnostics=diagnostics,
            )
        except (ValueError, cv2.error) as error:
            return DetectorOutput(
                candidates=[],
                success=False,
                failure_reason=str(error),
                processing_time_ms=round(
                    (time.perf_counter() - started) * 1000, 2
                ),
            )
