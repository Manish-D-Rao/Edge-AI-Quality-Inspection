from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.inspection import (
    CandidateBox,
    InspectionArtifacts,
    InspectionConfig,
    InspectionResponse,
)


def valid_response() -> dict:
    return {
        "inspection_id": uuid4(),
        "status": "completed",
        "detector_id": "opencv_reference_difference",
        "config": {"threshold": 25, "min_area": 80},
        "candidate_count": 1,
        "candidates": [
            {
                "x": 1,
                "y": 2,
                "width": 10,
                "height": 12,
                "area": 100,
                "status": "suspicious_difference",
            }
        ],
        "processing_time_ms": 2.5,
        "artifacts": {
            "annotated": "/api/inspections/id/artifacts/annotated",
            "difference": "/api/inspections/id/artifacts/difference",
            "mask": "/api/inspections/id/artifacts/mask",
            "result": "/api/inspections/id/artifacts/result",
        },
        "warning": "Candidates indicate image differences, not confirmed defects.",
    }


def test_response_schema_accepts_candidate_not_confirmed_defect() -> None:
    response = InspectionResponse.model_validate(valid_response())
    assert response.candidate_count == 1
    assert response.warning.endswith("not confirmed defects.")


@pytest.mark.parametrize(
    "candidate",
    [
        {"x": -1, "y": 0, "width": 2, "height": 2, "area": 4, "status": "suspicious_difference"},
        {"x": 0, "y": 0, "width": 0, "height": 2, "area": 0, "status": "suspicious_difference"},
        {"x": 0, "y": 0, "width": 2, "height": 2, "area": 4, "status": "confirmed_defect"},
    ],
)
def test_candidate_schema_rejects_invalid_coordinates_or_claims(
    candidate: dict,
) -> None:
    with pytest.raises(ValidationError):
        CandidateBox.model_validate(candidate)


def test_config_schema_enforces_baseline_parameter_ranges() -> None:
    with pytest.raises(ValidationError):
        InspectionConfig(threshold=256, min_area=1)
    with pytest.raises(ValidationError):
        InspectionConfig(threshold=25, min_area=0)


def test_response_rejects_unexpected_or_invalid_fields() -> None:
    payload = valid_response()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        InspectionResponse.model_validate(payload)

    payload = valid_response()
    payload["candidate_count"] = -1
    with pytest.raises(ValidationError):
        InspectionResponse.model_validate(payload)


def test_artifact_schema_requires_every_known_artifact() -> None:
    with pytest.raises(ValidationError):
        InspectionArtifacts(annotated="/annotated")
