# Phase 01 — Real-Pair Candidate Localization Diagnosis

## Scope and evidence

This is a read-only diagnosis of the saved original/aligned comparison outputs.
The baseline implementation and its outputs were not changed. Visual review
covered original and aligned annotations and masks for all three real-pair
configurations. Difference images were reviewed for both modes; these are
produced before the configuration-dependent threshold and area filtering.
Quantitative mask/component statistics below were recomputed in memory using
the saved test images, saved aligned JPEG, and the existing baseline
preprocessing/morphology stages. No output images were regenerated.

## Observations confirmed by the images and measurements

- Candidates occur across the board, not just at its outer boundary. In the
  threshold-25 4 × 4 grid of candidate-box centers, every grid cell contains
  candidates (original cells: 31–112 each; aligned: 22–120 each). The
  annotations visibly cluster around component bodies and leads, silkscreen
  and chip text, fine traces, and dense component regions. Board-edge
  differences are also visible.
- The original and aligned difference images contain widespread fine detail.
  Their corresponding masks are dense around high-detail edges throughout the
  image. Alignment changes these patterns but does not localize differences
  to a small set of regions.
- At threshold 25 / minimum area 80, the post-morphology masks contain
  2,294,432 foreground pixels (14.43%) before alignment and 1,853,887
  (11.66%) after. Yet 5,129 versus 5,687 connected components are present,
  respectively; the contour-filtered candidate counts are 1,192 versus
  1,111.
- At threshold 15 / minimum area 40, foreground pixels decrease from
  4,060,567 (25.53%) to 3,588,066 (22.56%) after alignment, while connected
  components increase from 5,862 to 7,043 and candidates from 1,077 to 1,579.
  This is consistent with the aligned mask splitting into more islands even
  though fewer pixels remain foreground.
- At threshold 25, median contour area is 221 px² original and 201 px² aligned;
  903/1,192 original candidates and 850/1,111 aligned candidates have contour
  area at most 500 px². Both have a long tail of large candidates: 23 original
  and 22 aligned contours exceed 10,000 px². The largest aligned candidate's
  bounding box spans the full 4605 × 3454 frame, while its contour area is
  23,307 px². This confirms a border-connected candidate can have a huge box
  without comparable filled contour area.
- At threshold 15 / minimum area 40, 857/1,077 original candidates and
  1,301/1,579 aligned candidates have contour area at most 500 px². The median
  areas are 127 px² and 113 px². The candidate increase is predominantly in
  small regions, not an increase in mask foreground.
- These configurations change threshold and minimum area together. Therefore,
  count differences between configurations cannot be attributed to threshold
  alone.

## Alignment and implementation review

- The saved real-pair diagnostics report success: 1,173 ratio-tested matches,
  1,116 RANSAC inliers (0.9514 ratio), with inlier coverage of 0.7939 and
  0.7952. This supports a geometrically coherent feature match, but does not
  establish that the images are the same board revision or capture.
- The estimated homography is dominated by scale (approximately 1.925 × in
  x and 1.927 × in y), close to the direct resize factors from the test
  (2390 × 1792) to the reference (4605 × 3454). It contains little translation.
  Thus the saved alignment appears mainly to reproduce the size normalization
  already performed by the baseline, rather than correcting a large positional
  shift.
- The alignment code uses `warpPerspective` with linear interpolation and
  constant-black border fill. The original comparison resizes with
  `INTER_AREA`; the aligned comparison reads a separately warped and
  JPEG-encoded image. These different resampling and encoding paths are
  confirmed confounds. The aligned annotations show a frame-spanning candidate,
  and the aligned masks have border activity absent or much smaller in the
  original masks. Interpolation, fill-border, and JPEG effects are plausible
  contributors; their individual contributions were not isolated.
- Both comparison paths resize/warp to the reference dimensions. Candidate
  coordinates and the reported grid use reference-image pixel coordinates;
  there is no coordinate-system mix-up in these stored comparisons.
- The baseline applies grayscale conversion, CLAHE, a 5 × 5 Gaussian blur,
  absolute pixel difference, strict binary thresholding, 3 × 3 morphological
  opening, two iterations of closing, and external-contour extraction. Its
  `min_area` is contour area in pixels, not connected-component pixel count.
  At reference resolution, an 80 px² cutoff retains many tiny edge/text/trace
  mismatches. CLAHE and blur do not make the method invariant to exposure,
  focus, compression, or differing image detail. Closing can join nearby
  thresholded detail, while contour filtering treats each remaining external
  contour as a candidate.

## Likely causes versus unresolved hypotheses

**Strongly supported:** Difference signal is distributed over fine board
structure and candidate boxes are distributed across the full image. The large
candidate population is therefore not explained mainly by a single board
boundary artifact. The per-pixel method flags ordinary visual structure
wherever the two raster images differ: component edges/leads, silkscreen text,
and traces are visibly prominent.

**Plausible, not isolated:** The pair's capture/source differences (including
resolution and potentially focus, exposure, perspective, compression, or
revision) create residual high-frequency differences after registration.
Interpolation and JPEG encoding in the aligned path can change local
differences and connectivity; the border fill can produce frame-edge
responses. There are no capture records or ground-truth labels to decide which
factor dominates or whether any candidate represents a defect.

## Smallest useful next experiment

Repeat one real-pair configuration (threshold 25 / minimum area 80) in memory
using the uncompressed `warpPerspective` array and an explicit valid-source
support mask. Compare it against the saved aligned-JPEG and original-resize
paths, reporting border-only and board-interior mask/component counts plus
candidate-area distributions. This isolates warp fill and JPEG/resampling
effects without changing the baseline detector. If widespread interior
differences remain, the next evidence should be a controlled repeat capture of
the same board with stable illumination/focus and known registration
fiducials; only then can capture mismatch be separated from actual board
changes.
