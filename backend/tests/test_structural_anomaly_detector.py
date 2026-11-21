from __future__ import annotations

import numpy as np
import pytest

import app.services.structural_anomaly_detector as structural_module
from app.services.detector_protocol import DetectorConfig
from app.services.image_alignment import AlignmentResult
from app.services.structural_anomaly_detector import StructuralAnomalyDetector


def test_invalid_detector_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="threshold"):
        DetectorConfig(threshold=float("nan"))
    with pytest.raises(ValueError, match="min_area"):
        DetectorConfig(min_area=1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="weights"):
        DetectorConfig(gradient_weight=float("nan"))


def _texture(seed: int = 42) -> np.ndarray:
    return np.random.default_rng(seed).integers(
        0, 256, size=(128, 128, 3), dtype=np.uint8
    )


def test_identical_images_produce_no_candidates_and_measured_time() -> None:
    image = _texture()
    detector = StructuralAnomalyDetector(
        DetectorConfig(use_registration=False, min_area=20)
    )
    result = detector.detect(image, image.copy())
    assert result.success
    assert result.candidates == []
    assert result.processing_time_ms >= 0
    assert result.diagnostics["registration"] == "disabled"
    assert result.binary_mask is not None
    assert result.combined_map is not None


def test_local_edit_is_detected_in_reference_coordinates() -> None:
    reference = _texture()
    test = reference.copy()
    test[42:72, 55:86] = 255
    detector = StructuralAnomalyDetector(
        DetectorConfig(
            threshold=25,
            min_area=20,
            use_registration=False,
            intensity_weight=0.5,
            gradient_weight=0.5,
        )
    )
    result = detector.detect(reference, test)
    assert result.success
    assert result.candidates
    assert any(
        candidate["x"] < 70
        and candidate["x"] + candidate["width"] > 55
        and candidate["y"] < 60
        and candidate["y"] + candidate["height"] > 42
        for candidate in result.candidates
    )
    assert result.intensity_map is not None
    assert result.gradient_map is not None
    assert result.combined_map is not None
    assert result.binary_mask is not None
    assert result.valid_source_mask is not None


def test_gradient_signal_can_drive_localization() -> None:
    reference = np.zeros((128, 128, 3), dtype=np.uint8)
    test = reference.copy()
    test[40:85, 40:85] = 200
    detector = StructuralAnomalyDetector(
        DetectorConfig(
            threshold=25,
            min_area=20,
            use_registration=False,
            intensity_weight=0,
            gradient_weight=1,
        )
    )
    result = detector.detect(reference, test)
    assert result.success
    assert result.gradient_map is not None
    assert np.count_nonzero(result.gradient_map) > 0
    assert result.candidates


def test_registration_failure_is_reported_without_candidates() -> None:
    blank = np.zeros((128, 128, 3), dtype=np.uint8)
    result = StructuralAnomalyDetector().detect(blank, blank.copy())
    assert not result.success
    assert not result.candidates
    assert result.failure_reason is not None
    assert "registration failed" in result.failure_reason.lower()
    assert result.diagnostics["registration"] == "enabled"
    assert result.processing_time_ms >= 0


def test_insufficient_registered_source_support_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = _texture()

    def unsupported_alignment(
        reference: np.ndarray, test: np.ndarray
    ) -> AlignmentResult:
        del reference
        return AlignmentResult(
            aligned_test=test.copy(),
            diagnostics={
                "success": True,
                "failure_reason": None,
                "homography_test_to_reference": [
                    [1, 0, 10000],
                    [0, 1, 10000],
                    [0, 0, 1],
                ],
            },
        )

    monkeypatch.setattr(
        structural_module, "align_test_to_reference", unsupported_alignment
    )
    result = StructuralAnomalyDetector().detect(image, image.copy())
    assert not result.success
    assert result.valid_source_mask is not None
    assert np.count_nonzero(result.valid_source_mask) == 0
    assert result.failure_reason is not None
    assert "insufficient valid-source support" in result.failure_reason


def test_unregistered_size_mismatch_is_resized_to_reference_frame() -> None:
    reference = np.zeros((100, 100, 3), dtype=np.uint8)
    test = np.zeros((200, 200, 3), dtype=np.uint8)
    test[80:120, 80:120] = 255
    result = StructuralAnomalyDetector(
        DetectorConfig(use_registration=False, min_area=20)
    ).detect(reference, test)
    assert result.success
    assert result.diagnostics["test_resized_to_reference"] is True
    assert result.binary_mask is not None
    assert result.binary_mask.shape == reference.shape[:2]
    assert result.candidates
    assert all(
        candidate["x"] + candidate["width"] <= 100
        and candidate["y"] + candidate["height"] <= 100
        for candidate in result.candidates
    )


def test_invalid_images_return_clear_failure() -> None:
    result = StructuralAnomalyDetector().detect(None, None)  # type: ignore[arg-type]
    assert not result.success
    assert result.failure_reason is not None
    assert "non-empty arrays" in result.failure_reason
