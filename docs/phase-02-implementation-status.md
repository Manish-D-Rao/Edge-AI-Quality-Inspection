# Phase 02 Implementation Status

## Result

The evaluation and experimental detector code is implemented. No real PCB
accuracy result or 70% recall claim is available: the current dataset metadata,
annotations, and splits do not form a complete, verified paired benchmark.

## Implemented

- Candidate matching uses one-to-one maximum-cardinality matching at the
  explicit IoU threshold of 0.3. Duplicate candidate boxes cannot claim the
  same defect instance.
- Evaluation reports per-image and aggregate recall, precision, F1, unmatched
  candidate counts, defect/normal class metrics, normal-image false candidates
  per image, and measured processing time.
- The runner reads reference/test pairs and annotation paths from the manifest,
  validates labels and reference-frame coordinates, supports `baseline` and
  `structural` detectors, selects one split or all splits, and refuses to
  overwrite an existing output directory. Detector errors are reported rather
  than replaced with zero-valued results.
- The separate structural detector now uses both intensity and gradient
  differences, optional ORB/RANSAC registration, a valid-source mask, measured
  latency, and reference-frame candidate coordinates. It fails closed when
  valid registered support is below the configured minimum. The baseline
  detector was not changed.
- Split generation requires complete labels and a known board ID or capture
  session, assigns whole groups to deterministic splits, checks annotation
  bounds, reports held-out minimums, and will not replace existing split files.
- The manifest contract is documented in
  [datasets/labels/README.md](../datasets/labels/README.md).

## Verification

- Backend test suite (including Phase 03 API coverage): **83 passed, 4 subtests passed**.
- Synthetic-only baseline-versus-structural comparison: completed on the
  existing generated 640 × 480 pair; both detectors returned two candidates
  matching the two known artificial edits at IoU >= 0.3. See
  [phase-02-detector-selection.md](./phase-02-detector-selection.md) for
  measured metrics and visual artifacts. This does not evaluate real PCBs.
- Python compilation: passed.
- Pylance diagnostics on the changed Python modules: no diagnostics.
- `git diff --check`: passed.
- Running the evaluation CLI on the current manifest fails explicitly because
  it lacks `annotation_path`, `reference_path`, `sample_class`, `sample_id`,
  and `test_path`. Split creation likewise refuses the incomplete manifest;
  no new production split or evaluation output was written.

## Data blockers

The current `datasets/labels/dataset_manifest.csv` contains the older inventory
columns (`source`, `board_revision`, `capture_session`, `camera_lighting`,
`consent_license`, `image_path`, `label_status`, and `annotator_status`), not
the required paired-sample fields. The real-image rows are marked unlabeled
and pending. The existing split files contain duplicate/overlapping
`reference` IDs, and the held-out split is empty. Some annotation JSON files
also have an `image_id` that does not match the sample/file identity required
by the schema. These artifacts were preserved and were not treated as verified
ground truth.

The synthetic unit fixtures prove code behavior for controlled edits only.
They do not measure real PCB recall, precision, generalization, or industrial
performance. The owner approved an initial budget of a mean of at most 5 false
candidate boxes per normal image for a manually reviewed prototype. This is a
review-workload target, not an industrial threshold.

## Remaining work

1. Create manifest rows for complete reference/test pairs, with accurate source,
   board/session identity, license/provenance, `sample_class`, and
   `label_status=complete`.
2. Obtain human-reviewed defect annotations in reference-image coordinates and
   complete normal-image labels; reconcile independent annotations where
   required.
3. Generate non-overlapping board/session-grouped train, validation, and
   held-out splits. Confirm the held-out defect-instance and normal-image
   minimums before calling the 70% target evaluable.
4. Compare detectors on development/validation data against the approved
   false-candidate budget, freeze the selected configuration, then run
   held-out evaluation once.

See the task checkboxes and dependency order in
[mvp-implementation-plan.md](./mvp-implementation-plan.md). Phase 02 tasks
T019–T027 are implemented; T029 is complete as a report of available
synthetic-only evidence, and T032 is complete as a report that the held-out
gate is not evaluable. T028, T030, and T031 remain blocked until a valid
labeled real dataset and non-overlapping splits exist. The next phase's API
vertical slice is documented in [phase-03-api.md](./phase-03-api.md).
