from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.dataset_evaluation import (
    evaluate_split,
    group_by_split,
    load_manifest,
    run_dataset_evaluation,
)

MANIFEST_FIELDS = [
    "sample_id",
    "reference_path",
    "test_path",
    "annotation_path",
    "sample_class",
    "label_status",
    "board_id",
    "capture_session",
]


def _write_sample(
    root: Path,
    sample_id: str,
    sample_class: str,
    *,
    with_edit: bool = False,
) -> dict[str, str]:
    reference = np.zeros((96, 96, 3), dtype=np.uint8)
    test = reference.copy()
    annotations = []
    if with_edit:
        test[30:52, 25:48] = 255
        annotations.append(
            {
                "label": "defect",
                "x": 25,
                "y": 30,
                "width": 23,
                "height": 22,
                "area": 506,
                "status": "synthetic_edit",
                "image_id": sample_id,
                "annotator_id": "test",
                "creation_timestamp": "2025-01-15T10:30:45Z",
            }
        )
    reference_path = root / f"{sample_id}_reference.png"
    test_path = root / f"{sample_id}_test.png"
    annotation_path = root / f"{sample_id}.json"
    assert cv2.imwrite(str(reference_path), reference)
    assert cv2.imwrite(str(test_path), test)
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    return {
        "sample_id": sample_id,
        "reference_path": str(reference_path),
        "test_path": str(test_path),
        "annotation_path": str(annotation_path),
        "sample_class": sample_class,
        "label_status": "complete",
        "board_id": f"board-{sample_id}",
        "capture_session": f"session-{sample_id}",
    }


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_load_manifest_validates_fields_and_unique_ids(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_write_sample(tmp_path, "normal-1", "normal")],
    )
    assert len(load_manifest(manifest)) == 1

    duplicate = _write_manifest(
        tmp_path / "duplicate.csv",
        [
            _write_sample(tmp_path, "same", "normal"),
            _write_sample(tmp_path, "same", "normal"),
        ],
    )
    with pytest.raises(ValueError, match="Duplicate sample_id"):
        load_manifest(duplicate)


def test_group_by_split_validates_membership_and_disjointness(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_write_sample(tmp_path, "normal-1", "normal")],
    )
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    (splits_dir / "train_ids.json").write_text('["normal-1"]', encoding="utf-8")
    assert group_by_split(manifest, splits_dir) == {"train": ["normal-1"]}

    (splits_dir / "held_out_ids.json").write_text(
        '["unknown"]', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="missing from manifest"):
        group_by_split(manifest, splits_dir)


def test_run_dataset_evaluation_uses_pairs_labels_and_writes_aggregate(
    tmp_path: Path,
) -> None:
    rows = [
        _write_sample(tmp_path, "normal-1", "normal"),
        _write_sample(tmp_path, "defect-1", "defect", with_edit=True),
    ]
    manifest = _write_manifest(tmp_path / "manifest.csv", rows)
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    (splits_dir / "validation_ids.json").write_text(
        '["normal-1", "defect-1"]', encoding="utf-8"
    )
    output_dir = tmp_path / "evaluation"

    result = run_dataset_evaluation(
        manifest,
        splits_dir,
        config={"threshold": 25, "min_area": 40},
        output_dir=output_dir,
    )["validation"]
    aggregate = result["aggregate"]
    assert aggregate["n_evaluated"] == 2
    assert aggregate["n_ground_truth_total"] == 1
    assert aggregate["n_matched_total"] == 1
    assert aggregate["recall"] == 1
    assert aggregate["n_normal_images"] == 1
    assert aggregate["false_candidates_per_normal_image"] == 0
    assert aggregate["mean_processing_time_ms"] >= 0
    assert result["detector"] == "baseline"
    assert result["config"] == {"threshold": 25, "min_area": 40}
    assert (output_dir / "validation_evaluation.json").is_file()
    with pytest.raises(FileExistsError):
        run_dataset_evaluation(manifest, splits_dir, output_dir=output_dir)


def test_normal_only_images_contribute_false_candidates(tmp_path: Path) -> None:
    row = _write_sample(tmp_path, "normal-1", "normal")
    manifest = _write_manifest(tmp_path / "manifest.csv", [row])

    def false_alarm(reference: Path, test: Path, config: dict) -> dict:
        del reference, test, config
        return {
            "regions": [{"x": 1, "y": 1, "width": 5, "height": 5}],
            "processing_time_ms": 4.5,
        }

    result = evaluate_split("test", ["normal-1"], manifest, false_alarm, {})
    assert result["aggregate"]["recall"] is None
    assert result["aggregate"]["false_candidates_per_normal_image"] == 1
    assert result["aggregate"]["n_false_positives_total"] == 1


def test_unlabeled_sample_and_detector_failure_are_not_zero_filled(
    tmp_path: Path,
) -> None:
    row = _write_sample(tmp_path, "normal-1", "normal")
    row["label_status"] = "pending"
    manifest = _write_manifest(tmp_path / "manifest.csv", [row])
    with pytest.raises(ValueError, match="not completely labeled"):
        evaluate_split("test", ["normal-1"], manifest, lambda *_: {}, {})

    row["label_status"] = "complete"
    _write_manifest(manifest, [row])

    def detector_failure(
        reference: Path, test: Path, config: dict
    ) -> dict:
        del reference, test, config
        raise RuntimeError("expected test failure")

    with pytest.raises(RuntimeError, match="expected test failure"):
        evaluate_split("test", ["normal-1"], manifest, detector_failure, {})


def test_annotation_bounds_are_checked_against_reference_image(tmp_path: Path) -> None:
    row = _write_sample(tmp_path, "defect-1", "defect", with_edit=True)
    annotations_path = Path(row["annotation_path"])
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    annotations[0]["x"] = 90
    annotations[0]["width"] = 20
    annotations[0]["area"] = 440
    annotations_path.write_text(json.dumps(annotations), encoding="utf-8")
    manifest = _write_manifest(tmp_path / "manifest.csv", [row])
    with pytest.raises(ValueError, match="extends beyond image dimensions"):
        evaluate_split("test", ["defect-1"], manifest, lambda *_: {}, {})


def test_annotation_coordinates_use_reference_frame(tmp_path: Path) -> None:
    row = _write_sample(tmp_path, "defect-1", "defect", with_edit=True)
    small_test = np.zeros((48, 48, 3), dtype=np.uint8)
    assert cv2.imwrite(row["test_path"], small_test)
    manifest = _write_manifest(tmp_path / "manifest.csv", [row])

    def no_candidates(reference: Path, test: Path, config: dict) -> dict:
        del reference, test, config
        return {"regions": [], "processing_time_ms": 1.0}

    result = evaluate_split("test", ["defect-1"], manifest, no_candidates, {})
    assert result["aggregate"]["n_ground_truth_total"] == 1
    assert result["aggregate"]["recall"] == 0


def test_annotation_filename_must_match_sample_id(tmp_path: Path) -> None:
    row = _write_sample(tmp_path, "normal-1", "normal")
    renamed_path = tmp_path / "other-name.json"
    Path(row["annotation_path"]).rename(renamed_path)
    row["annotation_path"] = str(renamed_path)
    manifest = _write_manifest(tmp_path / "manifest.csv", [row])
    with pytest.raises(ValueError, match="does not match sample_id"):
        evaluate_split("test", ["normal-1"], manifest, lambda *_: {}, {})
