from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    area: int = Field(ge=0)
    status: Literal["suspicious_difference"]


class InspectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: int = Field(ge=0, le=255)
    min_area: int = Field(ge=1)


class InspectionArtifacts(BaseModel):
    annotated: str
    difference: str
    mask: str
    result: str


class InspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inspection_id: UUID
    status: Literal["completed"] = "completed"
    detector_id: Literal["opencv_reference_difference"]
    config: InspectionConfig
    candidate_count: int = Field(ge=0)
    candidates: list[CandidateBox]
    processing_time_ms: float = Field(ge=0, allow_inf_nan=False)
    artifacts: InspectionArtifacts
    warning: Literal[
        "Candidates indicate image differences, not confirmed defects."
    ] = "Candidates indicate image differences, not confirmed defects."


class ErrorResponse(BaseModel):
    detail: str
