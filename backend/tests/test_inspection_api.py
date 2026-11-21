from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.services.inspection_service import InspectionService
from main import app
from app.api import inspection as inspection_api


def _png_bytes(color: tuple[int, int, int] = (0, 0, 0)) -> bytes:
    image = np.zeros((96, 96, 3), dtype=np.uint8)
    image[:] = color
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        inspection_api,
        "inspection_service",
        InspectionService(output_root=tmp_path),
    )
    return TestClient(app)


def test_health_endpoint_and_multipart_inspection(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    response = client.post(
        "/api/inspect",
        files={
            "reference": ("not-a-path.png", _png_bytes(), "image/png"),
            "test": ("../../unsafe.png", _png_bytes((255, 255, 255)), "image/png"),
        },
        data={"threshold": "25", "min_area": "20"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["detector_id"] == "opencv_reference_difference"
    assert payload["config"] == {"threshold": 25, "min_area": 20}
    assert payload["candidate_count"] == len(payload["candidates"])
    assert "not confirmed defects" in payload["warning"]
    assert client.get(payload["artifacts"]["annotated"]).status_code == 200
    assert client.get(payload["artifacts"]["difference"]).status_code == 200
    assert client.get(payload["artifacts"]["mask"]).status_code == 200
    assert client.get(payload["artifacts"]["result"]).status_code == 200


def test_invalid_image_and_invalid_parameter_return_client_errors(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/inspect",
        files={
            "reference": ("ref.png", b"nope", "image/png"),
            "test": ("test.png", _png_bytes(), "image/png"),
        },
    )
    assert response.status_code == 422
    assert "Only JPEG and PNG" in response.json()["detail"]

    response = client.post(
        "/api/inspect",
        files={
            "reference": ("ref.png", _png_bytes(), "image/png"),
            "test": ("test.png", _png_bytes(), "image/png"),
        },
        data={"threshold": "999"},
    )
    assert response.status_code == 422


def test_oversized_upload_returns_413(client: TestClient) -> None:
    response = client.post(
        "/api/inspect",
        files={
            "reference": ("huge.png", b"x" * (10 * 1024 * 1024 + 1), "image/png"),
            "test": ("test.png", _png_bytes(), "image/png"),
        },
    )
    assert response.status_code == 413
    assert "10 MiB" in response.json()["detail"]


def test_detector_failure_has_generic_error_without_stack_or_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed_detector(
        reference_path: str,
        test_path: str,
        output_dir: str,
        threshold: int,
        min_area: int,
    ) -> dict:
        del reference_path, test_path, output_dir, threshold, min_area
        raise RuntimeError("internal path should not be exposed")

    monkeypatch.setattr(
        inspection_api,
        "inspection_service",
        InspectionService(output_root=tmp_path, detector=failed_detector),
    )
    response = TestClient(app).post(
        "/api/inspect",
        files={
            "reference": ("ref.png", _png_bytes(), "image/png"),
            "test": ("test.png", _png_bytes(), "image/png"),
        },
    )
    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Inspection could not be completed by the detector."
    )
    assert str(tmp_path) not in response.text


def test_artifact_route_rejects_unknown_ids_and_names(client: TestClient) -> None:
    assert client.get(
        f"/api/inspections/{uuid4()}/artifacts/annotated"
    ).status_code == 404
    assert client.get(
        f"/api/inspections/{uuid4()}/artifacts/../../secrets"
    ).status_code in {404, 422}
