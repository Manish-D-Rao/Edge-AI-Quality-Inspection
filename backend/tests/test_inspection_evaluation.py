import unittest

import numpy as np

from app.services.inspection_evaluation import (
    candidate_bbox_ranges,
    evaluate_edit_coverage,
    inspect_pair,
    synthetic_edit_boxes,
)


class InspectionEvaluationTests(unittest.TestCase):
    def test_candidate_bbox_ranges_and_empty_case(self) -> None:
        regions = [
            {"x": 10, "y": 20, "width": 5, "height": 6},
            {"x": 3, "y": 40, "width": 7, "height": 9},
        ]
        self.assertEqual(
            candidate_bbox_ranges(regions),
            {"x": [3, 10], "y": [20, 40]},
        )
        self.assertEqual(
            candidate_bbox_ranges([]),
            {"x": None, "y": None},
        )

    def test_edit_coverage_uses_union_of_box_intersections(self) -> None:
        edit = {"name": "edit", "x": 10, "y": 20, "width": 4, "height": 2}
        regions = [
            {"x": 10, "y": 20, "width": 2, "height": 2},
            {"x": 12, "y": 20, "width": 2, "height": 2},
            {"x": 50, "y": 50, "width": 2, "height": 2},
        ]
        result = evaluate_edit_coverage([edit], regions)
        self.assertTrue(result["edits"][0]["covered"])
        self.assertEqual(result["edits"][0]["bbox_coverage_ratio"], 1.0)
        self.assertEqual(result["additional_candidate_count"], 1)
        self.assertEqual(result["additional_candidate_indexes"], [2])

    def test_inspection_results_use_reference_dimensions(self) -> None:
        reference = np.zeros((100, 120, 3), dtype=np.uint8)
        test = np.zeros((50, 60, 3), dtype=np.uint8)
        result, images = inspect_pair(
            reference,
            test,
            reference_path="reference.jpg",
            test_path="test.jpg",
            threshold=25,
            min_area=80,
        )
        self.assertEqual((result["image_width"], result["image_height"]), (120, 100))
        self.assertEqual(images["annotated.jpg"].shape, reference.shape)
        self.assertEqual(result["coordinate_system"], "reference image pixel coordinates")

    def test_synthetic_edit_bounds_come_from_draw_operations(self) -> None:
        edits = synthetic_edit_boxes()
        self.assertEqual(
            [(edit["x"], edit["y"], edit["width"], edit["height"]) for edit in edits],
            [(367, 67, 57, 19), (511, 141, 19, 19)],
        )


if __name__ == "__main__":
    unittest.main()
