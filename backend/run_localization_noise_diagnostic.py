import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from app.services.inspection_evaluation import inspect_pair
from app.services.localization_noise_diagnostic import analyze_localization


def _load_image(path: Path) -> Any:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def run(output_dir: Path) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[1]
    if not output_dir.is_absolute():
        output_dir = repository_root / output_dir
    if output_dir.exists():
        raise FileExistsError(
            f"Diagnostic output already exists; refusing to overwrite: {output_dir}"
        )

    reference_path = repository_root / "datasets/real_pcb/reference.jpg"
    test_path = repository_root / "datasets/real_pcb/test.jpg"
    reference = _load_image(reference_path)
    test = _load_image(test_path)
    baseline, baseline_images = inspect_pair(
        reference,
        test,
        reference_path=str(reference_path),
        test_path=str(test_path),
        threshold=25,
        min_area=80,
    )
    result, diagnostic_images = analyze_localization(
        reference, baseline["regions"]
    )
    result.update({
        "experiment": "original INTER_AREA resize baseline",
        "reference_image": str(reference_path),
        "test_image": str(test_path),
        "configuration": {"threshold": 25, "min_area": 80},
        "baseline_processing_time_ms": baseline["processing_time_ms"],
        "processing_time_scope": baseline["processing_time_scope"],
    })
    output_dir.mkdir(parents=True)
    images = {
        **baseline_images,
        **diagnostic_images,
    }
    for name, image in images.items():
        path = output_dir / name
        if not cv2.imwrite(str(path), image):
            raise OSError(f"Could not write diagnostic image: {path}")
    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze localization noise in the real PCB baseline."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/localization_noise_diagnostic"),
    )
    args = parser.parse_args()
    result = run(args.output)
    print("Candidates:", result["candidate_count"])
    print(
        "Contour area buckets:",
        result["distributions"]["contour_area_buckets"],
    )
    print(
        "Bounding box area buckets:",
        result["distributions"]["bounding_box_area_buckets"],
    )
    print(
        "Aspect ratio buckets:",
        result["distributions"]["aspect_ratio_buckets"],
    )
    print(
        "Nearby box groups (10 px):",
        result["nearby_boxes"]["within_10_pixels"],
    )
    print("Saved diagnostic to:", args.output)


if __name__ == "__main__":
    main()
