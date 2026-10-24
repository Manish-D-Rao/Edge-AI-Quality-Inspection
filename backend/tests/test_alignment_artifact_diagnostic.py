import unittest

import cv2
import numpy as np

from app.services.alignment_artifact_diagnostic import (
    analyze_comparison,
    compare_masks,
    warp_with_valid_source_mask,
)


class AlignmentArtifactDiagnosticTests(unittest.TestCase):
    def test_warp_support_excludes_constant_border_fill(self) -> None:
        source = np.full((20, 30, 3), 100, dtype=np.uint8)
        transform = np.float64([[1, 0, 5], [0, 1, 0], [0, 0, 1]])
        warped, support = warp_with_valid_source_mask(
            source, transform, (30, 20)
        )
        self.assertTrue(np.all(warped[:, :5] == 0))
        self.assertTrue(np.all(support[:, :5] == 0))
        self.assertTrue(np.all(support[:, 5:] == 255))

    def test_comparison_reports_full_and_support_aware_statistics(self) -> None:
        reference = np.zeros((40, 50, 3), dtype=np.uint8)
        test = reference.copy()
        test[10:20, 10:20] = 255
        support = np.full((40, 50), 255, dtype=np.uint8)
        support[:, :5] = 0
        support[5:25, 5:25] = 0
        result, images = analyze_comparison(reference, test, support)
        self.assertEqual(result["image_dimensions"], {"width": 50, "height": 40})
        self.assertEqual(
            result["coordinate_system"], "reference image pixel coordinates"
        )
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["valid_source_filtered_candidate_count"], 0)
        self.assertEqual(result["invalid_border_only_candidate_count"], 1)
        self.assertIn("connected_components", result)
        self.assertEqual(images["valid_source_mask.png"].shape, support.shape)

    def test_mask_comparison_counts_changed_pixels(self) -> None:
        left = np.zeros((10, 10), dtype=np.uint8)
        right = left.copy()
        left[2:4, 2:4] = 255
        right[3:5, 2:4] = 255
        support = np.full((10, 10), 255, dtype=np.uint8)
        result = compare_masks(left, right, support)
        self.assertEqual(result["changed_foreground_decisions"], 4)
        self.assertEqual(result["left_only_foreground_pixels"], 2)
        self.assertEqual(result["right_only_foreground_pixels"], 2)
        self.assertEqual(result["changed_invalid_border_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
