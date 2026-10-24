
# Phase 01 — Inspection Baseline Results

## Environment
- OS: Ubuntu 26.04.1 LTS
- Python version: 3.14.4 (`backend/venv`)
- OpenCV version: 5.0.0
- CPU: Intel(R) Core(TM) i5-6300U CPU @ 2.40GHz
- RAM: 7,491,240 kB total (about 7.15 GiB)

## Test images
- Reference image: `datasets/samples/reference.jpg` — readable, 4605 × 3454 pixels.
- Test image: `datasets/samples/test.jpg` — readable, 2390 × 1792 pixels.
- Image dimensions: The inspection resizes the test image to the reference size (4605 × 3454) before comparing.
- Region coordinates use that resized-reference coordinate system; ranges below are the candidates' bounding-box top-left coordinates.

The baseline converts images to grayscale, applies CLAHE and a 5 × 5 Gaussian blur, then thresholds their absolute pixel difference. It applies a 3 × 3 morphological opening and a closing (two iterations), and retains external contours whose contour area meets `min-area`. The reported timer starts before image loading and stops before output files are written.

## Experiment 1
- Threshold: 25
- Minimum area: 80
- Candidate regions: 1192 (x: 154–4460, y: 115–3366)
- Processing time (ms): 2471.33 (from the freshly generated `outputs/result.json`)
- Did the artificial differences get highlighted?: Not evaluated for this real-image pair; it has no known artificial changes or ground-truth annotations. The annotated output does visibly mark widespread differences across the board, not just isolated regions.

## Experiment 2
- Threshold: 15
- Minimum area: 40
- Candidate regions: 1077 (x: 150–4549, y: 114–3406)
- Processing time (ms): 2442.86 (from the freshly generated `outputs/sensitive/result.json`)
- Did the artificial differences get highlighted?: Not evaluated for this real-image pair; the output marks widespread differences.

## Experiment 3
- Threshold: 40
- Minimum area: 120
- Candidate regions: 1051 (x: 187–4486, y: 155–3325)
- Processing time (ms): 2053.28 (from the freshly generated `outputs/conservative/result.json`)
- Did the artificial differences get highlighted?: Not evaluated for this real-image pair; the output marks widespread differences.

## Synthetic demo
- Images: `datasets/samples/exampleLocal/reference.jpg` and `datasets/samples/exampleLocal/test.jpg`, both readable at 640 × 480 pixels.
- Configuration: Threshold 25; minimum area 80 (from `outputs/synthetic/result.json`).
- Candidate regions: 2.
- Processing time (ms): 74.4 (from `outputs/synthetic/result.json`).
- Did the artificial differences get highlighted?: Yes. In `outputs/synthetic/annotated.jpg`, both intended edits in the test image are boxed: the scratch-like line at x=367, y=66 (57 × 21 bounding box; area 454) and the small circular mark at x=511, y=141 (19 × 19 bounding box; area 274). These match the two artificial edits in the demo generator. No additional candidate boxes are visible in this synthetic run.

## Step 1B — Image alignment

The separate diagnostic alignment uses ORB features, Hamming-distance descriptor matching with a 0.75 ratio test, and a RANSAC homography. Feature extraction is capped at 4,000 keypoints on images whose longest side is at most 1,600 pixels. Alignment requires at least 12 ratio-tested matches, 10 RANSAC inliers, a 0.25 inlier ratio, and 1% inlier convex-hull coverage in each image; estimated transforms are checked for finite values and plausible projected image bounds before warping. The test image is warped into the reference image's original width, height, and coordinate system. Alignment timing includes feature extraction, matching, transform checks, and warping; it is separate from inspection timing.

- Real pair: Alignment succeeded. 1,173 good matches; 1,116 inliers (0.9514 ratio); inlier coverage was 0.7939 for the reference and 0.7952 for the test. The latest run took 577.95 ms; output is 4605 × 3454.
- Synthetic pair: Alignment succeeded. 685 good matches; 683 inliers (0.9971 ratio); inlier coverage was 0.8051 for each image. The latest run took 33.04 ms; output is 640 × 480. The estimated transform was effectively identity, as expected from the matching-size synthetic pair.
- Outputs: `outputs/alignment/real_pcb/` and `outputs/alignment/synthetic/` contain aligned test images and diagnostic JSON.
- These feature-match diagnostics do not establish that the real images depict the same board revision or that alignment improves candidate detection. No before/after inspection comparison was run.

## Step 1C — Alignment effect on baseline candidate regions

The separate evaluator compares the original test image and the saved Step 1B aligned test image against the same reference. It uses the existing baseline `preprocess` function and repeats its absolute difference, binary threshold, 3 × 3 opening, two-iteration closing, external contour extraction, and minimum contour-area filtering without changing the baseline. All saved regions and bounding-box ranges use reference-image coordinates. `processing_time_ms` covers preprocessing through contour filtering but excludes input/output file I/O; alignment time is reported separately.

| Dataset | Threshold / min area | Original candidates | Aligned candidates | Delta (aligned − original) | Original / aligned processing (ms) | Alignment (ms) | Aligned total (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Real PCB pair | 25 / 80 | 1192 | 1111 | -81 | 481.92 / 417.76 | 577.95 | 995.71 |
| Real PCB pair | 15 / 40 | 1077 | 1579 | +502 | 438.65 / 413.65 | 577.95 | 991.60 |
| Real PCB pair | 40 / 120 | 1051 | 926 | -125 | 438.77 / 385.34 | 577.95 | 963.29 |
| Synthetic pair | 25 / 80 | 2 | 2 | 0 | 5.57 / 8.29 | 33.04 | 41.33 |
| Synthetic pair | 15 / 40 | 2 | 2 | 0 | 6.44 / 6.40 | 33.04 | 39.44 |
| Synthetic pair | 40 / 120 | 2 | 2 | 0 | 4.81 / 6.50 | 33.04 | 39.54 |

- Synthetic edit coverage: Edit boxes were derived by rasterizing the generator's actual line and circle drawing calls. The line box is `(x=367, y=67, width=57, height=19)` and the circle box is `(x=511, y=141, width=19, height=19)`. For every threshold/min-area configuration, both boxes had 100% pixel coverage by the union of candidate boxes, and there were 0 additional candidate boxes, for both original and aligned comparisons.
- Candidate bounding-box top-left coordinate ranges are stored per run in each `result.json`. Across the real configurations, the original ranges span x=154–4549/y=114–3406 and aligned ranges span x=0–4535/y=0–3452. Synthetic original and aligned ranges match: at threshold 15, x=366–510/y=66–140; at threshold 25, x=367–511/y=66–141; at threshold 40, x=367–511/y=67–141.
- On the real pair, alignment changed candidate counts in both directions depending on configuration. These are measured count changes only; there are no labels to determine whether candidates correspond to defects or whether fewer candidates are better. Some aligned coordinate ranges reach the image boundary; border effects from warping were not isolated.
- The saved aligned JPEG is used for this comparison, so compression/resampling effects are included. Synthetic coverage is limited to these two known edits and does not establish general detection performance. Alignment cost is material relative to one inspection pass; the aligned-total column is the aligned comparison time plus the separately measured Step 1B alignment time. Timings are single-run measurements, not a benchmark.
- Outputs are under `outputs/alignment_evaluation/`, separated by dataset, configuration, and original/aligned input; `summary.json` records the six comparisons.

## Limitations
- Sensitivity to image alignment: The baseline inspection path does not geometrically register images. For the real-image pair, the test is smaller and is resized to the reference dimensions; its baseline output shows candidates spread across the image, but alignment effects were not isolated from other causes. Step 1B adds a separate alignment diagnostic, but it has not been integrated into inspection or evaluated for candidate-count changes. The synthetic pair has matching dimensions and does not evaluate alignment sensitivity.
- Sensitivity to lighting: Not evaluated with controlled lighting changes. Direct grayscale pixel differencing can respond to illumination and exposure variation even after CLAHE.
- Missed differences: No missed edits were apparent in the synthetic demo: both known artificial changes produced candidates. Missed changes on the real-image pair are not evaluated because it has no labeled changes. By design, subtle changes can be removed by the threshold, morphological opening, or minimum contour-area filter.
- False positives: The real-image annotated output contains many candidates across ordinary-looking board features and near board edges. These are suspicious image differences, not confirmed false positives or defects; ground truth is unavailable. The synthetic run showed no additional candidate boxes, but this does not establish general false-positive performance. The broad distribution on the real-image pair means the current output does not localize a small set of actionable regions reliably.

## Next steps
- Test real PCB images.
- Improve candidate-region localization.
- Integrate with the FastAPI backend.
