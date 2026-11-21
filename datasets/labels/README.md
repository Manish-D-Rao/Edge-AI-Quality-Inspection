# Annotation JSON Format — Edge Vision-Language PCB Inspection

## Overview

This document describes the JSON annotation format used to label PCB inspection data. The format is keyed by image/sample ID and stores one or more annotated regions per image. Each region has a label (normal, defect, uncertain), bounding-box coordinates, and free-form status tags. The schema is enforced by the backend service (backend/app/services/annotation_schema.py).

This format is used by the annotation workflow in docs/annotation-guidelines.md, the inter-annotator reconciliation process, the dataset split generator (backend/scripts/create_dataset_split.py), and the evaluation metrics (backend/app/services/detection_metrics.py).

The examples in this document explain the schema only; they are not evidence
that a region was verified on the real PCB images. Do not use an annotation for
accuracy evaluation until its image pair, source, and label status are recorded
in the manifest and the annotations have been reviewed.

## Dataset Manifest

The evaluator and split generator require one row per reference/test sample
pair in `dataset_manifest.csv`, with these columns:

| Column | Meaning |
|---|---|
| `sample_id` | Unique identifier shared by the split file and annotation JSON. |
| `reference_path` | Path to the normal/reference image. |
| `test_path` | Path to the inspected image. |
| `annotation_path` | JSON annotation file for the test sample. |
| `sample_class` | `normal` when the fully reviewed image has no defects; otherwise `defect`. |
| `label_status` | Must be `complete` before the sample can be evaluated or split. |
| `board_id` | Board identity used to group related revisions and prevent leakage. |
| `capture_session` | Fallback grouping key when board identity is unavailable. |

Source/license, board revision, camera, lighting, and provenance fields should
also be recorded when available. Relative image and annotation paths are
resolved from the repository root for manifests under `datasets/labels/`.
Annotation coordinates use the reference-image pixel frame because candidate
boxes are reported in that frame. A completed normal sample may have an empty
annotation list; a completed defect sample must have at least one `defect`
region. The evaluator ignores `uncertain` regions rather than treating them as
positive or negative ground truth.

The current inventory manifest predates this paired-sample contract and is not
evaluation-ready. Do not fill missing identities, paths, or labels by guessing.

## Top-Level Structure

The annotation dataset is a directory (datasets/labels/) containing one JSON file per image (or per sample ID). The filename (without .json extension) is the image_id used in each region's metadata.

### Directory Layout

```
datasets/labels/
├── README.md              # This file
├── real_pcb_v1_ref.json
├── real_pcb_v1_test.json
├── synthetic_demo_ref.json
└── ...
```

Each file is a JSON array of region objects. An image with no annotated regions has an empty array [].

## Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | `str` | Yes | Must be one of: `"normal"`, `"defect"`, `"uncertain"` |
| `x` | `int` | Yes | Top-left x coordinate in reference-image pixel coordinates. Must be ≥ 0. |
| `y` | `int` | Yes | Top-left y coordinate in reference-image pixel coordinates. Must be ≥ 0. |
| `width` | `int` | Yes | Box width in pixels. Must be ≥ 1. |
| `height` | `int` | Yes | Box height in pixels. Must be ≥ 1. |
| `area` | `int` | Yes | Computed as `width × height`. Must equal `width * height`. |
| `status` | `str` | Yes | Free-form descriptive tag. Common values: `"scratch"`, `"solder_bridge"`, `"crack"`, `"void"`, `"discoloration"`, `"occluded"`, `"partial"`, `"fully_occluded"`, `"borderline_defect"`, `"possible_shadow"`, `"edge_case"` |
| `image_id` | `str` | Yes | Must match the filename (without extension) of the JSON file it resides in. |
| `annotator_id` | `str` | Yes | Identifier of the annotator. Recommended `"annotator_01"`, `"annotator_02"`, etc. |
| `creation_timestamp` | `str` | Yes | ISO 8601 datetime string (e.g., `"2025-01-15T10:30:45Z"`). Must be valid ISO 8601. |

## Validation Rules

The backend schema validator (backend/app/services/annotation_schema.py) enforces these rules. Any region failing these rules will cause the entire annotation file to be rejected during import:

1. **Label validity**: `label` must be exactly `"normal"`, `"defect"`, or `"uncertain"`.
2. **Coordinate bounds**: `x ≥ 0`, `y ≥ 0`, `width ≥ 1`, `height ≥ 1`.
3. **Image boundary**: `x + width` must not exceed the reference image width, and `y + height` must not exceed the reference image height. Exact dimensions known at validation time (passed as context, not stored in JSON).
4. **Area consistency**: `area` must equal `width × height` exactly.
5. **Status presence**: `status` must be a non-empty string.
6. **Image ID match**: `image_id` must equal the filename (without `.json`) of the containing file.
7. **Annotator ID non-empty**: `annotator_id` must be a non-empty string.
8. **Timestamp format**: `creation_timestamp` must parse as valid ISO 8601.

## Inter-Annotator Reconciliation

When two annotators label the same image, the raw annotations are preserved with an optional `reconciliation` field if needed:

```json
{
  "label": "defect",
  "x": 367,
  "y": 67,
  "width": 57,
  "height": 21,
  "area": 1197,
  "status": "scratch",
  "image_id": "real_pcb_v1_ref",
  "annotator_id": "annotator_01",
  "creation_timestamp": "2025-01-15T10:30:45Z",
  "reconciliation": {
    "matched_iou": 0.82,
    "partner_annotator": "annotator_02",
    "final_label": "defect",
    "resolution": "both_defect"
  }
}
```

The `reconciliation` field is optional and not required for basic import. It is added during the reconciliation step and should not be present in raw single-annotator submissions.

## What NOT to Include

Do not include regions that violate the guidelines:

- Boxes with `width` or `height` ≤ 0.
- Regions extending beyond image boundaries.
- `label` values other than `"normal"`, `"defect"`, `"uncertain"`.
- Missing required fields.
- `status` values that are empty strings or purely whitespace.

Such regions should be fixed per the quality checks in docs/annotation-guidelines.md §8 before saving.

## Example Files

### Example: Annotated Defect Regions

`datasets/labels/real_pcb_v1_ref.json`:

```json
[
  {
    "label": "defect",
    "x": 367,
    "y": 67,
    "width": 57,
    "height": 21,
    "area": 1197,
    "status": "scratch",
    "image_id": "real_pcb_v1_ref",
    "annotator_id": "annotator_01",
    "creation_timestamp": "2025-01-15T10:30:45Z"
  },
  {
    "label": "defect",
    "x": 511,
    "y": 141,
    "width": 19,
    "height": 19,
    "area": 361,
    "status": "circular_mark",
    "image_id": "real_pcb_v1_ref",
    "annotator_id": "annotator_01",
    "creation_timestamp": "2025-01-15T10:35:12Z"
  },
  {
    "label": "normal",
    "x": 100,
    "y": 100,
    "width": 50,
    "height": 30,
    "area": 1500,
    "status": "pad",
    "image_id": "real_pcb_v1_ref",
    "annotator_id": "annotator_01",
    "creation_timestamp": "2025-01-15T11:02:44Z"
  }
]
```

### Example: Image with No Defects

`datasets/labels/normal_board_ref.json`:

```json
[]
```
## Contact & Questions

If any case not covered by this format arises, the team lead or the annotating team should document the exception and add it to the guidelines (docs/annotation-guidelines.md) or this README for future consistency.

**File:** `datasets/labels/README.md`