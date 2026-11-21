from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.annotation_schema import AnnotationRegion
from app.services.dataset_evaluation import load_manifest


RANDOM_SEED = 42
SPLIT_NAMES = ("train", "validation", "held_out")


def _resolve_path(raw_path: str, manifest_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    manifest_path = manifest_path.resolve()
    root = (
        manifest_path.parents[2]
        if manifest_path.parent.name == "labels"
        else manifest_path.parent
    )
    root_candidate = root / path
    if root_candidate.exists():
        return root_candidate
    return manifest_path.parent / path


def _sample_metadata(
    row: dict[str, str], manifest_path: Path
) -> tuple[int, str]:
    sample_id = row["sample_id"].strip()
    if row["label_status"].strip().lower() != "complete":
        raise ValueError(f"Sample {sample_id!r} is not completely labeled.")
    sample_class = row["sample_class"].strip().lower()
    if sample_class not in {"normal", "defect"}:
        raise ValueError(
            f"Sample {sample_id!r} has unsupported sample_class "
            f"{row['sample_class']!r}."
        )

    reference_path = _resolve_path(row["reference_path"], manifest_path)
    test_path = _resolve_path(row["test_path"], manifest_path)
    reference = cv2.imread(str(reference_path), cv2.IMREAD_UNCHANGED)
    test = cv2.imread(str(test_path), cv2.IMREAD_UNCHANGED)
    if reference is None:
        raise ValueError(
            f"Could not read reference image for {sample_id!r}: {reference_path}"
        )
    if test is None:
        raise ValueError(f"Could not read test image for {sample_id!r}: {test_path}")
    height, width = reference.shape[:2]
    annotation_path = _resolve_path(row["annotation_path"], manifest_path)
    if annotation_path.stem != sample_id:
        raise ValueError(
            f"Annotation filename {annotation_path.name!r} does not match "
            f"sample_id {sample_id!r}."
        )
    try:
        annotations = json.loads(annotation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read annotations {annotation_path}: {error}") from error
    if not isinstance(annotations, list):
        raise ValueError(f"Annotation file must contain a list: {annotation_path}")

    defect_instances = 0
    for index, raw_region in enumerate(annotations):
        if not isinstance(raw_region, dict):
            raise ValueError(f"Annotation {index} in {annotation_path} is not an object.")
        try:
            region = AnnotationRegion.model_validate(raw_region)
        except ValidationError as error:
            raise ValueError(
                f"Invalid annotation {index} in {annotation_path}: {error}"
            ) from error
        if region.image_id != sample_id:
            raise ValueError(
                f"Annotation image_id {region.image_id!r} does not match "
                f"sample_id {sample_id!r}."
            )
        if region.x + region.width > width or region.y + region.height > height:
            raise ValueError(
                f"Annotation {index} exceeds image dimensions {width}x{height}."
            )
        if region.label == "defect":
            defect_instances += 1
    if sample_class == "normal" and defect_instances:
        raise ValueError(f"Normal sample {sample_id!r} has defect annotations.")
    if sample_class == "defect" and not defect_instances:
        raise ValueError(f"Defect sample {sample_id!r} has no defect annotations.")
    return defect_instances, sample_class


def _group_key(row: dict[str, str]) -> str:
    board_id = (row.get("board_id") or "").strip()
    capture_session = (row.get("capture_session") or "").strip()
    unknown_values = {"", "unknown", "n/a", "na", "none"}
    if board_id.lower() not in unknown_values:
        return f"board:{board_id}"
    if capture_session.lower() not in unknown_values:
        return f"session:{capture_session}"
    raise ValueError(
        f"Sample {row['sample_id']!r} needs a known board_id or capture_session "
        "to prevent split leakage."
    )


def create_splits(
    manifest_path: str | Path,
    heldout_defect_min: int = 20,
    heldout_normal_min: int = 20,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    rows = load_manifest(manifest_path)
    if not rows:
        raise ValueError("Cannot create splits from an empty manifest.")

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    labels: dict[str, tuple[int, str]] = {}
    for row in rows:
        sample_id = row["sample_id"].strip()
        groups[_group_key(row)].append(row)
        labels[sample_id] = _sample_metadata(row, manifest_path)
    if len(groups) < len(SPLIT_NAMES):
        raise ValueError(
            "At least three independent board/capture-session groups are required "
            "to create non-empty train, validation, and held-out splits."
        )

    randomized_groups = list(groups.items())
    random.Random(seed).shuffle(randomized_groups)
    randomized_groups.sort(key=lambda item: -len(item[1]))
    targets = {"train": 0.6, "validation": 0.2, "held_out": 0.2}
    assigned: dict[str, list[str]] = {name: [] for name in SPLIT_NAMES}
    assigned_groups: dict[str, list[str]] = {name: [] for name in SPLIT_NAMES}
    counts = {name: 0 for name in SPLIT_NAMES}

    for index, (group_id, group_rows) in enumerate(randomized_groups):
        if index < len(SPLIT_NAMES):
            split_name = SPLIT_NAMES[index]
        else:
            total = len(rows)

            def projected_cost(name: str) -> float:
                cost = 0.0
                for candidate in SPLIT_NAMES:
                    projected = counts[candidate] + (
                        len(group_rows) if candidate == name else 0
                    )
                    cost += (projected / total - targets[candidate]) ** 2
                return cost

            split_name = min(SPLIT_NAMES, key=projected_cost)
        assigned[split_name].extend(
            row["sample_id"].strip() for row in group_rows
        )
        assigned_groups[split_name].append(group_id)
        counts[split_name] += len(group_rows)

    summaries = {
        split_name: {
            "n_images": len(assigned[split_name]),
            "n_defect_instances": sum(
                labels[sample_id][0] for sample_id in assigned[split_name]
            ),
            "n_normal_images": sum(
                labels[sample_id][1] == "normal"
                for sample_id in assigned[split_name]
            ),
            "groups": assigned_groups[split_name],
        }
        for split_name in SPLIT_NAMES
    }
    held_out = summaries["held_out"]
    meets_minimums = (
        held_out["n_defect_instances"] >= heldout_defect_min
        and held_out["n_normal_images"] >= heldout_normal_min
    )
    return {
        "seed": seed,
        "splits": assigned,
        "summary": summaries,
        "held_out_targets": {
            "defect_instances": heldout_defect_min,
            "normal_images": heldout_normal_min,
            "met": meets_minimums,
        },
    }


def save_splits(result: dict[str, Any], splits_dir: str | Path) -> None:
    output_dir = Path(splits_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = [
        output_dir / f"{split_name}_ids.json" for split_name in SPLIT_NAMES
    ]
    existing = [path for path in output_paths if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing split files: "
            + ", ".join(str(path) for path in existing)
        )
    for split_name, path in zip(SPLIT_NAMES, output_paths):
        path.write_text(
            json.dumps(result["splits"][split_name], indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create deterministic, board/session-grouped dataset splits."
    )
    parser.add_argument(
        "--manifest",
        default="datasets/labels/dataset_manifest.csv",
        help="Path to the complete dataset manifest.",
    )
    parser.add_argument(
        "--splits-dir",
        default="datasets/labels/splits",
        help="Directory for new split ID files; existing files are never replaced.",
    )
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    try:
        result = create_splits(args.manifest, seed=args.seed)
        save_splits(result, args.splits_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Could not create dataset splits: {error}\n")

    for split_name, summary in result["summary"].items():
        print(
            f"{split_name}: {summary['n_images']} images, "
            f"{summary['n_defect_instances']} defect instances, "
            f"{summary['n_normal_images']} normal images"
        )
    if not result["held_out_targets"]["met"]:
        print(
            "Held-out minimums not met: "
            f"need {result['held_out_targets']['defect_instances']} defect "
            "instances and "
            f"{result['held_out_targets']['normal_images']} normal images."
        )


if __name__ == "__main__":
    main()
