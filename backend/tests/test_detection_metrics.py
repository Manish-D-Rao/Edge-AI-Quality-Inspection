from __future__ import annotations

import pytest

from app.services.detection_metrics import _iou, compute_metrics, match_candidates


def box(x: int, y: int = 0, width: int = 10, height: int = 10) -> dict[str, int]:
    return {"x": x, "y": y, "width": width, "height": height}


def test_iou_identical_disjoint_and_partial_boxes() -> None:
    assert _iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1
    assert _iou([0, 0, 10, 10], [10, 0, 10, 10]) == 0
    assert _iou([0, 0, 10, 10], [5, 0, 10, 10]) == pytest.approx(1 / 3)


def test_iou_threshold_boundary_is_inclusive() -> None:
    candidate = box(0, width=6)
    truth = box(3, width=7)
    assert _iou(
        [candidate["x"], 0, candidate["width"], 10],
        [truth["x"], 0, truth["width"], 10],
    ) == pytest.approx(0.3)
    assert len(match_candidates([candidate], [truth], 0.3)["matched_candidate_indices"]) == 1
    assert len(
        match_candidates([candidate], [truth], 0.300001)["matched_candidate_indices"]
    ) == 0


def test_matching_finds_maximum_cardinality_assignment() -> None:
    candidates = [box(4, width=10), box(0, width=4)]
    truths = [box(0), box(8)]
    result = match_candidates(candidates, truths, iou_threshold=0.3)
    assert len(result["matched_candidate_indices"]) == 2
    assert set(result["matched_candidate_indices"]) == {0, 1}
    assert not result["false_positives"]
    assert not result["missed_gt"]


def test_duplicate_candidates_only_match_one_ground_truth() -> None:
    result = match_candidates(
        [box(0), box(1)], [box(0)], iou_threshold=0.3
    )
    assert result["matched_candidate_indices"] == [0]
    assert result["false_positives"] == [1]
    assert result["missed_gt"] == []


def test_empty_predictions_and_ground_truth_are_explicit() -> None:
    missed = compute_metrics([], [box(0)])
    assert missed["recall"] == 0
    assert missed["precision"] == 0
    assert missed["n_missed"] == 1

    false_alarm = compute_metrics([box(0)], [])
    assert false_alarm["n_false_positives"] == 1
    assert false_alarm["recall"] == 0

    empty = compute_metrics([], [])
    assert empty["f1"] == 0


@pytest.mark.parametrize(
    "candidates,truths",
    [([box(0, width=0)], []), ([box(0)], [box(0, height=-1)])],
)
def test_invalid_box_dimensions_fail(candidates, truths) -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_metrics(candidates, truths)


def test_invalid_iou_threshold_fails() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        match_candidates([], [], 1.1)


def test_negative_coordinates_fail() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        compute_metrics([box(-1)], [])
