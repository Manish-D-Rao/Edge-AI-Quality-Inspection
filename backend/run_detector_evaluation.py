#!/usr/bin/env python3
"""Run dataset evaluation - T028.

Runs baseline and structural detectors on splits.
Saves results to outputs/model_selection/<run-id>/ directories.
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.detector_protocol import DetectorConfig
from app.services.structural_anomaly_detector import StructuralAnomalyDetector


def load_annotation_boxes(annotation_path):
    """Load ground truth bounding boxes from annotation JSON."""
    if not os.path.exists(annotation_path):
        return []
    with open(annotation_path) as f:
        regions = json.load(f)
    boxes = []
    for r in regions:
        if r.get("label") == "defect":
            boxes.append({
                "x": int(r["x"]),
                "y": int(r["y"]),
                "width": int(r["width"]),
                "height": int(r["height"]),
                "area": int(r["area"]),
                "status": r.get("status", "defect"),
                "label": "defect",
            })
    return boxes