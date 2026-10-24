import unittest

import numpy as np

from app.services.preprocessing_experiment import (
    VARIANTS,
    inspect_variant,
)


class PreprocessingExperimentTests(unittest.TestCase):
    def test_each_variant_reports_fixed_configuration_and_measurables(self) -> None:
        reference = np.zeros((64, 80, 3), dtype=np.uint8)
        test = reference.copy()
        test[20:30, 20:30] = 220
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                result, images = inspect_variant(
                    reference, test, variant=variant
                )
                self.assertEqual(
                    result["configuration"], {"threshold": 25, "min_area": 80}
                )
                self.assertIn("candidate_count", result)
                self.assertIn("foreground_mask_percentage", result)
                self.assertIn("connected_component_count", result)
                self.assertGreaterEqual(result["processing_time_ms"], 0)
                self.assertEqual(images["mask.png"].shape, (64, 80))

    def test_unknown_variant_is_rejected(self) -> None:
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            inspect_variant(image, image, variant="not_a_variant")


if __name__ == "__main__":
    unittest.main()
