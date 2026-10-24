# Phase 01C.5 — Noise-Reduction Preprocessing Experiment

## Scope and method

This is a separate experiment; it does not modify the inspection baseline,
alignment code, or existing outputs. The real PCB and synthetic image pairs
were evaluated at the same fixed threshold (**25**) and minimum contour area
(**80 px²**). A differently sized test image is resized to reference dimensions
using the existing `INTER_AREA` behavior. Each variant applies the same
preprocessing choice to reference and test before absolute difference.

All variants use grayscale conversion and CLAHE (`clipLimit=2.0`,
`tileGridSize=(8,8)`). The choices are:

1. **Baseline:** existing `preprocess` function (5×5 Gaussian blur), then the
   existing 3×3 rectangular opening and 3×3 rectangular closing with two
   iterations.
2. **Gaussian 7×7:** replace only the final 5×5 Gaussian blur with 7×7;
   baseline morphology is unchanged.
3. **Median 5×5:** replace the final 5×5 Gaussian blur with a 5×5 median
   filter; baseline morphology is unchanged.
4. **Morphology variation:** keep baseline preprocessing and use 5×5
   rectangular opening once, followed by 3×3 rectangular closing once. This
   changes both opening size and closing iteration count as one explicitly
   defined morphology variant.

Foreground percentage and connected-component count are measured on the
post-morphology binary mask. The candidate count is the number of external
contours with contour area ≥80 px². Processing time includes both
preprocessings, difference/threshold, morphology, connected-component
analysis, and contour filtering; it excludes input/output file operations.
Timings are single-run observations, not benchmarks.

## Results

### Real PCB pair

| Variant | Candidates | Foreground mask | Connected components | Processing time (ms) |
|---|---:|---:|---:|---:|
| Baseline | 1,192 | 2,294,432 px (14.4252%) | 5,129 | 602.11 |
| Gaussian 7×7 | 1,308 | 2,093,032 px (13.1590%) | 4,979 | 568.24 |
| Median 5×5 | 1,292 | 2,111,048 px (13.2723%) | 5,281 | 481.58 |
| Morphology variation | 2,186 | 956,051 px (6.0108%) | 6,538 | 437.06 |

The larger Gaussian and median filters each lowered foreground pixels and
connected components somewhat, but both **increased** the contour-filtered
candidate count over baseline. The morphology variant cut foreground mask
coverage substantially, but produced more connected components and **994 more
candidates** than baseline. Fewer foreground pixels therefore did not imply
less contour fragmentation in this experiment.

### Synthetic pair

| Variant | Candidates | Foreground mask | Connected components | Processing time (ms) | Scratch-like line coverage | Circular mark coverage |
|---|---:|---:|---:|---:|---|---|
| Baseline | 2 | 816 px (0.2656%) | 2 | 8.08 | 100% | 100% |
| Gaussian 7×7 | 2 | 902 px (0.2936%) | 2 | 6.41 | 100% | 100% |
| Median 5×5 | 2 | 630 px (0.2051%) | 2 | 8.87 | 96.49% | 80.06% |
| Morphology variation | 2 | 810 px (0.2637%) | 2 | 4.78 | 100% | 100% |

Coverage is the fraction of each known artificial edit's full generator-derived
bounding box covered by the union of candidate boxes. Median filtering still
produces two candidates, but neither candidate fully covers its respective
edit box under the strict 100% criterion. The other variants fully cover both
synthetic edit boxes and yield no additional candidate boxes.

## Interpretation and limitations

The filters are not interchangeable noise-reduction improvements. The 7×7
Gaussian and 5×5 median filters reduce real-pair foreground pixels but slightly
increase candidate counts. The tested morphology change reduces the foreground
fraction considerably while increasing both connected-component and candidate
counts, consistent with more fragmented post-morphology regions under this
configuration. On the small synthetic pair, median filtering reduces mask
area but leaves incomplete candidate-box coverage of the known edits.

The real PCB pair has no verified defect labels, capture records, or region
ground truth. It is therefore not possible to determine whether any candidate
is a defect, whether a candidate-count change improves localization, or whether
the removed foreground pixels were noise or meaningful image differences.
These results are comparisons of image-derived statistics only; fewer
candidates do not imply better accuracy or performance.

Only one filter size per family and one morphology configuration were tested.
These measurements do not identify optimal parameters or establish behavior
across boards, capture conditions, or defect types. Synthetic coverage applies
only to the two known artificial edits in this generated image pair.

## Artifacts

Generated outputs are under
[`outputs/preprocessing_experiment/`](../outputs/preprocessing_experiment/),
with one directory per dataset and variant. Each variant directory contains
`result.json`, `annotated.jpg`, `difference.png`, and `mask.png`.
`summary.json` contains the measured comparison values; per-variant JSON
includes the full candidate boxes and, for synthetic data, edit coverage.
