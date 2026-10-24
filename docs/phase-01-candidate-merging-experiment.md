# Phase 01C.4 — Candidate Merging Experiment

## Scope and method

This is a separate post-processing experiment. It runs the existing baseline at
threshold **25** and minimum contour area **80**, preserving the original
candidate boxes and writing each merged strategy to its own result and
visualization directory. The detector, alignment logic, thresholds, and input
images were not changed. The real pair uses original `INTER_AREA` resizing;
the synthetic pair is also included.

All groups use transitive connected-component semantics: if A is related to B
and B to C, all three are merged even if A and C are not directly related.
Each merged result is the union bounding rectangle of all source boxes in the
group. This is intentionally a simple geometry baseline; it can bridge unrelated
regions through chains or broad boxes.

The compared strategies are:

1. **Original:** unchanged, unmerged candidate boxes.
2. **Overlap:** merge boxes only when their intersection has positive area.
   Edge-touching alone does not count as overlap.
3. **Nearby 10 px:** merge when the maximum horizontal or vertical
   edge-to-edge gap is ≤10 pixels. Overlapping and edge-touching boxes are
   included.
4. **Nearby relative:** merge when that maximum x/y gap is ≤0.25% of the
   image diagonal. This is **14.391 px** for the 4605 × 3454 real image and
   **2 px** for the 640 × 480 synthetic image.

Times below distinguish the baseline inspection pass from each merge pass.
They are single-run measurements; merge timing covers only grouping and union
box creation and excludes JSON/image file writes.

## Results

### Real PCB pair

The baseline produced **1,192** unmerged candidates; that baseline pass took
**723.74 ms** in this run. There are no verified defect labels for this pair,
so merging quality and defect accuracy cannot be established.

| Strategy | Result boxes | Reduction from original | Merge time (ms) | Merged width median / max (px) | Merged height median / max (px) | Largest group |
|---|---:|---:|---:|---:|---:|---:|
| Original | 1,192 | — | 0 | 25 / 2,308 | 28 / 2,289 | 1 |
| Overlap | 340 | 71.5% | 51.10 | 26 / 3,502 | 30 / 2,892 | 658 |
| Nearby 10 px | 160 | 86.6% | 57.72 | 30 / 4,263 | 34 / 3,183 | 825 |
| Nearby relative (14.391 px) | 131 | 89.0% | 56.80 | 34 / 4,290 | 36 / 3,183 | 863 |

Group sizes show why the count reductions should not be read as improved
localization. For overlap merging, 285 groups are singletons and there is one
group containing **658** original boxes. The 10 px strategy has 105 singleton
groups and one group of **825** boxes. The relative strategy has 78 singleton
groups and one group of **863** boxes. These broad connected groups create
merged rectangles spanning large parts of the image. The overlays make this
over-merging visible: several magenta boxes cover broad PCB areas rather than
isolated local structures.

### Synthetic pair

The baseline produced **2** candidates and took **3.98 ms** in this run. Each
strategy retained two singleton boxes; merge times were 0.0499 ms (overlap),
0.0438 ms (10 px), and 0.0541 ms (relative 2 px). Box widths remained 19–57 px
and heights 19–21 px.

Both known generator edits remain fully covered by the union of candidate boxes
under all four paths (original and three strategies): the scratch-like line
and circular mark each have **100% bounding-box coverage**, with **0 additional
candidate boxes**. The relative distance is only 2 px at this image size, and
the two edit boxes are far apart; no merging is expected. This check is limited
to those two synthetic edits.

## Interpretation and limitations

Merging substantially lowers the number of reported boxes on the real pair,
but does so by aggregating many nearby or overlapping boxes into large
transitive groups. In particular, the very large groups and merged box
dimensions indicate that these thresholds can over-merge. The synthetic pair
does not discriminate among strategies because it has only two separated
candidate boxes. No conclusion about defect accuracy or real-pair merging
quality is possible without verified labels and evaluation criteria. Fewer
boxes alone do not mean better detection.

The rules use bounding-box geometry, not mask connectivity or PCB component
semantics. A box can overlap another even when their underlying difference
pixels are unrelated, and chains of locally close boxes can produce a very
large merged rectangle. Relative thresholds scale with image dimensions but
are not normalized to component size or board spacing.

## Artifacts

All outputs are under
[`outputs/candidate_merging_experiment/`](../outputs/candidate_merging_experiment/).
Each dataset contains `original/` and one folder per merge strategy, each with
an `annotated.jpg` and a `result.json`. Original candidate lists remain in the
original JSON; merged JSON includes group sizes and source candidate indexes.
`summary.json` combines measurements for both datasets. Red boxes show original
candidates; magenta boxes show merged boxes, with the member count labeled.
