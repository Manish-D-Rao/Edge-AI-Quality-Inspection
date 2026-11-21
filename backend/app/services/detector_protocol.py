from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np


@dataclass
class DetectorConfig:
    threshold: float = 25.0
    min_area: int = 80
    use_registration: bool = True
    use_source_masking: bool = True
    gradient_weight: float = 0.5
    intensity_weight: float = 0.5
    min_valid_source_fraction: float = 0.1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.threshold, (int, float))
            or isinstance(self.threshold, bool)
            or not math.isfinite(self.threshold)
            or not 0 <= self.threshold <= 255
        ):
            raise ValueError("threshold must be between 0 and 255.")
        if (
            not isinstance(self.min_area, int)
            or isinstance(self.min_area, bool)
            or self.min_area < 1
        ):
            raise ValueError("min_area must be at least 1.")
        if (
            not isinstance(self.gradient_weight, (int, float))
            or isinstance(self.gradient_weight, bool)
            or not isinstance(self.intensity_weight, (int, float))
            or isinstance(self.intensity_weight, bool)
            or not math.isfinite(self.gradient_weight)
            or not math.isfinite(self.intensity_weight)
            or self.gradient_weight < 0
            or self.intensity_weight < 0
        ):
            raise ValueError("Difference weights must be finite and non-negative.")
        if self.gradient_weight + self.intensity_weight <= 0:
            raise ValueError("At least one difference weight must be positive.")
        if (
            not isinstance(self.min_valid_source_fraction, (int, float))
            or isinstance(self.min_valid_source_fraction, bool)
            or not math.isfinite(self.min_valid_source_fraction)
            or not 0 < self.min_valid_source_fraction <= 1
        ):
            raise ValueError(
                "min_valid_source_fraction must be greater than 0 and at most 1."
            )
        if not isinstance(self.use_registration, bool) or not isinstance(
            self.use_source_masking, bool
        ):
            raise ValueError("Registration and source-masking flags must be booleans.")


@dataclass
class DetectorOutput:
    candidates: list[dict[str, int | str]]
    gradient_map: np.ndarray | None = None
    intensity_map: np.ndarray | None = None
    combined_map: np.ndarray | None = None
    binary_mask: np.ndarray | None = None
    valid_source_mask: np.ndarray | None = None
    processing_time_ms: float = 0.0
    success: bool = True
    failure_reason: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorInput:
    reference_image: np.ndarray
    test_image: np.ndarray
    config: DetectorConfig = field(default_factory=DetectorConfig)


@runtime_checkable
class DetectorProtocol(Protocol):
    @classmethod
    def from_config(cls, config: dict[str, Any]) -> DetectorProtocol: ...

    def detect(
        self, reference: np.ndarray, test: np.ndarray
    ) -> DetectorOutput: ...

    @property
    def config(self) -> DetectorConfig: ...
