
from fastapi import FastAPI

from app.api.inspection import router as inspection_router

app = FastAPI(
    title="Edge Quality Inspection API",
    version="0.1.0",
    description="Lightweight industrial inspection prototype",
)
app.include_router(inspection_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "project": "edge-quality-inspection",
        "phase": "03",
    }