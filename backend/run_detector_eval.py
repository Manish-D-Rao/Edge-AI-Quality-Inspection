from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.detector_protocol import DetectorConfig
from app.services.structural_anomaly_detector import StructuralAnomalyDetector


def load_annotation_boxes(annotation_path: str) -> List[Dict[str, Any]]:
    """Load ground truth bounding boxes from annotation JSON."""
    if not os.path.exists(annotation_path):
        return []
    with open(annotation_path) as f:
        regions = json.load(f)
    boxes = []
    for region in regions:
        if region.get("label") == "defect":
            boxes.append({
                "x": int(region["x"]),
                "y": int(region["y"]),
                "width": int(region["width"]),
                "height": int(region["height"]),
                "area": int(region["area"]),
                "status": region.get("status", "defect"),
                "label": "defect",
            })
    return boxes


def load_splits(splits_dir: str) -> Dict[str, List[str]]:
    """Load split ID lists from datasets/labels/splits/."""
    splits = {}
    for split_name in ["train", "validation", "held_out"]:
        split_path = os.path.join(splits_dir, f"{split_name}_ids.json")
        if os.path.exists(split_path):
            with open(split_path) as f:
                splits[split_name] = json.load(f)
        else:
            splits[split_name] = []
    return splits