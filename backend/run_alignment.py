import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from app.services.image_alignment import align_test_to_reference


def _run_pair(
    label: str,
    reference_path: Path,
    test_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    reference = cv2.imread(str(reference_path), cv2.IMREAD_COLOR)
    test = cv2.imread(str(test_path), cv2.IMREAD_COLOR)
    if reference is None:
        raise ValueError(f"Could not read reference image: {reference_path}")
    if test is None:
        raise ValueError(f"Could not read test image: {test_path}")

    result = align_test_to_reference(reference, test)
    output_dir = output_root / label
    output_dir.mkdir(parents=True, exist_ok=True)
    if result.aligned_test is not None:
        aligned_path = output_dir / "aligned_test.jpg"
        if not cv2.imwrite(str(aligned_path), result.aligned_test):
            raise OSError(f"Could not write aligned image: {aligned_path}")
        result.diagnostics["aligned_image"] = str(aligned_path)
    else:
        result.diagnostics["aligned_image"] = None

    result.diagnostics["reference_image"] = str(reference_path)
    result.diagnostics["test_image"] = str(test_path)
    diagnostic_path = output_dir / "diagnostics.json"
    result.diagnostics["diagnostics_file"] = str(diagnostic_path)
    with diagnostic_path.open("w", encoding="utf-8") as file:
        json.dump(result.diagnostics, file, indent=2)
    print(json.dumps(result.diagnostics, indent=2))
    return result.diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Align the real and synthetic image pairs for diagnostics."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/alignment"),
        help="Directory for aligned images and diagnostics.",
    )
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    datasets = repository_root / "datasets"
    pairs = (
        (
            "real_pcb",
            datasets / "real_pcb" / "reference.jpg",
            datasets / "real_pcb" / "test.jpg",
        ),
        (
            "synthetic",
            datasets / "synthetic" / "reference.jpg",
            datasets / "synthetic" / "test.jpg",
        ),
    )
    output_root = args.output
    if not output_root.is_absolute():
        output_root = repository_root / output_root
    for label, reference_path, test_path in pairs:
        _run_pair(label, reference_path, test_path, output_root)


if __name__ == "__main__":
    main()
