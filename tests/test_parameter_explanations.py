import unittest

from parameter_explanations import build_parameter_explanation


class ParameterExplanationTests(unittest.TestCase):
    def test_thickness_template_returns_expected_text(self) -> None:
        result = build_parameter_explanation(
            field_name="thickness_m",
            label="Material Thickness",
            description="fallback",
            expected_impacts=("u_value",),
        )

        self.assertIn("Kalınlık", result["summary"])
        self.assertTrue(result["impact"])

    def test_conductivity_template_returns_expected_text(self) -> None:
        result = build_parameter_explanation(
            field_name="conductivity_w_per_mk",
            label="Material Conductivity",
            description="fallback",
            expected_impacts=("heat_transfer",),
        )

        self.assertIn("Iletkenlik", result["summary"])
        self.assertTrue(result["impact"])

    def test_fallback_uses_description_and_impacts(self) -> None:
        result = build_parameter_explanation(
            field_name="unknown_field",
            label="Unknown Parameter",
            description="Unknown parameter description.",
            expected_impacts=("impact_a", "impact_b"),
        )

        self.assertIn("Unknown parameter description", result["summary"])
        self.assertIn("impact_a", result["impact"])


if __name__ == "__main__":
    unittest.main()
