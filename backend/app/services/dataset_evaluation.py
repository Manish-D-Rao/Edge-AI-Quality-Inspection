from __future__ import annotations

import csv
import json
import math
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
from pydantic import ValidationError

from app.services.annotation_schema import AnnotationRegion
from app.services.detection_metrics import compute_metrics
from app.services.detector_protocol import DetectorConfig, DetectorOutput
from app.services.inspection_baseline import inspect_images
from app.services.structural_anomaly_detector import StructuralAnomalyDetector


SPLIT_DIR = "datasets/labels/splits"
MANIFEST_FIELDS = {
    "sample_id",
    "reference_path",
    "test_path",
    "annotation_path",
    "sample_class",
    "label_status",
}
DetectorFunction = Callable[[Path, Path, dict[str, Any]], dict[str, Any]]


def load_manifest(manifest_path: str | Path) -> list[dict[str, str]]:
    path = Path(manifest_path)
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"Manifest has no header: {path}")
        missing_fields = MANIFEST_FIELDS - set(reader.fieldnames)
        if missing_fields:
            raise ValueError(
                "Manifest is missing required fields: "
                + ", ".join(sorted(missing_fields))
            )
        rows = list(reader)

    sample_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        for field, value in row.items():
            if value is not None:
                row[field] = value.strip()
        sample_id = (row.get("sample_id") or "").strip()
        if not sample_id:
            raise ValueError(f"Manifest row {row_number} has an empty sample_id.")
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate sample_id in manifest: {sample_id}")
        sample_ids.add(sample_id)
        for field in MANIFEST_FIELDS - {"sample_id"}:
            if not (row.get(field) or "").strip():
                raise ValueError(
                    f"Manifest row {row_number} has an empty {field}."
                )
    return rows


def group_by_split(
    manifest_path: str | Path, splits_dir: str | Path
) -> dict[str, list[str]]:
    rows = load_manifest(manifest_path)
    known_ids = {row["sample_id"].strip() for row in rows}
    split_path = Path(splits_dir)
    split_files = sorted(split_path.glob("*_ids.json"))
    if not split_files:
        raise ValueError(f"No *_ids.json split files found in {split_path}.")

    splits: dict[str, list[str]] = {}
    seen_ids: set[str] = set()
    for path in split_files:
        split_name = path.name.removesuffix("_ids.json")
        try:
            image_ids = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read split file {path}: {error}") from error
        if not isinstance(image_ids, list) or not all(
            isinstance(image_id, str) and image_id for image_id in image_ids
        ):
            raise ValueError(f"Split file must contain a list of IDs: {path}")
        if len(set(image_ids)) != len(image_ids):
            raise ValueError(f"Split file contains duplicate IDs: {path}")
        unknown = set(image_ids) - known_ids
        if unknown:
            raise ValueError(
                f"Split {split_name} references IDs missing from manifest: "
                + ", ".join(sorted(unknown))
            )
        overlap = seen_ids.intersection(image_ids)
        if overlap:
            raise ValueError(
                "Sample IDs appear in more than one split: "
                + ", ".join(sorted(overlap))
            )
        seen_ids.update(image_ids)
        splits[split_name] = image_ids
    missing_ids = known_ids - seen_ids
    if missing_ids:
        raise ValueError(
            "Manifest samples are not assigned to a split: "
            + ", ".join(sorted(missing_ids))
        )
    return splits


def _dataset_root(manifest_path: Path) -> Path:
    resolved = manifest_path.resolve()
    if len(resolved.parents) > 2 and resolved.parent.name == "labels":
        return resolved.parents[2]
    return resolved.parent


def _resolve_path(raw_path: str, manifest_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    root_candidate = _dataset_root(manifest_path) / path
    if root_candidate.exists():
        return root_candidate
    return manifest_path.resolve().parent / path


def _load_annotations(
    annotation_path: Path,
    sample_id: str,
    image_width: int,
    image_height: int,
    sample_class: str,
) -> list[dict[str, int | str]]:
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
        raise ValueError(f"Annotation file must contain a JSON list: {annotation_path}")

    defects: list[dict[str, int | str]] = []
    for index, raw_region in enumerate(annotations):
        if not isinstance(raw_region, dict):
            raise ValueError(
                f"Annotation {index} in {annotation_path} must be an object."
            )
        try:
            region = AnnotationRegion.model_validate(raw_region)
        except ValidationError as error:
            raise ValueError(
                f"Invalid annotation {index} in {annotation_path}: {error}"
            ) from error
        if region.image_id != sample_id:
            raise ValueError(
                f"Annotation image_id {region.image_id!r} does not match "
                f"sample_id {sample_id!r} in {annotation_path}."
            )
        if (
            region.x + region.width > image_width
            or region.y + region.height > image_height
        ):
            raise ValueError(
                f"Annotation {index} extends beyond image dimensions "
                f"{image_width}x{image_height} in {annotation_path}."
            )
        if region.label == "defect":
            defects.append(
                {
                    "x": region.x,
                    "y": region.y,
                    "width": region.width,
                    "height": region.height,
                    "area": region.area,
                    "label": "defect",
                    "status": region.status,
                }
            )

    if sample_class == "normal" and defects:
        raise ValueError(
            f"Normal sample {sample_id!r} has defect annotations."
        )
    if sample_class == "defect" and not defects:
        raise ValueError(
            f"Defect sample {sample_id!r} has no defect annotations."
        )
    return defects


def _baseline_detector(
    reference_path: Path, test_path: Path, config: dict[str, Any]
) -> dict[str, Any]:
    threshold = config["threshold"]
    min_area = config["min_area"]
    with tempfile.TemporaryDirectory(prefix="pcb-baseline-eval-") as output_dir:
        return inspect_images(
            str(reference_path),
            str(test_path),
            output_dir=output_dir,
            min_area=min_area,
            threshold=threshold,
        )


def _structural_detector(
    reference_path: Path, test_path: Path, config: dict[str, Any]
) -> dict[str, Any]:
    detector = StructuralAnomalyDetector.from_config(config)
    reference = cv2.imread(str(reference_path), cv2.IMREAD_UNCHANGED)
    test = cv2.imread(str(test_path), cv2.IMREAD_UNCHANGED)
    if reference is None or test is None:
        raise ValueError(
            f"Could not load detector inputs {reference_path} and {test_path}."
        )
    result: DetectorOutput = detector.detect(reference, test)
    if not result.success:
        raise RuntimeError(result.failure_reason or "Structural detector failed.")
    return {
        "candidate_count": len(result.candidates),
        "regions": result.candidates,
        "processing_time_ms": result.processing_time_ms,
    }


def _aggregate(
    split_name: str, per_image: list[dict[str, Any]], iou_threshold: float
) -> dict[str, Any]:
    total_candidates = sum(item["candidate_count"] for item in per_image)
    total_ground_truth = sum(item["ground_truth_count"] for item in per_image)
    total_matched = sum(item["metrics"]["n_matched"] for item in per_image)
    total_false_positives = sum(
        item["metrics"]["n_false_positives"] for item in per_image
    )
    total_missed = sum(item["metrics"]["n_missed"] for item in per_image)
    normal_images = [item for item in per_image if item["sample_class"] == "normal"]
    defect_images = [item for item in per_image if item["sample_class"] == "defect"]
    normal_false_positives = sum(item["candidate_count"] for item in normal_images)
    recall = total_matched / total_ground_truth if total_ground_truth else None
    precision = total_matched / total_candidates if total_candidates else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if recall is not None and precision + recall
        else 0.0
    )
    return {
        "split": split_name,
        "n_images": len(per_image),
        "n_evaluated": len(per_image),
        "n_defect_images": sum(
            item["sample_class"] == "defect" for item in per_image
        ),
        "n_normal_images": len(normal_images),
        "n_matched_total": total_matched,
        "n_false_positives_total": total_false_positives,
        "n_missed_total": total_missed,
        "n_candidates_total": total_candidates,
        "n_ground_truth_total": total_ground_truth,
        "per_class_metrics": {
            "defect": {
                "n_images": len(defect_images),
                "n_ground_truth": sum(
                    item["ground_truth_count"] for item in defect_images
                ),
                "n_matched": sum(
                    item["metrics"]["n_matched"] for item in defect_images
                ),
                "recall": (
                    sum(item["metrics"]["n_matched"] for item in defect_images)
                    / sum(item["ground_truth_count"] for item in defect_images)
                    if sum(item["ground_truth_count"] for item in defect_images)
                    else None
                ),
                "false_candidates": sum(
                    item["metrics"]["n_false_positives"] for item in defect_images
                ),
            },
            "normal": {
                "n_images": len(normal_images),
                "false_candidates": normal_false_positives,
                "false_candidates_per_image": (
                    normal_false_positives / len(normal_images)
                    if normal_images
                    else None
                ),
            },
        },
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "normal_image_false_candidates": normal_false_positives,
        "false_candidates_per_normal_image": (
            normal_false_positives / len(normal_images) if normal_images else None
        ),
        "mean_processing_time_ms": (
            sum(item["processing_time_ms"] for item in per_image) / len(per_image)
            if per_image
            else None
        ),
        "iou_threshold": iou_threshold,
    }


def evaluate_split(
    split_name: str,
    image_ids: list[str],
    manifest_path: str | Path,
    detector_func: DetectorFunction,
    config: dict[str, Any],
    iou_threshold: float = 0.3,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    rows = load_manifest(manifest_file)
    rows_by_id = {row["sample_id"].strip(): row for row in rows}
    per_image: list[dict[str, Any]] = []

    for sample_id in image_ids:
        row = rows_by_id.get(sample_id)
        if row is None:
            raise ValueError(f"Split sample {sample_id!r} is missing from manifest.")
        if row["label_status"].strip().lower() != "complete":
            raise ValueError(
                f"Sample {sample_id!r} is not completely labeled "
                f"(label_status={row['label_status']!r})."
            )
        sample_class = row["sample_class"].strip().lower()
        if sample_class not in {"normal", "defect"}:
            raise ValueError(
                f"Sample {sample_id!r} has unsupported sample_class "
                f"{row['sample_class']!r}."
            )

        reference_path = _resolve_path(row["reference_path"], manifest_file)
        test_path = _resolve_path(row["test_path"], manifest_file)
        annotation_path = _resolve_path(row["annotation_path"], manifest_file)
        reference = cv2.imread(str(reference_path), cv2.IMREAD_UNCHANGED)
        test = cv2.imread(str(test_path), cv2.IMREAD_UNCHANGED)
        if reference is None:
            raise ValueError(f"Could not read reference image: {reference_path}")
        if test is None:
            raise ValueError(f"Could not read test image: {test_path}")
        ground_truth = _load_annotations(
            annotation_path,
            sample_id,
            reference.shape[1],
            reference.shape[0],
            sample_class,
        )
        detection = detector_func(reference_path, test_path, config)
        candidates = detection.get("regions")
        if not isinstance(candidates, list):
            raise ValueError(
                f"Detector {detection!r} did not return a regions list "
                f"for sample {sample_id!r}."
            )
        processing_time = detection.get("processing_time_ms")
        if (
            not isinstance(processing_time, (int, float))
            or isinstance(processing_time, bool)
            or not math.isfinite(processing_time)
            or processing_time < 0
        ):
            raise ValueError(
                f"Detector returned an invalid processing time for {sample_id!r}."
            )
        metrics = compute_metrics(candidates, ground_truth, iou_threshold)
        per_image.append(
            {
                "sample_id": sample_id,
                "sample_class": sample_class,
                "status": "ok",
                "candidate_count": len(candidates),
                "ground_truth_count": len(ground_truth),
                "metrics": metrics,
                "processing_time_ms": processing_time,
            }
        )

    return {
        "split": split_name,
        "results": per_image,
        "aggregate": _aggregate(split_name, per_image, iou_threshold),
    }


def run_dataset_evaluation(
    manifest_path: str | Path,
    splits_dir: str | Path = SPLIT_DIR,
    detector_name: str = "baseline",
    config: dict[str, Any] | None = None,
    output_dir: str | Path | None = None,
    split_name: str | None = None,
) -> dict[str, dict[str, Any]]:
    config = dict(config or {"threshold": 25, "min_area": 80})
    detector_functions: dict[str, DetectorFunction] = {
        "baseline": _baseline_detector,
        "structural": _structural_detector,
    }
    if detector_name not in detector_functions:
        raise ValueError(
            f"Unknown detector {detector_name!r}; choose baseline or structural."
        )
    if detector_name == "baseline":
        unsupported = set(config) - {"threshold", "min_area"}
        if unsupported:
            raise ValueError(
                "Unsupported baseline configuration fields: "
                + ", ".join(sorted(unsupported))
            )
        config.setdefault("threshold", 25)
        config.setdefault("min_area", 80)
        threshold = config["threshold"]
        min_area = config["min_area"]
        if (
            not isinstance(threshold, int)
            or isinstance(threshold, bool)
            or not 0 <= threshold <= 255
        ):
            raise ValueError("Baseline threshold must be an integer from 0 to 255.")
        if (
            not isinstance(min_area, int)
            or isinstance(min_area, bool)
            or min_area < 1
        ):
            raise ValueError("Baseline min_area must be a positive integer.")
    else:
        try:
            config = asdict(DetectorConfig(**config))
        except TypeError as error:
            raise ValueError(
                f"Invalid structural detector configuration: {error}"
            ) from error

    splits = group_by_split(manifest_path, splits_dir)
    if split_name is not None:
        if split_name not in splits:
            raise ValueError(
                f"Split {split_name!r} not found. Available: "
                + ", ".join(sorted(splits))
            )
        splits = {split_name: splits[split_name]}
    evaluated = {
        split_name: evaluate_split(
            split_name,
            image_ids,
            manifest_path,
            detector_functions[detector_name],
            config,
        )
        for split_name, image_ids in splits.items()
    }
    for result in evaluated.values():
        result["detector"] = detector_name
        result["config"] = config
        result["iou_threshold"] = 0.3
    if output_dir is not None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=False)
        for split_name, result in evaluated.items():
            path = output_path / f"{split_name}_evaluation.json"
            path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return evaluated
