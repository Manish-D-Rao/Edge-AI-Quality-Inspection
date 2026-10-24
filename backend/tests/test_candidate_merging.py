import unittest

from app.services.candidate_merging import (
    merge_candidate_boxes,
    summarize_boxes,
)


class CandidateMergingTests(unittest.TestCase):
    def test_overlap_strategy_merges_only_positive_area_intersections(self) -> None:
        regions = [
            {"x": 0, "y": 0, "width": 10, "height": 10, "area": 30},
            {"x": 8, "y": 2, "width": 10, "height": 10, "area": 30},
            {"x": 18, "y": 2, "width": 10, "height": 10, "area": 30},
        ]
        merged = merge_candidate_boxes(regions, strategy="overlap")
        self.assertEqual(len(merged), 2)
        self.assertEqual(sorted(box["group_size"] for box in merged), [1, 2])

    def test_nearby_merging_is_transitive_and_preserves_members(self) -> None:
        regions = [
            {"x": 0, "y": 0, "width": 5, "height": 5, "area": 10},
            {"x": 10, "y": 0, "width": 5, "height": 5, "area": 10},
            {"x": 20, "y": 0, "width": 5, "height": 5, "area": 10},
        ]
        merged = merge_candidate_boxes(
            regions, strategy="nearby", distance_threshold=5
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["candidate_indexes"], [0, 1, 2])
        self.assertEqual(merged[0]["width"], 25)

    def test_summary_reports_box_dimensions_and_group_sizes(self) -> None:
        summary = summarize_boxes([
            {
                "x": 0,
                "y": 0,
                "width": 4,
                "height": 6,
                "group_size": 2,
            },
            {
                "x": 8,
                "y": 0,
                "width": 5,
                "height": 6,
                "group_size": 1,
            },
        ])
        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["box_width_pixels"]["median"], 4.5)
        self.assertEqual(summary["merge_group_sizes"], {"1": 1, "2": 1})


if __name__ == "__main__":
    unittest.main()
