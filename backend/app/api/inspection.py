from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas.inspection import InspectionResponse
from app.services.image_validation import ImageValidationError, MAX_IMAGE_BYTES
from app.services.inspection_service import (
    DetectorExecutionError,
    inspection_service,
)


router = APIRouter(prefix="/api", tags=["inspection"])


async def _read_limited_upload(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(64 * 1024):
        total += len(chunk)
        if total > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/inspect", response_model=InspectionResponse)
async def inspect_uploads(
    reference: UploadFile = File(...),
    test: UploadFile = File(...),
    threshold: int = Form(default=25, ge=0, le=255),
    min_area: int = Form(default=80, ge=1),
) -> InspectionResponse:
    reference_bytes = await _read_limited_upload(reference)
    test_bytes = await _read_limited_upload(test)
    try:
        return inspection_service.inspect(
            reference_bytes,
            test_bytes,
            threshold=threshold,
            min_area=min_area,
        )
    except ImageValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except DetectorExecutionError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="Inspection artifacts could not be stored.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/inspections/{inspection_id}/artifacts/{artifact_name}")
def get_inspection_artifact(
    inspection_id: UUID,
    artifact_name: str,
) -> FileResponse:
    artifact = inspection_service.artifact_path(inspection_id, artifact_name)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Inspection artifact not found.")
    return FileResponse(
        path=artifact,
        media_type="application/json" if artifact.suffix == ".json" else "image/jpeg",
        filename=artifact.name,
    )
