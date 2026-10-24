import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import cv2

from app.services.candidate_merging import (
    merge_candidate_boxes,
    summarize_boxes,
)
from app.services.inspection_evaluation import (
    evaluate_edit_coverage,
    inspect_pair,
    synthetic_edit_boxes,
)


CONFIGURATION = {"threshold": 25, "min_area": 80}
FIXED_DISTANCE_PIXELS = 10
RELATIVE_DIAGONAL_FRACTION = 0.0025
STRATEGIES = (
    ("overlap", "Merge boxes with positive-area overlap."),
    (
        "nearby_10px",
        "Merge boxes whose maximum x/y edge-to-edge gap is at most 10 pixels.",
    ),
    (
        "nearby_0_25pct_diagonal",
        "Merge boxes whose maximum x/y edge-to-edge gap is at most 0.25% "
        "of the image diagonal.",
    ),
)


def _load_image(path: Path) -> Any:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _draw_boxes(
    image: Any, regions: list[dict[str, Any]], *, merged: bool
) -> Any:
    annotated = image.copy()
    color = (255, 0, 255) if merged else (0, 0, 255)
    for index, region in enumerate(regions):
        x, y = int(region["x"]), int(region["y"])
        width, height = int(region["width"]), int(region["height"])
        cv2.rectangle(
            annotated,
            (x, y),
            (x + width, y + height),
            color,
            2 if merged else 1,
        )
        if merged:
            cv2.putText(
                annotated,
                str(region["group_size"]),
                (x, max(18, y - 3)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )
    return annotated


def _write_json(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def _merge_parameters(
    strategy: str, width: int, height: int
) -> tuple[str, float]:
    if strategy == "overlap":
        return "positive-area intersection; transitive groups", 0
    if strategy == "nearby_10px":
        return "maximum x/y edge gap <= 10 pixels; transitive groups", float(
            FIXED_DISTANCE_PIXELS
        )
    diagonal = math.hypot(width, height)
    threshold = diagonal * RELATIVE_DIAGONAL_FRACTION
    return (
        "maximum x/y edge gap <= 0.25% of image diagonal; transitive groups",
        threshold,
    )


def _save_run(
    run_dir: Path,
    source_image: Any,
    regions: list[dict[str, Any]],
    *,
    dataset: str,
    strategy: str,
    strategy_description: str,
    threshold_description: float,
    merge_time_ms: float,
) -> dict[str, Any]:
    summary = summarize_boxes(regions)
    result = {
        "dataset": dataset,
        "strategy": strategy,
        "strategy_description": strategy_description,
        "distance_threshold_pixels": threshold_description,
        "merge_processing_time_ms": merge_time_ms,
        **summary,
        "regions": regions,
    }
    run_dir.mkdir(parents=True)
    annotated_path = run_dir / "annotated.jpg"
    if not cv2.imwrite(
        str(annotated_path),
        _draw_boxes(source_image, regions, merged=(strategy != "original")),
    ):
        raise OSError(f"Could not write visualization: {annotated_path}")
    _write_json(run_dir / "result.json", result)
    return result


def _run_pair(
    repository_root: Path,
    output_root: Path,
    dataset: str,
    reference_path: Path,
    test_path: Path,
    *,
    synthetic: bool,
) -> dict[str, Any]:
    reference = _load_image(reference_path)
    test = _load_image(test_path)
    baseline, _ = inspect_pair(
        reference,
        test,
        reference_path=str(reference_path),
        test_path=str(test_path),
        threshold=CONFIGURATION["threshold"],
        min_area=CONFIGURATION["min_area"],
    )
    original_regions = baseline["regions"]
    height, width = reference.shape[:2]
    pair_dir = output_root / dataset
    pair_dir.mkdir(parents=True)
    original_result = _save_run(
        pair_dir / "original",
        test if test.shape[:2] == reference.shape[:2] else cv2.resize(
            test, (width, height), interpolation=cv2.INTER_AREA
        ),
        original_regions,
        dataset=dataset,
        strategy="original",
        strategy_description="Unmerged baseline candidates.",
        threshold_description=0,
        merge_time_ms=0.0,
    )
    original_result["baseline_processing_time_ms"] = baseline["processing_time_ms"]
    original_result["configuration"] = CONFIGURATION
    _write_json(pair_dir / "original" / "result.json", original_result)

    edits = synthetic_edit_boxes() if synthetic else []
    if synthetic:
        original_result["synthetic_edit_coverage"] = evaluate_edit_coverage(
            edits, original_regions
        )
        _write_json(pair_dir / "original" / "result.json", original_result)

    strategy_results = []
    for strategy, description in STRATEGIES:
        strategy_description, distance = _merge_parameters(
            strategy, width, height
        )
        started = time.perf_counter()
        merged_regions = merge_candidate_boxes(
            original_regions,
            strategy="overlap" if strategy == "overlap" else "nearby",
            distance_threshold=distance,
        )
        merge_time_ms = round((time.perf_counter() - started) * 1000, 4)
        result = _save_run(
            pair_dir / strategy,
            test if test.shape[:2] == reference.shape[:2] else cv2.resize(
                test, (width, height), interpolation=cv2.INTER_AREA
            ),
            merged_regions,
            dataset=dataset,
            strategy=strategy,
            strategy_description=f"{description} {strategy_description}",
            threshold_description=distance,
            merge_time_ms=merge_time_ms,
        )
        result["original_candidate_count"] = len(original_regions)
        result["baseline_processing_time_ms"] = baseline["processing_time_ms"]
        result["configuration"] = CONFIGURATION
        if synthetic:
            result["synthetic_edit_coverage"] = evaluate_edit_coverage(
                edits, merged_regions
            )
        _write_json(pair_dir / strategy / "result.json", result)
        strategy_results.append(result)

    return {
        "dataset": dataset,
        "image_dimensions": {"width": width, "height": height},
        "configuration": CONFIGURATION,
        "baseline_processing_time_ms": baseline["processing_time_ms"],
        "original": original_result,
        "strategies": strategy_results,
    }


def run(output_root: Path) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[1]
    if not output_root.is_absolute():
        output_root = repository_root / output_root
    if output_root.exists():
        raise FileExistsError(
            f"Experiment output already exists; refusing to overwrite: {output_root}"
        )
    datasets_root = repository_root / "datasets"
    pairs = [
        (
            "real_pcb",
            datasets_root / "real_pcb/reference.jpg",
            datasets_root / "real_pcb/test.jpg",
            False,
        )
    ]
    synthetic_reference = datasets_root / "synthetic/reference.jpg"
    synthetic_test = datasets_root / "synthetic/test.jpg"
    if synthetic_reference.is_file() and synthetic_test.is_file():
        pairs.append(
            ("synthetic", synthetic_reference, synthetic_test, True)
        )

    output_root.mkdir(parents=True)
    results = {
        "configuration": CONFIGURATION,
        "merge_semantics": (
            "Groups are connected components of the pairwise merge relation; "
            "merging is transitive and outputs the union bounding rectangle."
        ),
        "relative_distance_definition": (
            "0.25% of the image diagonal, computed independently for each "
            "dataset's reference dimensions."
        ),
        "datasets": {},
    }
    for dataset, reference_path, test_path, synthetic in pairs:
        dataset_result = _run_pair(
            repository_root,
            output_root,
            dataset,
            reference_path,
            test_path,
            synthetic=synthetic,
        )
        results["datasets"][dataset] = dataset_result
    _write_json(output_root / "summary.json", results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate candidate-box merging strategies separately."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/candidate_merging_experiment"),
    )
    args = parser.parse_args()
    result = run(args.output)
    for dataset, dataset_result in result["datasets"].items():
        print(dataset, "original=", dataset_result["original"]["candidate_count"])
        for strategy in dataset_result["strategies"]:
            print(
                strategy["strategy"],
                "merged=", strategy["candidate_count"],
                "groups=", strategy["merge_group_sizes"],
                "merge_ms=", strategy["merge_processing_time_ms"],
            )


if __name__ == "__main__":
    main()
