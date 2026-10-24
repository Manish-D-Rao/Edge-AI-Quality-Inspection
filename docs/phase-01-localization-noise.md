# Phase 01C.3 — Candidate Localization Noise

## Scope and method

This diagnostic analyzes the real PCB pair using the original test image and
the baseline's `INTER_AREA` resize path. The detector was not changed.
`inspection_evaluation.inspect_pair` was used for the exact baseline stages at
threshold **25** and minimum contour area **80 px²**. It returns the same
external contours, contour areas, bounding boxes, difference image, mask, and
annotation used by the evaluator.

The input reference is 4605 × 3454 pixels. Candidate coordinates are in this
reference-image coordinate system. The run produced **1,192** candidates.
Measured detector processing time was **549.30 ms** for this run; it is a
single-run measurement and not a stable performance benchmark.

### Explicit size and shape bins

- **Contour area:** small ≤500 px²; medium >500 and ≤10,000 px²; large
  >10,000 px².
- **Bounding-box area:** small ≤500 px²; medium >500 and ≤10,000 px²; large
  >10,000 px². Bounding-box area is width × height and is distinct from contour
  area.
- **Aspect ratio:** portrait <0.5; balanced 0.5–2.0 inclusive; landscape >2.0.
  The ratio is bounding-box width / height.

## Candidate size and shape

| Measure | Small / portrait | Medium / balanced | Large / landscape |
|---|---:|---:|---:|
| Contour-area bins | 903 (≤500 px²) | 266 (501–10,000 px²) | 23 (>10,000 px²) |
| Bounding-box-area bins | 500 (≤500 px²) | 632 (501–10,000 px²) | 60 (>10,000 px²) |
| Aspect-ratio bins | 225 (<0.5) | 827 (0.5–2.0) | 140 (>2.0) |

These are independent distributions; a candidate is not necessarily in the
same size bin for contour area and box area. Contour area has a median of
**221 px²**, p90 **1,212.6 px²**, and maximum **746,311 px²**. Bounding-box
area has a median of **616 px²**, p90 **4,174.9 px²**, and maximum
**5,283,012 px²**. This discrepancy confirms that at least some candidates
have boxes that cover much more area than their contour interior. The
candidate-area overlay uses orange for small, red for medium, and magenta for
large contour-area bins.

## Nearby and overlapping bounding boxes

Bounding boxes were considered neighbors when their maximum horizontal or
vertical edge-to-edge gap was no greater than the specified pixel distance.
Connected groups use transitive connectivity: if A is near B and B is near C,
all three belong to one group even if A is not near C. These are box geometry
statistics, not proof that candidates arise from one underlying change.

| Neighbor definition | Nearby pairs | Positive-area box-overlap pairs | Multi-box groups | Candidates in multi-box groups | Largest group |
|---|---:|---:|---:|---:|---:|
| Gap ≤10 px | 1,780 | 1,124 | 55 | 1,087 | 825 |
| Gap ≤25 px | 2,503 | 1,124 | 39 | 1,146 | 890 |

At a 10 px maximum gap, pair separation has median 0 px and p90 8 px. At 25 px,
the median is 2 px and p90 21 px. Thus many candidate boxes overlap or occur
close together. This is consistent with multiple contours around the same
dense local image structure, but it does not by itself establish fragmentation
of one physical defect or even one continuous difference region. The very large
transitive groups are particularly sensitive to a few broad boxes; the largest
candidate box spans 5,283,012 px². Contours are extracted with
`RETR_EXTERNAL`, so any box intersection is a bounding-box overlap, not a
claim that contour pixels overlap.

The quantitative test supports grouping boxes for review, but **cannot
reliably determine how many candidates are duplicate/fragmented detections of
the same image-difference region**. That requires examining the underlying
connected mask geometry and/or assigning region-level associations rather
than interpreting transitive box groups as ground truth.

## Spatial distribution and visual review

Candidate centers were counted in a 4-row × 4-column grid over the full
reference image. Counts by row, left to right:

| Image row | Column 1 | Column 2 | Column 3 | Column 4 |
|---|---:|---:|---:|---:|
| Top | 69 | 97 | 77 | 76 |
| Upper middle | 73 | 89 | 57 | 64 |
| Lower middle | 31 | 103 | 84 | 56 |
| Bottom | 41 | 95 | 112 | 68 |

Every cell contains candidates (31–112 each). The distribution is widespread,
not confined to the outer frame or one board region. Only **1** candidate box
intersects the outer 2% of the image width or height. That frame-relative
statistic is not a physical PCB-edge detector: the board boundary lies inside
the photograph, and its visible edge is not necessarily represented by a box
touching the image border.

Visual review of the generated candidate-area overlay, density overlay,
difference image, and binary mask shows detections throughout the board. Many
small boxes occur around component bodies and leads/pins, while broader boxes
cover some dense component areas and silkscreen/text. Fine traces and board
edges also appear among the highlighted image structure. The density overlay
shows hotspots in detailed regions, including component clusters, but no
exclusive concentration around a single feature class. These are visual
descriptions of image differences only. At full-board scale, individual box
association with a specific lead, trace, or text glyph is not reliable enough
to classify every candidate.

## Interpretation and limitations

The observed candidate volume is consistent with the detector responding to
raster differences across detailed PCB structure: component edges and leads,
text/silkscreen, traces, and some board-edge structure are all present in the
difference and mask outputs. The area distribution is strongly skewed toward
small contours (903/1,192 are at most 500 px²), while many boxes are close to
or overlap other boxes. Together, these measurements explain why the contour
filter emits many localized image-difference regions.

This experiment does not establish whether any region is a defect, a harmless
capture difference, a board revision change, or a measurement artifact. There
are no verified defect labels or capture records for this real pair. Spatial
proximity and visual overlap cannot establish defect accuracy, and fewer boxes
would not by itself demonstrate a better detector.

## Diagnostic outputs

The generated files are under
[`outputs/localization_noise_diagnostic/`](../outputs/localization_noise_diagnostic/):

- `result.json` — complete per-candidate values, bin definitions, spatial
  counts, and pair/group statistics.
- `annotated.jpg` — baseline candidate annotations.
- `candidate_area_overlay.jpg` — candidate boxes colored by contour-area bin.
- `candidate_density_overlay.jpg` — smoothed candidate-center density overlay.
- `difference.jpg` and `mask.jpg` — baseline difference and post-morphology
  binary mask.
