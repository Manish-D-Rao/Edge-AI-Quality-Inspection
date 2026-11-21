# MVP Held-Out Evaluation

## Verdict: Not evaluable

The 70% defect-instance recall gate has **not** been run or met. No held-out
score is available, and no detector is frozen. The current workspace has no
valid verified real-PCB held-out dataset.

## Evidence

- `datasets/labels/dataset_manifest.csv` is an inventory manifest, not a
  complete paired-sample manifest. It lacks sample IDs, reference/test paths,
  annotation paths, and normal/defect class labels.
- Its real-image rows are marked unlabeled/pending. The provenance and
  annotation identity for existing real-image JSON files have not been
  verified against the image content.
- Existing split IDs overlap/duplicate `reference`, and
  `held_out_ids.json` is empty. The evaluation runner rejects the manifest
  rather than emitting zero-valued metrics.
- The available generated pair contains two known artificial edits but no
  normal-only sample. Its results are documented separately in
  [phase-02-detector-selection.md](./phase-02-detector-selection.md) and do
  not count as held-out PCB validation.

## Held-out evaluation record

- Valid real held-out sample IDs: **0** (the current held-out ID file is empty).
- Verified labeled real defect-instance denominator: **unavailable**; the
  existing real rows are pending/unlabeled.
- Eligible normal-image denominator: **0 verified images**.
- Held-out run: **not performed**. Matched count, recall, precision, false
  candidates per normal image, and latency are therefore **not available**,
  not zero.
- Detector/configuration frozen for real held-out evaluation: **none**.

## Metric definition for a future valid holdout

- A defect instance is matched once to at most one candidate using IoU >= 0.3.
- Recall = matched labeled defect instances / all labeled defect instances.
- Precision = matched candidates / all candidate boxes.
- False-candidate budget: owner-approved mean <=5 false candidate boxes per
  fully labeled normal image, for manual review only.
- Record split membership, numerator/denominator, detector/configuration,
  per-image and aggregate metrics, and measured processing times in the
  evaluation output before making a target claim.

## Gate

Do not state “at least 70% recall met” until a frozen detector has been run
once on a complete, verified, board/session-independent real held-out split,
and the approved normal-image false-candidate budget is met. Required
prerequisites remain dataset provenance, human-reviewed annotations, and
valid grouped splits.
