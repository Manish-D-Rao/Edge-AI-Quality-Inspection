from __future__ import annotations

import csv, json, os, random
from collections import defaultdict
from typing import Any, Dict, List, Tuple

RANDOM_SEED = 42
MIN_HELDOUT_DEFECT = 20
MIN_HELDOUT_NORMAL = 20
SPLIT_DIR = "datasets/labels/splits"


def load_manifest(manifest_path: str) -> List[Dict[str, str]]:
    rows = []
    with open(manifest_path, "r") as f:
        import csv as c
        reader = c.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def group_by_board(manifest_path: str, ann_dir: str) -> Dict[str, List[str]]:
    rows = load_manifest(manifest_path)
    groups = defaultdict(list)
    for row in rows:
        img_id = os.path.splitext(os.path.basename(row["image_path"]))[0]
        board = None
        for r in rows:
            if r["image_path"] == row["image_path"]:
                board = r.get("board_revision", "").strip()
            if not board or board == "unknown":
                board = r.get("capture_session", "").strip()
        if not board or board == "unknown":
            parts = os.path.basename(row["image_path"]).replace(".jpg", "").split("_")
            board = "_".join(parts[:2]) if len(parts) >= 2 else "unknown"
        groups[board].append(img_id)
    return dict(groups)


def create_splits(
    manifest_path: str,
    ann_dir: str,
    heldout_defect_min: int = MIN_HELDOUT_DEFECT,
    heldout_normal_min: int = MIN_HELDOUT_NORMAL,
    seed: int = RANDOM_SEED,
) -> Dict[str, Dict[str, List[str]]]:
    random.seed(seed)
    rows = load_manifest(manifest_path)
    groups = group_by_board(manifest_path, ann_dir)

    all_imgs: List[Tuple[str, str]] = []
    for bid, iids in groups.items():
        for img_id in iids:
            path = os.path.join(ann_dir, img_id + ".json")
            ann = json.load(open(path)) if os.path.exists(path) else []
            label = ann[0].get("label", "unknown") if ann else "unknown"
            all_imgs.append((img_id, label))

    defect = [(i, l) for i, l in all_imgs if l == "defect"]
    normal = [(i, l) for i, l in all_imgs if l == "normal"]
    other = [(i, l) for i, l in all_imgs if l not in ("defect", "normal")]

    random.shuffle(defect)
    random.shuffle(normal)
    random.shuffle(other)

    held_def = max(MIN_HELDOUT_DEFECT, min(len(defect) // 5, len(defect) - 5))
    held_norm = max(MIN_HELDOUT_NORMAL, len(normal) // 5, len(normal) - 5)
    held_def = min(held_def, len(defect) - 5)
    held_norm = min(held_norm, len(normal) - 5)
    if len(defect) < 10:
        held_def = max(1, len(defect) - 2)
    if len(normal) < 10:
        held_norm = max(1, len(normal) - 2)

    h_def_ids = [i for i, _ in defect[:held_def]]
    h_norm_ids = [i for i, _ in normal[:held_norm]]
    rem_def = [i for i, _ in defect[held_def:]]
    rem_norm = [i for i, _ in normal[held_norm:]]
    rem_other = [i for i, _ in other]

    v_def = max(1, min(len(rem_def) // 4, 5))
    v_norm = max(1, min(len(rem_norm) // 4, 5))
    val_def_ids = rem_def[:v_def]
    train_def_ids = rem_def[v_def:]
    val_norm_ids = rem_norm[:v_norm]
    train_norm_ids = rem_norm[v_norm:]
    val_other_ids = rem_other[: max(1, len(rem_other) // 4)]
    train_other_ids = rem_other[max(1, len(rem_other) // 4):]

    splits = {
        "train": {"image_ids": train_def_ids + train_norm_ids + train_other_ids},
        "validation": {"image_ids": val_def_ids + val_norm_ids + val_other_ids},
        "held_out": {"image_ids": h_def_ids + h_norm_ids},
    }

    print(f"Split summary (seed={RANDOM_SEED}):")
    print(f"  Total: {len(all_imgs)}, Defect: {len(defect)} (held: {len(h_def_ids)}), Normal: {len(normal)} (held: {len(h_norm_ids)})")
    print(f"  Train: {len(splits['train']['image_ids'])}, Val: {len(splits['validation']['image_ids'])}, Held: {len(splits['held_out']['image_ids'])}")
    print(f"  Held-out defect: {len(h_def_ids)} (min: {heldout_defect_min}), Normal: {len(h_norm_ids)} (min: {heldout_normal_min})")
    return splits


def save_splits(splits: Dict[str, Dict[str, List[str]]], splits_dir: str) -> None:
    os.makedirs(splits_dir, exist_ok=True)
    for sn, sd in splits.items():
        with open(os.path.join(splits_dir, sn + "_ids.json"), "w") as f:
            json.dump(sd["image_ids"], f, indent=2)
        print(f"Saved {len(sd['image_ids'])} image IDs to {sn}_ids.json")


def main() -> None:
    manifest_path = "datasets/labels/dataset_manifest.csv"
    ad = "datasets/labels"
    if not os.path.exists(manifest_path):
        print(f"Error: Manifest not found at {manifest_path}")
        print("Run T015 first to create the dataset manifest.")
        return
    splits = create_splits(manifest_path, ad)
    save_splits(splits, os.path.join(ad, "splits"))


if __name__ == "__main__":
    main()