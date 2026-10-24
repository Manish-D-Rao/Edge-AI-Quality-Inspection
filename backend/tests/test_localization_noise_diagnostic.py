import unittest

import numpy as np

from app.services.localization_noise_diagnostic import analyze_localization


class LocalizationNoiseDiagnosticTests(unittest.TestCase):
    def test_reports_explicit_size_and_aspect_buckets(self) -> None:
        reference = np.zeros((100, 100, 3), dtype=np.uint8)
        regions = [
            {"x": 10, "y": 10, "width": 10, "height": 10, "area": 100},
            {"x": 30, "y": 10, "width": 30, "height": 20, "area": 600},
            {"x": 70, "y": 10, "width": 80, "height": 20, "area": 10_001},
        ]
        result, _ = analyze_localization(reference, regions)
        self.assertEqual(
            result["distributions"]["contour_area_buckets"],
            {
                "small_le_500": 1,
                "medium_501_10000": 1,
                "large_gt_10000": 1,
            },
        )
        self.assertEqual(
            result["distributions"]["aspect_ratio_buckets"],
            {
                "portrait_lt_0_5": 0,
                "balanced_0_5_to_2": 2,
                "landscape_gt_2": 1,
            },
        )

    def test_groups_nearby_boxes_but_keeps_distant_box_separate(self) -> None:
        reference = np.zeros((100, 100, 3), dtype=np.uint8)
        regions = [
            {"x": 10, "y": 10, "width": 5, "height": 5, "area": 100},
            {"x": 20, "y": 10, "width": 5, "height": 5, "area": 100},
            {"x": 70, "y": 70, "width": 5, "height": 5, "area": 100},
        ]
        result, _ = analyze_localization(reference, regions)
        nearby = result["nearby_boxes"]["within_10_pixels"]
        self.assertEqual(nearby["nearby_box_pair_count"], 1)
        self.assertEqual(nearby["multi_box_group_count"], 1)
        self.assertEqual(nearby["candidates_in_multi_box_groups"], 2)
        self.assertEqual(nearby["largest_group_size"], 2)


if __name__ == "__main__":
    unittest.main()
