import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.services.alignment_artifact_diagnostic import (
    analyze_comparison,
    compare_masks,
    warp_with_valid_source_mask,
)


def _load(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _write_comparison(
    output: Path,
    reference: np.ndarray,
    test: np.ndarray,
    support: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray]:
    stats, images = analyze_comparison(reference, test, support)
    output.mkdir(parents=True, exist_ok=False)
    for name, image in images.items():
        path = output / name
        if not cv2.imwrite(str(path), image):
            raise OSError(f"Could not write diagnostic image: {path}")
    result_path = output / "result.json"
    result_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats, images["mask.png"]


def run(output_root: Path) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[1]
    if not output_root.is_absolute():
        output_root = repository_root / output_root
    if output_root.exists():
        raise FileExistsError(
            f"Diagnostic output already exists; refusing to overwrite: {output_root}"
        )

    reference_path = repository_root / "datasets/real_pcb/reference.jpg"
    test_path = repository_root / "datasets/real_pcb/test.jpg"
    saved_aligned_path = (
        repository_root / "outputs/alignment/real_pcb/aligned_test.jpg"
    )
    alignment_diagnostics_path = (
        repository_root / "outputs/alignment/real_pcb/diagnostics.json"
    )
    reference = _load(reference_path)
    original_test = _load(test_path)
    saved_aligned = _load(saved_aligned_path)
    alignment = json.loads(
        alignment_diagnostics_path.read_text(encoding="utf-8")
    )
    if not alignment.get("success"):
        raise RuntimeError(
            f"Saved alignment did not succeed: {alignment.get('failure_reason')}"
        )
    homography = np.asarray(
        alignment["homography_test_to_reference"], dtype=np.float64
    )
    reference_height, reference_width = reference.shape[:2]
    if saved_aligned.shape[:2] != reference.shape[:2]:
        raise ValueError("Saved aligned JPEG does not match reference dimensions.")

    original_resized = cv2.resize(
        original_test,
        (reference_width, reference_height),
        interpolation=cv2.INTER_AREA,
    )
    memory_aligned, valid_support = warp_with_valid_source_mask(
        original_test,
        homography,
        (reference_width, reference_height),
    )
    all_valid = np.full((reference_height, reference_width), 255, np.uint8)

    output_root.mkdir(parents=True)
    paths = {
        "A_original_inter_area": (
            original_resized,
            all_valid,
            reference_path,
            test_path,
        ),
        "B_saved_aligned_jpeg": (
            saved_aligned,
            valid_support,
            reference_path,
            saved_aligned_path,
        ),
        "C_in_memory_warp": (
            memory_aligned,
            valid_support,
            reference_path,
            test_path,
        ),
    }
    results: dict[str, Any] = {
        "dataset": "real_pcb",
        "configuration": {"threshold": 25, "min_area": 80},
        "reference_image": str(reference_path),
        "original_test_image": str(test_path),
        "saved_aligned_jpeg": str(saved_aligned_path),
        "homography_source": str(alignment_diagnostics_path),
        "alignment_time_ms": alignment["alignment_time_ms"],
        "alignment_method": alignment["method"],
        "output_dimensions": {
            "width": reference_width,
            "height": reference_height,
        },
        "valid_source_mask_method": (
            "Warp an all-255 source mask with the same homography, INTER_LINEAR, "
            "and constant-zero border; only pixels whose interpolated support "
            "remains 255 are marked valid."
        ),
        "paths": {},
    }
    binary_masks = {}
    for name, (test_image, support, _, _) in paths.items():
        result, mask = _write_comparison(
            output_root / name,
            reference,
            test_image,
            support,
        )
        result["input_image"] = str(paths[name][3])
        result["alignment_time_ms"] = (
            0.0 if name == "A_original_inter_area" else alignment["alignment_time_ms"]
        )
        result["total_including_alignment_ms"] = round(
            result["processing_time_ms"] + result["alignment_time_ms"], 2
        )
        (output_root / name / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        results["paths"][name] = result
        binary_masks[name] = mask

    results["jpeg_vs_memory_mask_comparison"] = compare_masks(
        binary_masks["B_saved_aligned_jpeg"],
        binary_masks["C_in_memory_warp"],
        valid_support,
    )
    results_path = output_root / "summary.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Isolate resampling, border support, and JPEG effects."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/alignment_artifact_diagnostic"),
    )
    args = parser.parse_args()
    results = run(args.output)
    for name, result in results["paths"].items():
        print(
            name,
            "candidates=", result["candidate_count"],
            "foreground%=", result["foreground_percentage_of_full_image"],
            "components=", result["connected_components"]["full_mask_count"],
            "border_pixels=", result["invalid_border_foreground_pixels"],
        )
    print("JPEG vs memory:", results["jpeg_vs_memory_mask_comparison"])


if __name__ == "__main__":
    main()
