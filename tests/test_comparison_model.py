import unittest

from comparison_model import (
    COMMON_COMPARISON_FIELDS,
    build_unified_comparison_model,
    validate_common_comparison_items,
)


class ComparisonModelTests(unittest.TestCase):
    def test_unified_model_collects_multiple_comparison_types(self) -> None:
        unified = build_unified_comparison_model(
            changed_cells=[
                {
                    "row_key": "name=beton",
                    "column": "thickness_m",
                    "baseline_value": "0.20",
                    "scenario_value": "0.25",
                }
            ],
            metric_rows=[
                {
                    "metric_id": "annual_heating",
                    "label": "Annual Heating",
                    "unit": "kWh",
                    "base_value": 1000,
                    "scenario_value": 900,
                    "delta": -100,
                    "percent_delta": -10,
                }
            ],
            cost_summary={
                "has_data": True,
                "method": "annual_cost",
                "currency": "TRY",
                "base_cost": 20000,
                "scenario_cost": 18000,
                "delta": -2000,
                "percent_delta": -10,
                "message": "direct",
            },
            layer_impact_rows=[
                {
                    "id": "layer-1",
                    "changed_field": "conductivity",
                    "old_value": "1.75",
                    "new_value": "2.10",
                    "layer_name": "duvar | 1",
                    "material_name": "beton",
                    "construction_names": "disduvar",
                    "badge": "Degisen Layer",
                }
            ],
        )

        items = unified["items"]
        validate_common_comparison_items(items)
        for item in items:
            self.assertEqual(tuple(item.keys()), COMMON_COMPARISON_FIELDS)

        by_type = unified["summary"]["by_type"]
        self.assertEqual(by_type["parameter"], 1)
        self.assertEqual(by_type["metric"], 1)
        self.assertEqual(by_type["cost"], 1)
        self.assertEqual(by_type["layer_impact"], 1)

    def test_unified_model_builds_severity_and_highlight_summary(self) -> None:
        unified = build_unified_comparison_model(
            metric_rows=[
                {
                    "metric_id": "annual_heating",
                    "label": "Annual Heating",
                    "unit": "kWh",
                    "base_value": 1000,
                    "scenario_value": 650,
                    "delta": -350,
                    "percent_delta": -35,
                },
                {
                    "metric_id": "annual_cooling",
                    "label": "Annual Cooling",
                    "unit": "kWh",
                    "base_value": 500,
                    "scenario_value": 575,
                    "delta": 75,
                    "percent_delta": 15,
                },
            ],
            cost_summary={
                "has_data": True,
                "method": "annual_cost",
                "currency": "TRY",
                "base_cost": 10000,
                "scenario_cost": 13500,
                "delta": 3500,
                "percent_delta": 35,
                "message": "direct",
            },
        )

        summary = unified["summary"]
        self.assertTrue(summary["top_changed"])
        self.assertEqual(summary["most_critical"]["severity_level"], "kritik")
        self.assertEqual(summary["best_improvement"]["trend"], "iyilesme")
        self.assertEqual(summary["worst_worsening"]["trend"], "kotulesme")
        self.assertTrue(str(summary["most_critical"]["auto_comment"]).strip())

        items = unified["items"]
        annual_heating_item = next(item for item in items if item["item_id"] == "annual_heating")
        self.assertEqual(annual_heating_item["context"]["severity_level"], "kritik")
        self.assertEqual(annual_heating_item["context"]["trend"], "iyilesme")
        self.assertTrue(str(annual_heating_item["context"]["auto_comment"]).strip())


if __name__ == "__main__":
    unittest.main()
