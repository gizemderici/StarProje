import unittest

from parameter_catalog import get_parameter_definition
from ui_sections.analytics import (
    build_missing_metrics_markdown,
    build_run_artifacts_markdown,
    build_selected_analysis_signature,
)
from ui_sections.parameter_sections import (
    build_parameter_section_counts,
    filter_parameters_for_section,
    resolve_default_category_for_section,
    resolve_parameter_section_for_category,
)
from view_models.parameter_effects import (
    analyze_parameter_change_state,
    build_parameter_change_summary_text,
    try_parse_number,
)
from parameter_catalog import list_parameter_definitions


class UiSectionHelperTests(unittest.TestCase):
    def test_build_selected_analysis_signature_uses_name_and_mtime(self) -> None:
        signature = build_selected_analysis_signature(
            [{"scenario_name": "a", "report_mtime": 1.5}, {"scenario_name": "b", "report_mtime": 2}],
            "a",
        )

        self.assertEqual(signature[1], "a")
        self.assertEqual(signature[0][0], ("a", 1.5))

    def test_build_missing_metrics_markdown_lists_missing_and_null_values(self) -> None:
        markdown = build_missing_metrics_markdown(
            title="Enerji performansi",
            selected_name="demo",
            missing_metric_ids=["total_energy"],
            null_metric_ids=["annual_cooling"],
            report_path="scenario_runs/demo/comparison/demo__comparison.json",
        )

        self.assertIn("Enerji performansi veri durumu", markdown)
        self.assertIn("total_energy", markdown)
        self.assertIn("annual_cooling", markdown)
        self.assertIn("scenario_runs/demo/comparison", markdown)

    def test_build_run_artifacts_markdown_lists_paths(self) -> None:
        markdown = build_run_artifacts_markdown(
            title="Olusan Dosyalar",
            lead="Tamamlandi.",
            artifacts=[("Cikti", "simulation_outputs/demo/output.csv"), ("Log", None)],
        )

        self.assertIn("Olusan Dosyalar", markdown)
        self.assertIn("simulation_outputs/demo/output.csv", markdown)
        self.assertNotIn("Log", markdown)

    def test_parameter_section_counts_group_material_and_window_categories(self) -> None:
        counts = build_parameter_section_counts(list_parameter_definitions())

        self.assertGreater(counts["Tum"], 0)
        self.assertGreater(counts["Material"], 0)
        self.assertGreater(counts["Construction"], 0)
        self.assertGreater(counts["Window"], 0)

    def test_filter_parameters_for_section_filters_window_entries(self) -> None:
        window_parameters = filter_parameters_for_section(list_parameter_definitions(), "Window")

        self.assertTrue(window_parameters)
        self.assertTrue(all(getattr(item, "category", "") == "Windows" for item in window_parameters))

    def test_resolve_parameter_section_for_category_keeps_filters_in_sync(self) -> None:
        self.assertEqual(resolve_parameter_section_for_category("Tum Kategoriler"), "Tum")
        self.assertEqual(resolve_parameter_section_for_category("Materials"), "Material")
        self.assertEqual(resolve_parameter_section_for_category("Walls"), "Construction")
        self.assertEqual(resolve_parameter_section_for_category("Windows"), "Window")

    def test_resolve_default_category_for_section_supports_empty_initial_state(self) -> None:
        self.assertEqual(resolve_default_category_for_section("Tum"), "Tum Kategoriler")
        self.assertEqual(resolve_default_category_for_section("Material"), "Materials")
        self.assertEqual(resolve_default_category_for_section("Construction"), "Tum Kategoriler")
        self.assertEqual(resolve_default_category_for_section("Window"), "Windows")

    def test_try_parse_number_supports_decimal_comma(self) -> None:
        self.assertEqual(try_parse_number("8,5"), 8.5)
        self.assertEqual(try_parse_number("1.234,5"), 1234.5)
        self.assertEqual(try_parse_number("1,234.5"), 1234.5)

    def test_parameter_change_summary_mentions_direction(self) -> None:
        parameter = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        change_state = analyze_parameter_change_state(
            parameter=parameter,
            current_value="0.5",
            new_value="0.8",
        )
        summary = build_parameter_change_summary_text(
            parameter=parameter,
            current_value="0.5",
            new_value="0.8",
            change_state=change_state,
        )

        self.assertTrue(change_state["has_effective_change"])
        self.assertIn("0.5", summary)
        self.assertIn("0.8", summary)


if __name__ == "__main__":
    unittest.main()
