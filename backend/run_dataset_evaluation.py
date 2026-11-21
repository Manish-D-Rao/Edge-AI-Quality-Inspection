#!/usr/bin/env python3
"""Run dataset evaluation with explicit split, detector, config, and output arguments.

Refuses to overwrite existing evaluation directories.
"""

import argparse
import json
from pathlib import Path

import cv2

from app.services.dataset_evaluation import run_dataset_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run dataset evaluation for PCB inspection"
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to dataset_manifest.csv",
    )
    parser.add_argument(
        "--splits-dir",
        default="datasets/labels/splits",
        help="Path to splits directory (default: datasets/labels/splits)",
    )
    parser.add_argument(
        "--detector",
        default="baseline",
        choices=["baseline", "structural"],
        help="Detector implementation (default: baseline)",
    )
    parser.add_argument(
        "--split",
        default=None,
        choices=["train", "validation", "held_out"],
        help="Evaluate only one split (default: all splits)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="JSON object of detector configuration",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save evaluation results (default: None)",
    )
    args = parser.parse_args()

    config = None
    if args.config:
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError as error:
            parser.error(f"Invalid JSON in --config: {error}")
        if not isinstance(config, dict):
            parser.error("--config must be a JSON object.")

    if args.output_dir and Path(args.output_dir).exists():
        parser.error(
            f"Output directory {args.output_dir!r} already exists; choose a new path."
        )

    try:
        results = run_dataset_evaluation(
            manifest_path=args.manifest,
            splits_dir=args.splits_dir,
            detector_name=args.detector,
            config=config,
            output_dir=args.output_dir,
            split_name=args.split,
        )
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        parser.exit(1, f"Dataset evaluation failed: {error}\n")

    print("Dataset evaluation complete.")
    for split_name, result in results.items():
        aggregate = result["aggregate"]
        recall = aggregate["recall"]
        recall_text = "not evaluable" if recall is None else f"{recall:.3f}"
        print(
            f"{split_name}: {aggregate['n_evaluated']} images, "
            f"recall={recall_text}, "
            f"precision={aggregate['precision']:.3f}, "
            f"F1={aggregate['f1']:.3f}, "
            f"false candidates / normal image="
            f"{aggregate['false_candidates_per_normal_image']}, "
            f"mean time={aggregate['mean_processing_time_ms']}ms"
        )


if __name__ == "__main__":
    main()