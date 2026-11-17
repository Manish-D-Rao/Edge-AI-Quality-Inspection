from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator, ValidationError


class AnnotationRegion(BaseModel):
    """Schema validator for a single annotated region in a PCB inspection label file.

    Each region in the per-image JSON annotation files must conform to this schema.
    See docs/annotation-guidelines.md and datasets/labels/README.md for field definitions.

    Attributes:
        label: One of "normal", "defect", "uncertain".
        x: Top-left x coordinate in reference-image pixel coordinates (>= 0).
        y: Top-left y coordinate in reference-image pixel coordinates (>= 0).
        width: Box width in pixels (>= 1).
        height: Box height in pixels (>= 1).
        area: Computed as width * height; must equal width * height exactly.
        status: Free-form descriptive tag (non-empty string).
        image_id: Must match the filename (without .json) of the containing file.
        annotator_id: Identifier of the annotator (non-empty string).
        creation_timestamp: ISO 8601 datetime string (e.g. "2025-01-15T10:30:45Z").
    """

    label: str
    x: int
    y: int
    width: int
    height: int
    area: int
    status: str
    image_id: str
    annotator_id: str
    creation_timestamp: str

    @field_validator("label")
    @classmethod
    def label_must_be_valid(cls, v: str) -> str:
        valid = {"normal", "defect", "uncertain"}
        if v not in valid:
            raise ValueError(f'label must be one of {valid}, got "{v}"')
        return v

    @field_validator("x")
    @classmethod
    def x_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"x must be >= 0, got {v}")
        return v

    @field_validator("y")
    @classmethod
    def y_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"y must be >= 0, got {v}")
        return v

    @field_validator("width")
    @classmethod
    def width_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"width must be >= 1, got {v}")
        return v

    @field_validator("height")
    @classmethod
    def height_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"height must be >= 1, got {v}")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("status must be a non-empty string")
        return v.strip()

    @field_validator("annotator_id")
    @classmethod
    def annotator_id_must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("annotator_id must be a non-empty string")
        return v.strip()

    @model_validator(mode="before")
    @classmethod
    def area_must_equal_width_times_height(cls, values: dict) -> dict:
        """Validate that area equals width * height before model construction."""
        width = values.get("width")
        height = values.get("height")
        area = values.get("area")
        if width is not None and height is not None and area is not None:
            if area != width * height:
                raise ValueError(
                    f"area must equal width * height ({width} * {height} = {width * height}), got {area}"
                )
        return values

    @field_validator("creation_timestamp")
    @classmethod
    def creation_timestamp_must_be_iso_8601(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            raise ValueError(f'creation_timestamp must be valid ISO 8601, got "{v}"') from e
        return v

    @classmethod
    def validate_with_image_id(cls, data: dict, image_filename: str) -> "AnnotationRegion":
        region = cls(**data)
        import posixpath
        basename = posixpath.basename(image_filename)
        expected_id = posixpath.splitext(basename)[0]
        if region.image_id != expected_id:
            raise ValidationError(
                {
                    "image_id": [
                        f'image_id "{region.image_id}" does not match expected "{expected_id}" '
                        f'(from filename "{image_filename}")'
                    ]
                },
                model=cls,
            )
        return region

    @classmethod
    def from_dict(cls, data: dict) -> "AnnotationRegion":
        return cls(**data)