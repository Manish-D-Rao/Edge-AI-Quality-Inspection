# Annotation Guidelines — Edge Vision-Language PCB Inspection

## Purpose

These guidelines define a consistent labeling schema for real PCB inspection data. They are used to create the annotated dataset, compute evaluation metrics (recall/precision), and train/calibrate any optional VLM explanations. Two annotators should be able to apply these rules independently and arrive at consistent results.

## 1. Label Taxonomy

Each annotated region (bounding box) receives exactly one of the following labels:

| Label | Meaning | When to Use |
|---|---|---|
| **normal** | No defect present. The image region represents typical board features (traces, pads, silkscreen, empty space). | • The region contains only expected PCB features.<br>• No visible anomaly or damage. |
| **defect** | A verifiable manufacturing or physical defect. | • Crack, scratch, cut, or gouge in copper or substrate.<br>• Missing material (hole, void, popcorn).<br>• Solder bridge, excess solder, or solder ball.<br>• Discoloration, staining, or burn mark that correlates with a known defect class.<br>• Any feature an experienced inspector would flag as suspicious. |
| **uncertain** | The region is ambiguous — it may or may not be a defect, or its classification is unclear without further review. | • Discoloration without clear morphology (could be lighting variation).<br>• Edge-of-field features where partial occlusion makes classification difficult.<br>• Features that could be either a scratch or a normal trace variant.<br>• Any region the annotator is not confident about after inspection. |

**Rule:** Every annotated region must receive exactly one label. Do not leave a region unlabeled.
## 2. Defect Instance Identity

- Each defect gets **one bounding box**. If multiple physical defects are extremely close (touching or overlapping within 2 pixels), merge them into a single box that encloses all visible damage.
- **Do not** create multiple boxes for the same physical defect unless there are clearly distinct damage regions that an inspector would evaluate separately.
- **Do** create separate boxes for distinct defect features even if they are on the same component (e.g., a scratch and a nearby pad discoloration that are clearly separate issues).

## 3. Bounding-Box Coordinates

- Format: `[x, y, width, height]` in **reference-image pixel coordinates**.
- `(x, y)` is the **top-left corner** of the box.
- Coordinates are **integers** (round if sub-pixel).
- The box must be **fully inside the image boundaries**: `0 ≤ x, 0 ≤ y`, `x + width ≤ image_width`, `y + height ≤ image_height`.
- **Tip:** When the test image is resized to match reference dimensions, the same coordinate system applies. Annotate on the reference image dimensions.

**Example:** A scratch running from pixel (367, 67) with length 57 and height 21 → `[367, 67, 57, 21]`.

## 4. Occlusion Handling

- If a defect is partially obscured by a component, solder mask, or silkscreen, **still draw a box around the visible portion**.
- In the `status` or label field, add a note if useful: `"occluded"` or `"partial"`.
- **Do not** skip the region entirely — the model must learn to handle partially visible defects.
- If the **entire** defect is occluded and cannot be seen, mark the region as `uncertain` and note `"fully_occluded"` in the metadata.
## 5. Ambiguous Case Procedure

When an annotator is unsure whether a region is `normal`, `defect`, or `uncertain`:

| Situation | Action |
|---|---|
| Looks like a scratch but is very faint | Mark as `uncertain`. Add comment `"borderline_defect"` in metadata. |
| Suspicious dark spot but could be a stain or shadow | Mark as `uncertain`. Add comment `"possible_shadow"` in metadata. |
| Clear manufacturing feature (e.g., pad, via, test point) | Mark as `normal`. |
| Known defect type (e.g., hairline crack) but only a few pixels visible | Mark as `defect` with smallest enclosing box. Add `"minimal_visibility"` in metadata. |
| Region contains both normal and defective features | Enclose both in **one** box and mark as `defect` (merge rule). Add comment `"mixed_region"` in metadata. |
| Grid alignment, fiducial marks, tooling holes | Mark as `normal` (these are intentional board features). |

**Golden Rule:** When in doubt, default to `uncertain`. It is better to have a few uncertain boxes than to mislabel a normal feature as a defect or miss a real defect.

## 6. Metadata Fields (per region)

Each annotated region must include these fields in the JSON annotation file:

| Field | Type | Description |
|---|---|---|
| `label` | `str` | One of: `"normal"`, `"defect"`, `"uncertain"` |
| `x` | `int` | Top-left x coordinate |
| `y` | `int` | Top-left y coordinate |
| `width` | `int` | Box width in pixels |
| `height` | `int` | Box height in pixels |
| `area` | `int` | `width × height` |
| `status` | `str` | Free-form descriptive tag(s), e.g., `"scratch"`, `"solder_bridge"`, `"occluded"`, `"partial"`, `"fully_occluded"`, `"borderline_defect"` |
| `image_id` | `str` | Identifier of the image/sample this annotation belongs to |
| `annotator_id` | `str` | Identifier of the person who created this annotation |
| `creation_timestamp` | `str` (ISO 8601) | When the annotation was created |

**Example JSON region entry:**

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
  "creation_timestamp": "2025-01-15T10:30:45Z"
}
```
## 7. Annotation Workflow

1. **Open** the image in the chosen viewer (e.g., ImageJ, LabelImg, or a custom web UI).
2. **Zoom** to inspect details. Verify you are working at 100% or a known magnification.
3. **Draw** a bounding box around the region of interest.
4. **Select** the label from the taxonomy (`normal`, `defect`, `uncertain`).
5. **Fill** in the `status` field with a descriptive tag.
6. **Verify** that the box coordinates are within image bounds.
7. **Save** the region. The system should auto-fill `image_id`, `annotator_id`, and `creation_timestamp`.
8. **Repeat** for all regions in the image.
9. **Review** your work before moving to the next image. If annotating with a partner, compare a random subset (10%) for consistency.

## 8. Quality Checks (Per-Image)

Before submitting an annotation file, verify:

- [ ] Every annotated region has a `label` from the taxonomy.
- [ ] No box has `width` or `height` ≤ 0.
- [ ] All boxes are fully inside the image dimensions.
- [ ] `status` field is present and uses reasonable free-form tags.
- [ ] `image_id` matches the source image filename (without extension).
- [ ] No duplicate boxes for the same defect (apply merge rule if overlapping > 50%).

If any check fails, fix the entry before saving.

## 9. Inter-Annotator Reconciliation

When two annotators label the same image:

1. **Compare** their region sets using IoU (Intersection over Union) ≥ 0.5 as the matching threshold.
2. **Resolved cases** (IoU ≥ 0.5, same image region):
   - If both label `defect` → keep as `defect`.
   - If both label `normal` → keep as `normal`.
   - If both label `uncertain` → keep as `uncertain`.
   - If labels differ → mark the region as `uncertain` in the final dataset and add a reconciliation note.
3. **Unmatched regions** (no IoU partner):
   - Keep both boxes in the dataset but flag the one that has no partner with `"solo_annotation"`.
   - Annotator who labeled it should add a `status` tag explaining why it is unique (e.g., `"edge_case"`, `"rare_defect_type"`).

All reconciled annotations go into the final `datasets/labels/` dataset. The reconciliation report is stored separately and not part of the labeled dataset itself.

## 10. What NOT to Annotate

Do **not** create boxes for:

- Intentional board features: fiducial marks, tooling holes, alignment markers.
- General PCB context: large areas of empty board, background, non-functional regions.
- Cosmetic variations that are not defects (discoloration from lighting, camera noise).
- Regions smaller than 5 pixels × 5 pixels (these are below the reliable detection threshold).

Tiny features (< 5×5) may be merged into a larger adjacent region if they are clearly part of the same issue.

## 11. Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2025-01-15 | — | Initial release |

*Update this table whenever the guidelines are revised.*

## 12. Contact & Questions

If any case not covered by these guidelines arises, the team lead or the annotating team should document the exception and add it to these guidelines for future consistency.