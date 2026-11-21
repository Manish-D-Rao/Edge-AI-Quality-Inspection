from __future__ import annotations

import logging
import math
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.schemas.inspection import (
    CandidateBox,
    InspectionArtifacts,
    InspectionConfig,
    InspectionResponse,
)
from app.services.image_validation import decode_uploaded_image
from app.services.inspection_baseline import inspect_images


logger = logging.getLogger(__name__)
DetectorCall = Callable[..., dict[str, Any]]
ARTIFACT_NAMES = {
    "annotated": "annotated.jpg",
    "difference": "difference.jpg",
    "mask": "mask.jpg",
    "result": "result.json",
}


class DetectorExecutionError(RuntimeError):
    """Raised when a valid upload cannot be processed by the detector."""


class InspectionService:
    def __init__(
        self,
        output_root: str | Path | None = None,
        detector: DetectorCall = inspect_images,
    ) -> None:
        default_output = Path(__file__).resolve().parents[3] / "outputs" / "inspections"
        self.output_root = Path(output_root) if output_root else default_output
        self.detector = detector

    def inspect(
        self,
        reference_bytes: bytes,
        test_bytes: bytes,
        *,
        threshold: int = 25,
        min_area: int = 80,
    ) -> InspectionResponse:
        config = InspectionConfig(threshold=threshold, min_area=min_area)
        reference = decode_uploaded_image(reference_bytes)
        test = decode_uploaded_image(test_bytes)

        run_id = uuid4()
        self.output_root.mkdir(parents=True, exist_ok=True)
        staging_path = Path(
            tempfile.mkdtemp(prefix=".inspection-", dir=self.output_root)
        )
        promoted = False
        try:
            with tempfile.TemporaryDirectory(prefix="inspection-input-") as input_dir:
                input_root = Path(input_dir)
                reference_path = input_root / f"reference{reference.extension}"
                test_path = input_root / f"test{test.extension}"
                reference_path.write_bytes(reference_bytes)
                test_path.write_bytes(test_bytes)
                try:
                    result = self.detector(
                        reference_path=str(reference_path),
                        test_path=str(test_path),
                        output_dir=str(staging_path),
                        threshold=config.threshold,
                        min_area=config.min_area,
                    )
                except Exception as error:
                    logger.exception("Inspection detector failed for run %s", run_id)
                    raise DetectorExecutionError(
                        "Inspection could not be completed by the detector."
                    ) from error

            regions = result.get("regions")
            if not isinstance(regions, list):
                raise DetectorExecutionError(
                    "Detector returned an invalid candidate list."
                )
            try:
                candidates = [
                    CandidateBox.model_validate(region) for region in regions
                ]
            except ValidationError as error:
                raise DetectorExecutionError(
                    "Detector returned an invalid candidate box."
                ) from error
            processing_time = result.get("processing_time_ms")
            if (
                not isinstance(processing_time, (int, float))
                or isinstance(processing_time, bool)
                or not math.isfinite(processing_time)
                or processing_time < 0
            ):
                raise DetectorExecutionError(
                    "Detector returned an invalid processing time."
                )

            missing = [
                name
                for name in ARTIFACT_NAMES.values()
                if not (staging_path / name).is_file()
            ]
            if missing:
                raise DetectorExecutionError(
                    "Detector did not generate all required inspection artifacts."
                )

            artifacts = InspectionArtifacts(
                **{
                    key: (
                        f"/api/inspections/{run_id}/artifacts/{key}"
                    )
                    for key in ARTIFACT_NAMES
                }
            )
            response = InspectionResponse(
                inspection_id=run_id,
                detector_id="opencv_reference_difference",
                config=config,
                candidate_count=len(candidates),
                candidates=candidates,
                processing_time_ms=float(processing_time),
                artifacts=artifacts,
            )
            (staging_path / ARTIFACT_NAMES["result"]).write_text(
                response.model_dump_json(indent=2),
                encoding="utf-8",
            )
            final_path = self.output_root / str(run_id            )
            staging_path.rename(final_path)
            promoted = True
            return response
        finally:
            if not promoted:
                shutil.rmtree(staging_path)

    def artifact_path(self, inspection_id: UUID, artifact_name: str) -> Path | None:
        filename = ARTIFACT_NAMES.get(artifact_name)
        if filename is None:
            return None
        root = self.output_root.resolve()
        artifact = (root / str(inspection_id) / filename).resolve()
        if not artifact.is_relative_to(root) or not artifact.is_file():
            return None
        return artifact


inspection_service = InspectionService()
