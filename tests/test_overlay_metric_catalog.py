import unittest

from overlay_metric_catalog import (
    build_overlay_metric_catalog_markdown,
    get_overlay_suitable_metrics,
    get_overlay_unsuitable_metrics,
)


class OverlayMetricCatalogTests(unittest.TestCase):
    def test_overlay_suitable_metrics_include_core_time_series(self) -> None:
        metric_ids = {item.metric_id for item in get_overlay_suitable_metrics()}

        self.assertIn("monthly_heating", metric_ids)
        self.assertIn("monthly_cooling", metric_ids)
        self.assertIn("zone_temperatures", metric_ids)
        self.assertIn("surface_temperature", metric_ids)
        self.assertIn("hourly_temperature_profile", metric_ids)

    def test_overlay_unsuitable_metrics_include_single_value_kpis(self) -> None:
        metric_ids = {item.metric_id for item in get_overlay_unsuitable_metrics()}

        self.assertIn("annual_heating", metric_ids)
        self.assertIn("total_annual_cost", metric_ids)

    def test_each_metric_has_reason_and_visual_decision(self) -> None:
        all_metrics = get_overlay_suitable_metrics() + get_overlay_unsuitable_metrics()

        for metric in all_metrics:
            self.assertTrue(metric.reason.strip())
            self.assertIn(metric.preferred_visual, {"overlay_line", "kpi_or_bar"})

    def test_markdown_output_contains_two_main_sections(self) -> None:
        markdown = build_overlay_metric_catalog_markdown()

        self.assertIn("Overlay Line Chart Icin Uygun", markdown)
        self.assertIn("Overlay Icin Uygun Olmayanlar", markdown)


if __name__ == "__main__":
    unittest.main()
