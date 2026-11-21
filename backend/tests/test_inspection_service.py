from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.inspection_service import (
    DetectorExecutionError,
    InspectionService,
)


def _png_bytes(color: tuple[int, int, int] = (0, 0, 0)) -> bytes:
    image = np.zeros((96, 96, 3), dtype=np.uint8)
    image[:] = color
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


def test_service_writes_unique_artifacts_and_result_json(tmp_path: Path) -> None:
    service = InspectionService(output_root=tmp_path)
    response = service.inspect(_png_bytes(), _png_bytes((255, 255, 255)))

    run_dir = tmp_path / str(response.inspection_id)
    assert response.status == "completed"
    assert response.candidate_count >= 0
    assert response.processing_time_ms >= 0
    assert all((run_dir / filename).is_file() for filename in (
        "annotated.jpg",
        "difference.jpg",
        "mask.jpg",
        "result.json",
    ))
    assert "not confirmed defects" in response.warning
    assert service.artifact_path(response.inspection_id, "annotated") is not None
    assert service.artifact_path(response.inspection_id, "../result") is None


def test_service_rejects_invalid_second_image_before_detector(tmp_path: Path) -> None:
    detector_calls = 0

    def detector(**kwargs: object) -> dict:
        nonlocal detector_calls
        detector_calls += 1
        raise AssertionError("Detector must not run for invalid uploads.")

    service = InspectionService(output_root=tmp_path, detector=detector)
    with pytest.raises(ValueError, match="Only JPEG and PNG"):
        service.inspect(_png_bytes(), b"invalid")
    assert detector_calls == 0
    assert list(tmp_path.iterdir()) == []


def test_detector_failures_are_reported_and_staging_is_removed(
    tmp_path: Path,
) -> None:
    def detector(**kwargs: object) -> dict:
        raise RuntimeError("sensitive underlying error")

    service = InspectionService(output_root=tmp_path, detector=detector)
    with pytest.raises(DetectorExecutionError, match="could not be completed"):
        service.inspect(_png_bytes(), _png_bytes())
    assert list(tmp_path.iterdir()) == []


def test_detector_candidate_schema_is_validated(tmp_path: Path) -> None:
    def invalid_result(**kwargs: object) -> dict:
        output_dir = Path(str(kwargs["output_dir"]))
        for name in ("annotated.jpg", "difference.jpg", "mask.jpg"):
            (output_dir / name).write_bytes(b"test")
        return {
            "regions": [{"x": -1}],
            "processing_time_ms": 1.0,
        }

    service = InspectionService(output_root=tmp_path, detector=invalid_result)
    with pytest.raises(DetectorExecutionError, match="invalid candidate box"):
        service.inspect(_png_bytes(), _png_bytes())
    assert list(tmp_path.iterdir()) == []
