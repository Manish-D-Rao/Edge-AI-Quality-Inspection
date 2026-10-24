import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.services import image_alignment
from app.services.image_alignment import align_test_to_reference


class ImageAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(17)
        self.reference = rng.integers(
            0, 256, size=(300, 400, 3), dtype=np.uint8
        )
        for _ in range(20):
            center = tuple(int(value) for value in rng.integers(20, 380, 2))
            cv2.circle(
                self.reference,
                center,
                int(rng.integers(5, 18)),
                tuple(int(value) for value in rng.integers(0, 256, 3)),
                -1,
            )
        shift = np.float32([[1, 0, 13], [0, 1, -8]])
        self.test = cv2.warpAffine(
            self.reference, shift, (400, 300), borderValue=(0, 0, 0)
        )

    def test_aligns_translated_image_into_reference_dimensions(self) -> None:
        result = align_test_to_reference(self.reference, self.test)
        self.assertTrue(result.diagnostics["success"])
        self.assertIsNotNone(result.aligned_test)
        assert result.aligned_test is not None
        self.assertEqual(result.aligned_test.shape, self.reference.shape)
        self.assertGreaterEqual(result.diagnostics["inlier_count"], 10)

    def test_fails_safely_when_feature_matches_are_insufficient(self) -> None:
        blank = np.zeros((120, 160, 3), dtype=np.uint8)
        result = align_test_to_reference(blank, blank)
        self.assertFalse(result.diagnostics["success"])
        self.assertIsNone(result.aligned_test)
        self.assertIn("descriptor", result.diagnostics["failure_reason"])

    def test_rejects_non_finite_transform(self) -> None:
        original_find_homography = cv2.findHomography

        def invalid_homography(source, destination, method, threshold):
            _, inlier_mask = original_find_homography(
                source, destination, method, threshold
            )
            return np.full((3, 3), np.nan), inlier_mask

        with patch.object(
            image_alignment.cv2,
            "findHomography",
            side_effect=invalid_homography,
        ):
            result = align_test_to_reference(self.reference, self.test)
        self.assertFalse(result.diagnostics["success"])
        self.assertIsNone(result.aligned_test)
        self.assertIn("non-finite", result.diagnostics["failure_reason"])


if __name__ == "__main__":
    unittest.main()
