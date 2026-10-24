import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from app.services.inspection_evaluation import (
    evaluate_edit_coverage,
    inspect_pair,
    synthetic_edit_boxes,
)


CONFIGURATIONS = (
    {"threshold": 25, "min_area": 80},
    {"threshold": 15, "min_area": 40},
    {"threshold": 40, "min_area": 120},
)


def _read_image(path: Path) -> Any:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _save_comparison(
    output_dir: Path,
    reference: Any,
    test: Any,
    *,
    reference_path: Path,
    test_path: Path,
    configuration: dict[str, int],
    alignment_time_ms: float,
    synthetic: bool,
) -> dict[str, Any]:
    result, images = inspect_pair(
        reference,
        test,
        reference_path=str(reference_path),
        test_path=str(test_path),
        threshold=configuration["threshold"],
        min_area=configuration["min_area"],
        alignment_time_ms=alignment_time_ms,
    )
    if synthetic:
        result["synthetic_edit_evaluation"] = evaluate_edit_coverage(
            synthetic_edit_boxes(), result["regions"]
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, image in images.items():
        output_path = output_dir / filename
        if not cv2.imwrite(str(output_path), image):
            raise OSError(f"Could not write evaluation image: {output_path}")
    result_path = output_dir / "result.json"
    with result_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
    return result


def run_evaluation(output_root: Path) -> list[dict[str, Any]]:
    repository_root = Path(__file__).resolve().parents[1]
    datasets_root = repository_root / "datasets"
    pairs = (
        (
            "real_pcb",
            datasets_root / "real_pcb" / "reference.jpg",
            datasets_root / "real_pcb" / "test.jpg",
            repository_root / "outputs/alignment/real_pcb/aligned_test.jpg",
            repository_root / "outputs/alignment/real_pcb/diagnostics.json",
            False,
        ),
        (
            "synthetic",
            datasets_root / "synthetic" / "reference.jpg",
            datasets_root / "synthetic" / "test.jpg",
            repository_root / "outputs/alignment/synthetic/aligned_test.jpg",
            repository_root / "outputs/alignment/synthetic/diagnostics.json",
            True,
        ),
    )
    if not output_root.is_absolute():
        output_root = repository_root / output_root

    summaries = []
    for label, reference_path, original_path, aligned_path, alignment_json, synthetic in pairs:
        reference = _read_image(reference_path)
        original_test = _read_image(original_path)
        aligned_test = _read_image(aligned_path)
        alignment = json.loads(alignment_json.read_text(encoding="utf-8"))
        if not alignment.get("success"):
            raise RuntimeError(
                f"Alignment was not successful for {label}: "
                f"{alignment.get('failure_reason')}"
            )
        alignment_time_ms = float(alignment["alignment_time_ms"])
        reference_dimensions = (reference.shape[1], reference.shape[0])
        if (aligned_test.shape[1], aligned_test.shape[0]) != reference_dimensions:
            raise ValueError(
                f"Aligned image dimensions do not match reference for {label}."
            )

        for configuration in CONFIGURATIONS:
            config_name = (
                f"threshold_{configuration['threshold']}"
                f"_min_area_{configuration['min_area']}"
            )
            pair_dir = output_root / label / config_name
            original_result = _save_comparison(
                pair_dir / "original",
                reference,
                original_test,
                reference_path=reference_path,
                test_path=original_path,
                configuration=configuration,
                alignment_time_ms=0.0,
                synthetic=synthetic,
            )
            aligned_result = _save_comparison(
                pair_dir / "aligned",
                reference,
                aligned_test,
                reference_path=reference_path,
                test_path=aligned_path,
                configuration=configuration,
                alignment_time_ms=alignment_time_ms,
                synthetic=synthetic,
            )
            summaries.append({
                "dataset": label,
                "configuration": configuration,
                "original_candidate_count": original_result["candidate_count"],
                "aligned_candidate_count": aligned_result["candidate_count"],
                "candidate_count_delta": (
                    aligned_result["candidate_count"]
                    - original_result["candidate_count"]
                ),
                "original_processing_time_ms": original_result[
                    "processing_time_ms"
                ],
                "aligned_processing_time_ms": aligned_result[
                    "processing_time_ms"
                ],
                "alignment_time_ms": alignment_time_ms,
                "aligned_total_processing_time_ms": aligned_result[
                    "total_processing_time_ms"
                ],
            })
            print(json.dumps(summaries[-1], indent=2))
    summary_path = output_root / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summaries, file, indent=2)
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare baseline differences with and without alignment."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/alignment_evaluation"),
    )
    args = parser.parse_args()
    run_evaluation(args.output)


if __name__ == "__main__":
    main()
