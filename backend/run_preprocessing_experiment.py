import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from app.services.inspection_evaluation import (
    evaluate_edit_coverage,
    synthetic_edit_boxes,
)
from app.services.preprocessing_experiment import (
    CONFIGURATION,
    VARIANTS,
    inspect_variant,
)


def _load_image(path: Path) -> Any:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _write_json(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def run(output_root: Path) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[1]
    if not output_root.is_absolute():
        output_root = repository_root / output_root
    if output_root.exists():
        raise FileExistsError(
            f"Experiment output already exists; refusing to overwrite: {output_root}"
        )

    dataset_root = repository_root / "datasets"
    pairs = [
        (
            "real_pcb",
            dataset_root / "real_pcb/reference.jpg",
            dataset_root / "real_pcb/test.jpg",
            False,
        )
    ]
    synthetic_reference = dataset_root / "synthetic/reference.jpg"
    synthetic_test = dataset_root / "synthetic/test.jpg"
    if synthetic_reference.is_file() and synthetic_test.is_file():
        pairs.append(
            ("synthetic", synthetic_reference, synthetic_test, True)
        )

    output_root.mkdir(parents=True)
    summary: dict[str, Any] = {
        "configuration": CONFIGURATION,
        "datasets": {},
    }
    for dataset, reference_path, test_path, synthetic in pairs:
        reference = _load_image(reference_path)
        test = _load_image(test_path)
        dataset_result = {
            "reference_image": str(reference_path),
            "test_image": str(test_path),
            "variants": {},
        }
        for variant in VARIANTS:
            result, images = inspect_variant(
                reference,
                test,
                variant=variant,
                threshold=CONFIGURATION["threshold"],
                min_area=CONFIGURATION["min_area"],
            )
            result["dataset"] = dataset
            if synthetic:
                result["synthetic_edit_coverage"] = evaluate_edit_coverage(
                    synthetic_edit_boxes(), result["regions"]
                )
            variant_dir = output_root / dataset / variant
            variant_dir.mkdir(parents=True)
            for filename, image in images.items():
                path = variant_dir / filename
                if not cv2.imwrite(str(path), image):
                    raise OSError(f"Could not write experiment image: {path}")
            _write_json(variant_dir / "result.json", result)
            dataset_result["variants"][variant] = {
                key: result[key]
                for key in (
                    "candidate_count",
                    "foreground_mask_pixels",
                    "foreground_mask_percentage",
                    "connected_component_count",
                    "processing_time_ms",
                )
            }
            if synthetic:
                dataset_result["variants"][variant][
                    "synthetic_edit_coverage"
                ] = result["synthetic_edit_coverage"]
        summary["datasets"][dataset] = dataset_result
    _write_json(output_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare modest preprocessing variations with the baseline."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/preprocessing_experiment"),
    )
    args = parser.parse_args()
    results = run(args.output)
    for dataset, dataset_result in results["datasets"].items():
        print(dataset)
        for variant, values in dataset_result["variants"].items():
            print(variant, json.dumps(values, sort_keys=True))


if __name__ == "__main__":
    main()
