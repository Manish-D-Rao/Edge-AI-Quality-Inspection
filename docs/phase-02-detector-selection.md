# Phase 02 — Detector Comparison

## Status and scope

This is a **synthetic smoke comparison**, not the planned labeled real-PCB
development/validation experiment. The only verified pair available for this
comparison is the 640 × 480 generated demo pair. Its two known edits come
directly from `backend/create_demo_images.py`: the drawn line and circle.
Their enclosing reference-coordinate boxes are specified in the comparison
runner, not added as production annotations.

The run is saved under
`outputs/model_selection/synthetic-phase02-final/`. The command was run from
`backend/`:

```bash
./venv/bin/python run_synthetic_detector_comparison.py \
  --output-dir ../outputs/model_selection/synthetic-phase02-final
```

It refuses to overwrite an existing output directory. Machine-readable
measurements and candidate boxes are in
[`comparison.json`](../outputs/model_selection/synthetic-phase02-final/comparison.json),
with detector-specific results and visual artifacts in the `baseline/` and
`structural/` subdirectories.

## Results on this pair only

Both detectors used threshold **25**, minimum contour area **80**, and IoU
matching threshold **0.3**.

| Detector | Candidates | Matched edits | Unmatched candidates | Missed edits | Synthetic-edit recall | Synthetic-edit precision | F1 | Measured time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OpenCV baseline | 2 | 2/2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 60.58 ms |
| Structural (gradient + registered difference) | 2 | 2/2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 54.31 ms |

These are measurements from one run and timings are machine/load dependent.
The single evaluated class, `synthetic_edit`, had 2/2 matched instances for
each detector. It is not a real PCB defect class.

### Candidate regions

- Baseline: `(511, 141, 19 × 19)` and `(367, 66, 57 × 21)`.
- Structural: `(509, 139, 23 × 23)` and `(365, 65, 61 × 23)`.
- Structural alignment succeeded with 683 inliers from 685 ratio-tested
  matches (0.9971 inlier ratio); valid-source coverage was 100%.

The bounding boxes cover the two known artificial edits in this generated
image. This says nothing about whether similarly shaped real PCB changes are
defects.

### Visual evidence

Red boxes mark detector candidates. The known edit extents are not separately
overlaid in these saved images. Visual inspection confirms the two candidate
boxes overlap the generated line and circle in the test image.

![Baseline synthetic detector candidates](../outputs/model_selection/synthetic-phase02-final/baseline/annotated.jpg)

![Structural synthetic detector candidates](../outputs/model_selection/synthetic-phase02-final/structural/annotated.jpg)

The baseline [difference](../outputs/model_selection/synthetic-phase02-final/baseline/difference.jpg)
and [mask](../outputs/model_selection/synthetic-phase02-final/baseline/mask.jpg),
and the structural [combined difference](../outputs/model_selection/synthetic-phase02-final/structural/combined_difference.jpg),
[intensity difference](../outputs/model_selection/synthetic-phase02-final/structural/intensity_difference.jpg),
[gradient difference](../outputs/model_selection/synthetic-phase02-final/structural/gradient_difference.jpg),
and [mask](../outputs/model_selection/synthetic-phase02-final/structural/mask.jpg)
are saved with the run.

## False-candidate budget and selection

The owner-approved provisional budget is a mean of at most **5 false candidate
boxes per normal image**, for a manually reviewed prototype only. It is
**not evaluable here**: the test image contains the two generated edits, and
there is no normal-only image in this pair. The two unmatched-candidate count
on this edited pair is zero, but it is not a substitute for false candidates
measured on normal samples.

**No detector is frozen or selected.** The baseline remains the API's
provisional default. One generated image pair cannot serve as separate
development and validation data, test generalization, or establish performance
on real PCB images.

## Failure cases and limitations

- No registration failure occurred in this run. The structural detector's
  behavior on validly labeled, varied real captures remains unknown.
- No normal-only sample, lighting variation, camera variation, board revision,
  or labeled real defect was evaluated.
- The synthetic truth is known from the local generator, not independently
  annotated PCB imagery.
- The 1.00 recall/precision values above must not be reported as PCB accuracy
  or as evidence that the 70% real-image recall gate has passed.

## Required next data

To complete T028 and T030 with meaningful development/validation evidence,
provide complete real reference/test pairs, verified labels and provenance,
and non-overlapping board/session-grouped splits. The current manifest and
split files do not meet that requirement. Do not repair them by guessing
identities or defect labels.
