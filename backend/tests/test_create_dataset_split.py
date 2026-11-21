from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.create_dataset_split import create_splits, save_splits


FIELDS = [
    "sample_id",
    "reference_path",
    "test_path",
    "annotation_path",
    "sample_class",
    "label_status",
    "board_id",
    "capture_session",
]


def _sample(root: Path, sample_id: str, sample_class: str) -> dict[str, str]:
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    test_path = root / f"{sample_id}.png"
    assert cv2.imwrite(str(test_path), image)
    annotation_path = root / f"{sample_id}.json"
    annotations = []
    if sample_class == "defect":
        annotations.append(
            {
                "label": "defect",
                "x": 2,
                "y": 2,
                "width": 5,
                "height": 5,
                "area": 25,
                "status": "verified",
                "image_id": sample_id,
                "annotator_id": "test",
                "creation_timestamp": "2025-01-15T10:30:45Z",
            }
        )
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    return {
        "sample_id": sample_id,
        "reference_path": str(test_path),
        "test_path": str(test_path),
        "annotation_path": str(annotation_path),
        "sample_class": sample_class,
        "label_status": "complete",
        "board_id": sample_id,
        "capture_session": "session-1",
    }


def _manifest(root: Path, rows: list[dict[str, str]]) -> Path:
    path = root / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_splits_are_deterministic_and_groups_do_not_leak(tmp_path: Path) -> None:
    rows = [
        _sample(tmp_path, f"sample-{index}", "defect" if index % 2 else "normal")
        for index in range(9)
    ]
    manifest = _manifest(tmp_path, rows)

    first = create_splits(manifest, seed=7)
    second = create_splits(manifest, seed=7)
    assert first["splits"] == second["splits"]
    assert set(first["splits"]) == {"train", "validation", "held_out"}
    all_ids = [
        sample_id
        for sample_ids in first["splits"].values()
        for sample_id in sample_ids
    ]
    assert len(all_ids) == len(set(all_ids)) == len(rows)
    memberships = {
        sample_id: split_name
        for split_name, sample_ids in first["splits"].items()
        for sample_id in sample_ids
    }
    group_memberships: dict[str, set[str]] = {}
    for row in rows:
        group_memberships.setdefault(row["board_id"], set()).add(
            memberships[row["sample_id"]]
        )
    assert all(len(splits) == 1 for splits in group_memberships.values())
    assert first["held_out_targets"]["met"] is False


def test_unknown_board_and_session_metadata_fails_closed(tmp_path: Path) -> None:
    row = _sample(tmp_path, "sample-1", "normal")
    row["board_id"] = "unknown"
    row["capture_session"] = "unknown"
    manifest = _manifest(tmp_path, [row])
    with pytest.raises(ValueError, match="board_id or capture_session"):
        create_splits(manifest)


def test_split_writer_refuses_to_overwrite_existing_files(tmp_path: Path) -> None:
    result = {
        "splits": {
            "train": ["a"],
            "validation": ["b"],
            "held_out": ["c"],
        }
    }
    output = tmp_path / "splits"
    save_splits(result, output)
    original = (output / "train_ids.json").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        save_splits(result, output)
    assert (output / "train_ids.json").read_text(encoding="utf-8") == original
