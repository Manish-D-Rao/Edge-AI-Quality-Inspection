from __future__ import annotations

from typing import Any


def _coordinates(box: dict[str, Any]) -> tuple[int, int, int, int]:
    try:
        values = (box["x"], box["y"], box["width"], box["height"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Boxes require integer x, y, width, and height.") from error
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        raise ValueError("Boxes require integer x, y, width, and height.")
    x, y, width, height = values
    if x < 0 or y < 0:
        raise ValueError("Box coordinates must be non-negative.")
    if width <= 0 or height <= 0:
        raise ValueError("Box width and height must be positive.")
    return x, y, width, height


def _iou(box1: list[int] | tuple[int, ...], box2: list[int] | tuple[int, ...]) -> float:
    """Compute IoU for [x, y, width, height] pixel-coordinate boxes."""
    if len(box1) != 4 or len(box2) != 4:
        raise ValueError("Boxes must contain x, y, width, and height.")
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    if w1 <= 0 or h1 <= 0 or w2 <= 0 or h2 <= 0:
        raise ValueError("Box width and height must be positive.")

    left = max(x1, x2)
    top = max(y1, y2)
    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)
    intersection = max(0, right - left) * max(0, bottom - top)
    union = w1 * h1 + w2 * h2 - intersection
    return intersection / union


def match_candidates(
    candidates: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    iou_threshold: float = 0.3,
) -> dict[str, Any]:
    """Return a maximum-cardinality one-to-one assignment above the IoU threshold."""
    if not 0 <= iou_threshold <= 1:
        raise ValueError("iou_threshold must be between 0 and 1.")

    candidate_boxes = [_coordinates(box) for box in candidates]
    ground_truth_boxes = [_coordinates(box) for box in ground_truth]
    iou_matrix = [
        [_iou(candidate, truth) for truth in ground_truth_boxes]
        for candidate in candidate_boxes
    ]

    # Augmenting paths ensure an early ambiguous match cannot block another
    # valid match, unlike greedy per-ground-truth assignment.
    candidate_for_gt: dict[int, int] = {}

    def assign(gt_index: int, visited_candidates: set[int]) -> bool:
        eligible = sorted(
            (
                index
                for index, row in enumerate(iou_matrix)
                if row[gt_index] >= iou_threshold and row[gt_index] > 0
            ),
            key=lambda index: (-iou_matrix[index][gt_index], index),
        )
        for candidate_index in eligible:
            if candidate_index in visited_candidates:
                continue
            visited_candidates.add(candidate_index)
            previous_gt = candidate_for_gt.get(candidate_index)
            if previous_gt is None or assign(previous_gt, visited_candidates):
                candidate_for_gt[candidate_index] = gt_index
                return True
        return False

    for gt_index in range(len(ground_truth_boxes)):
        assign(gt_index, set())

    pairs = sorted(
        ((candidate, gt) for candidate, gt in candidate_for_gt.items()),
        key=lambda pair: pair[0],
    )
    matched_candidates = [candidate for candidate, _ in pairs]
    matched_ground_truth = [gt for _, gt in pairs]
    used_candidates = set(matched_candidates)
    used_ground_truth = set(matched_ground_truth)

    return {
        "matched_candidate_indices": matched_candidates,
        "matched_ground_truth_indices": matched_ground_truth,
        "false_positives": [
            index for index in range(len(candidates)) if index not in used_candidates
        ],
        "missed_gt": [
            index
            for index in range(len(ground_truth))
            if index not in used_ground_truth
        ],
        "iou_matrix": iou_matrix,
    }


def compute_metrics(
    candidates: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    iou_threshold: float = 0.3,
) -> dict[str, Any]:
    """Compute instance-level recall, precision, F1, and false-positive counts."""
    matches = match_candidates(candidates, ground_truth, iou_threshold)
    matched = len(matches["matched_ground_truth_indices"])
    false_positives = len(matches["false_positives"])
    missed = len(matches["missed_gt"])
    candidate_count = len(candidates)
    ground_truth_count = len(ground_truth)

    recall = matched / ground_truth_count if ground_truth_count else 0.0
    precision = matched / candidate_count if candidate_count else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "n_matched": matched,
        "n_false_positives": false_positives,
        "n_missed": missed,
        "n_candidates": candidate_count,
        "n_ground_truth": ground_truth_count,
        "iou_threshold": iou_threshold,
    }
