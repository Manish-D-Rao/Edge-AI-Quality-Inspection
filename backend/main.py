
from fastapi import FastAPI

app = FastAPI(
    title="Edge Quality Inspection API",
    version="0.1.0",
    description="Lightweight industrial inspection prototype",
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "project": "edge-quality-inspection",
        "phase": "00",
    }
