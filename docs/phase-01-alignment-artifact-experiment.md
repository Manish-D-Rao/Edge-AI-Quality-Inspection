# Phase 01: Alignment Artifact Experiment

## Purpose and method

This diagnostic isolates preprocessing effects for the real PCB image pair; it
does not change the production inspection baseline. All comparisons use the same
reference image (4605 × 3454 pixels), threshold 25, minimum contour area 80,
baseline preprocessing, 3 × 3 rectangular opening, and two closing iterations.
Coordinates and bounding boxes are in the reference image's coordinate system.

Three test-image paths were compared:

- **A — Original resize:** original test resized to reference dimensions with
  `INTER_AREA`, matching the baseline behavior.
- **B — Saved aligned JPEG:** existing saved alignment output, with the saved
  test-to-reference homography diagnostics.
- **C — In-memory warp:** original test warped with that same homography using
  `INTER_LINEAR`, constant-zero border fill, and reference output dimensions.

For B and C, a source-support mask was made by warping an all-255 source mask
with the same transform, interpolation, and border mode. Only output pixels
whose support remained 255 are considered valid source content. The
support-filtered candidate count applies that mask to the post-morphology binary
mask before contour extraction; the unfiltered count is also retained to show
the effect of the invalid border.

## Measured results

| Path | Candidates (full / support-filtered) | Foreground pixels (% full image) | 8-connected components (full mask) | Candidate contour area, median / p95 / max (px²) | Boxes touching invalid support |
|---|---:|---:|---:|---:|---:|
| A — Original resize | 1,192 / 1,192 | 2,294,432 (14.4252%) | 5,129 | 221 / 2,545.1 / 746,311 | 0 |
| B — Saved aligned JPEG | 1,111 / 1,109 | 1,853,887 (11.6555%) | 5,687 | 201 / 3,079.5 / 1,220,780 | 2 |
| C — In-memory warp | 1,125 / 1,123 | 1,854,516 (11.6595%) | 5,666 | 201 / 3,053.4 / 1,194,725 | 2 |

The B/C valid-source support covers **99.7937%** of the output. In B, 27,155
foreground pixels lie in the invalid border (82.7594% of that border); in C,
27,163 lie there (82.7837%). Each path has one candidate contour entirely in
the invalid-border-only mask. These pixels are therefore not valid inspection
evidence. Applying the support mask reduces the candidate count by two for each
aligned path. It does not explain the much larger candidate totals.

The median connected-component pixel area is 30 px² for all three paths. The
95th percentile is 667.6 px² for A, 532 px² for B, and 533.5 px² for C. B and C
have more full-mask components than A despite less total foreground. Candidate
contours are not equivalent to connected components: contours are separately
filtered at area 80, and their area distributions have long tails. In
particular, each path still has over 20 candidate contours larger than 10,000
px².

### JPEG versus in-memory warp

The B and C binary masks differ at 26,203 pixels (0.1647% of the full image).
Of these, 26,161 are inside valid source support and 42 are outside it; 12,787
pixels are foreground only in B and 13,416 only in C. The candidate count is
1,111 for B versus 1,125 for C. Thus JPEG encoding changes a small fraction of
threshold decisions but changes enough local connectivity to alter the
candidate count by 14. This comparison isolates encoding for the aligned path;
the A-to-C comparison also changes the geometric transform and resampling
method.

## Timing

The saved alignment diagnostics report **577.95 ms** for alignment. Diagnostic
processing times were 1,222.34 ms (A), 1,373.70 ms (B), and 919.55 ms (C),
measured separately from alignment. These diagnostic timings include
connected-component labeling and detailed area/statistics calculations; they
are not directly comparable to production detector latency. Including the
reported alignment time gives 1,222.34 ms for A, 1,951.65 ms for B, and
1,497.50 ms for C for this diagnostic run.

## Observations and limitations

- The invalid black border contributes a high density of thresholded foreground
  pixels within its small support area, but support filtering removes only two
  candidate boxes. It is a real artifact, not the primary cause of the
  remaining candidate volume.
- JPEG versus in-memory warp yields close overall foreground percentages, yet
  differs at 26,161 valid-source pixels and by 14 candidates. Encoding can
  therefore affect threshold connectivity on this pair.
- A has fewer connected components but more foreground pixels than B/C.
  Candidate count alone does not describe localization quality.
- The original resize versus warped paths differ in both alignment and
  interpolation, so this experiment cannot attribute their entire difference
  to a single cause.
- This is one image pair without verified board-revision identity or defect
  ground truth. The measurements do not establish improved defect accuracy,
  identify candidates as defects, or demonstrate industrial performance.

## Recommended next change

In a separately evaluated change, pass the valid-source support mask alongside
an aligned image and exclude unsupported pixels before candidate extraction.
Measure the effect with the existing evaluator and preserve the unmasked
comparison. Since this experiment removes only two candidates, investigate the
remaining localization behavior separately; do not treat support masking or a
lower candidate count as evidence of better accuracy.

## Artifacts

The reproducible diagnostic outputs are under
[`outputs/alignment_artifact_diagnostic/support_aware/`](../outputs/alignment_artifact_diagnostic/support_aware/).
The summary and per-path JSON files retain the complete measurements and
candidate regions. The initial diagnostic outputs remain under
[`outputs/alignment_artifact_diagnostic/`](../outputs/alignment_artifact_diagnostic/).
