from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.detection_metrics import compute_metrics
from app.services.detector_protocol import DetectorConfig
from app.services.inspection_baseline import inspect_images
from app.services.structural_anomaly_detector import StructuralAnomalyDetector


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_GROUND_TRUTH = [
    {
        "x": 367,
        "y": 67,
        "width": 57,
        "height": 19,
        "area": 1083,
        "label": "synthetic_edit",
        "status": "line from (370, 70) to (420, 82), thickness 5",
    },
    {
        "x": 511,
        "y": 141,
        "width": 19,
        "height": 19,
        "area": 361,
        "label": "synthetic_edit",
        "status": "circle centered at (520, 150), radius 9",
    },
]


def _write_image(path: Path, image: np.ndarray) -> None:
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write experiment image: {path}")


def _visualize(
    test_image: np.ndarray,
    candidates: list[dict[str, Any]],
) -> np.ndarray:
    annotated = test_image.copy()
    for region in SYNTHETIC_GROUND_TRUTH:
        x, y = region["x"], region["y"]
        cv2.rectangle(
            annotated,
            (x, y),
            (x + region["width"], y + region["height"]),
            (0, 200, 0),
            1,
        )
    for index, candidate in enumerate(candidates, start=1):
        x, y = candidate["x"], candidate["y"]
        width, height = candidate["width"], candidate["height"]
        cv2.rectangle(
            annotated,
            (x, y),
            (x + width, y + height),
            (0, 0, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"C{index}",
            (x, max(15, y - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    return annotated


def run_comparison(
    reference_path: str | Path,
    test_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    reference_path = Path(reference_path).resolve()
    test_path = Path(test_path).resolve()
    output_path = Path(output_dir).resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite {output_path}")
    reference = cv2.imread(str(reference_path), cv2.IMREAD_COLOR)
    test = cv2.imread(str(test_path), cv2.IMREAD_COLOR)
    if reference is None or test is None:
        raise ValueError("Both input image paths must be readable images.")
    if reference.shape[:2] != test.shape[:2]:
        raise ValueError("Synthetic comparison pair must have equal dimensions.")
    output_path.mkdir(parents=True)

    baseline_dir = output_path / "baseline"
    baseline_dir.mkdir()
    baseline = inspect_images(
        str(reference_path),
        str(test_path),
        output_dir=str(baseline_dir),
        threshold=25,
        min_area=80,
    )
    baseline_regions = baseline["regions"]
    baseline_metrics = compute_metrics(
        baseline_regions,
        SYNTHETIC_GROUND_TRUTH,
        iou_threshold=0.3,
    )

    structural_dir = output_path / "structural"
    structural_dir.mkdir()
    structural_detector = StructuralAnomalyDetector(
        DetectorConfig(
            threshold=25,
            min_area=80,
            use_registration=True,
            use_source_masking=True,
            gradient_weight=0.5,
            intensity_weight=0.5,
        )
    )
    structural = structural_detector.detect(reference, test)
    structural_result: dict[str, Any] = {
        "success": structural.success,
        "failure_reason": structural.failure_reason,
        "candidate_count": len(structural.candidates),
        "processing_time_ms": structural.processing_time_ms,
        "regions": structural.candidates,
        "diagnostics": structural.diagnostics,
        "config": {
            "threshold": 25,
            "min_area": 80,
            "use_registration": True,
            "use_source_masking": True,
            "gradient_weight": 0.5,
            "intensity_weight": 0.5,
        },
    }

    if structural.success:
        structural_result["metrics"] = compute_metrics(
            structural.candidates,
            SYNTHETIC_GROUND_TRUTH,
            iou_threshold=0.3,
        )
        if structural.binary_mask is None:
            raise RuntimeError("Structural detector did not return its binary mask.")
        if structural.intensity_map is None or structural.gradient_map is None:
            raise RuntimeError("Structural detector did not return its diagnostic maps.")
        if structural.combined_map is None:
            raise RuntimeError("Structural detector did not return its combined map.")
        _write_image(
            structural_dir / "annotated.jpg",
            _visualize(test, structural.candidates),
        )
        _write_image(structural_dir / "intensity_difference.jpg", structural.intensity_map)
        _write_image(structural_dir / "gradient_difference.jpg", structural.gradient_map)
        _write_image(structural_dir / "combined_difference.jpg", structural.combined_map)
        _write_image(structural_dir / "mask.jpg", structural.binary_mask)
        structural_json = structural_result
    else:
        structural_json = structural_result
    (structural_dir / "result.json").write_text(
        json.dumps(structural_json, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    summary = {
        "experiment": "synthetic_baseline_vs_structural",
        "scope": "single generated synthetic pair; not real PCB validation",
        "reference_image": str(reference_path),
        "test_image": str(test_path),
        "dimensions": {
            "width": int(reference.shape[1]),
            "height": int(reference.shape[0]),
        },
        "iou_threshold": 0.3,
        "synthetic_ground_truth_source": (
            "Known artificial edits in backend/create_demo_images.py; "
            "boxes enclose the generated line and circle."
        ),
        "ground_truth": SYNTHETIC_GROUND_TRUTH,
        "baseline": {
            "detector_id": baseline["method"],
            "config": baseline["parameters"],
            "candidate_count": baseline["candidate_count"],
            "processing_time_ms": baseline["processing_time_ms"],
            "metrics": baseline_metrics,
            "annotated_image": "baseline/annotated.jpg",
        },
        "structural": structural_result,
        "normal_image_false_candidate_budget": {
            "approved_limit_per_image_mean": 5,
            "status": "not_evaluable",
            "reason": "The pair includes artificial edits; no normal-only image is present.",
        },
        "selection": {
            "frozen": False,
            "reason": (
                "A single synthetic pair cannot represent development and "
                "validation splits or support real PCB detector selection."
            ),
        },
        "limitations": [
            "Synthetic edits are not verified real PCB defects.",
            "No normal-only image exists to evaluate the approved false-candidate budget.",
            "This single pair is not an independent development/validation set.",
        ],
    }
    if structural.success:
        summary["structural"]["metrics"] = compute_metrics(
            structural.candidates,
            SYNTHETIC_GROUND_TRUTH,
            iou_threshold=0.3,
        )
        summary["structural"]["annotated_image"] = "structural/annotated.jpg"
    summary_path = output_path / "comparison.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare baseline and structural detectors on the known synthetic demo pair."
    )
    parser.add_argument(
        "--reference",
        default=str(REPOSITORY_ROOT / "datasets/synthetic/reference.jpg"),
    )
    parser.add_argument(
        "--test",
        default=str(REPOSITORY_ROOT / "datasets/synthetic/test.jpg"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(
            REPOSITORY_ROOT / "outputs/model_selection" / f"synthetic-{uuid4()}"
        ),
    )
    args = parser.parse_args()
    try:
        result = run_comparison(args.reference, args.test, args.output_dir)
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        parser.exit(1, f"Synthetic comparison failed: {error}\n")

    print(json.dumps(result, indent=2))
    print(f"\nSaved synthetic-only comparison to: {args.output_dir}")


if __name__ == "__main__":
    main()
