import unittest

from overlay_chart_model import (
    append_overlay_series,
    build_monthly_overlay_chart_model,
    build_overlay_chart_model,
    build_parameter_value_overlay_model,
    overlay_chart_model_to_echart_series,
)


class OverlayChartModelTests(unittest.TestCase):
    def test_two_line_overlay_chart_model(self) -> None:
        model = build_monthly_overlay_chart_model(
            chart_name="Monthly Heating Overlay",
            months=["Ocak", "Subat", "Mart"],
            base_values=[120, 100, 80],
            scenario_values=[100, 90, 75],
            scenario_name="Scenario A",
        )

        self.assertEqual(model.chart_name, "Monthly Heating Overlay")
        self.assertEqual(model.x_labels, ["Ocak", "Subat", "Mart"])
        self.assertEqual(len(model.series), 2)
        self.assertEqual(model.series[0].origin, "base")
        self.assertEqual(model.series[1].origin, "scenario")
        self.assertEqual(model.series[0].data, [120.0, 100.0, 80.0])

    def test_three_line_overlay_chart_model(self) -> None:
        model = build_monthly_overlay_chart_model(
            chart_name="Monthly Cooling Overlay",
            months=["Ocak", "Subat", "Mart"],
            base_values=[50, 60, 70],
            scenario_values=[45, 55, 68],
            scenario_name="Scenario A",
        )
        model = append_overlay_series(
            model,
            name="Scenario B",
            data=[44, 54, 66],
            origin="variant",
            color="#dc2626",
            line_style="dashed",
        )

        self.assertEqual(len(model.series), 3)
        self.assertEqual(model.series[2].name, "Scenario B")
        self.assertEqual(model.series[2].origin, "variant")
        self.assertEqual(model.series[2].line_style, "dashed")

    def test_multi_scenario_overlay_model_from_common_builder(self) -> None:
        model = build_overlay_chart_model(
            chart_name="Zone Temperature Overlay",
            x_labels=["t1", "t2", "t3", "t4"],
            series=[
                {
                    "name": "Base Scenario",
                    "data": [22.1, 22.3, 22.0, 21.8],
                    "origin": "base",
                    "color": "#94a3b8",
                },
                {
                    "name": "Scenario A",
                    "data": [21.9, 22.1, 21.8, 21.6],
                    "origin": "scenario",
                    "color": "#0f766e",
                },
                {
                    "name": "Scenario B",
                    "data": [22.4, 22.6, 22.2, 22.0],
                    "origin": "variant",
                    "color": "#f59e0b",
                    "line_style": "dotted",
                },
                {
                    "name": "Scenario C",
                    "data": [21.5, 21.7, 21.4, 21.2],
                    "origin": "variant",
                    "line_type": "step",
                    "color": "#dc2626",
                },
            ],
        )

        self.assertEqual(len(model.series), 4)
        self.assertEqual(model.series[3].line_type, "step")
        self.assertEqual(model.series[2].line_style, "dotted")

    def test_model_converts_to_echart_series_shape(self) -> None:
        model = build_overlay_chart_model(
            chart_name="Generic Overlay",
            x_labels=["A", "B"],
            series=[
                {
                    "name": "Base Scenario",
                    "data": [1, 2],
                    "origin": "base",
                    "color": "#94a3b8",
                },
                {
                    "name": "Scenario A",
                    "data": [2, 3],
                    "origin": "scenario",
                    "line_type": "area",
                    "color": "#0f766e",
                },
            ],
        )

        echart_series = overlay_chart_model_to_echart_series(model)

        self.assertEqual(len(echart_series), 2)
        self.assertEqual(echart_series[0]["name"], "Base Scenario")
        self.assertEqual(echart_series[0]["meta"]["origin"], "base")
        self.assertEqual(echart_series[0]["lineStyle"]["width"], 3)
        self.assertIn("Before / Base / Original", echart_series[0]["meta"]["description"])
        self.assertIn("areaStyle", echart_series[1])

    def test_base_series_is_standardized_and_moved_to_first(self) -> None:
        model = build_overlay_chart_model(
            chart_name="Standardization",
            x_labels=["t1", "t2"],
            series=[
                {
                    "name": "Scenario A",
                    "data": [20, 21],
                    "origin": "scenario",
                },
                {
                    "name": "Old",
                    "data": [22, 23],
                    "origin": "scenario",
                },
            ],
        )

        self.assertEqual(model.series[0].name, "Base Scenario")
        self.assertEqual(model.series[0].origin, "base")
        self.assertEqual(model.series[0].line_style, "solid")

    def test_parameter_value_overlay_model_normalizes_mixed_units(self) -> None:
        model = build_parameter_value_overlay_model(
            [
                {
                    "label": "Thickness",
                    "base_value": "0.20",
                    "updated_value": "0.25",
                    "unit": "m",
                },
                {
                    "label": "Conductivity",
                    "base_value": "1.75",
                    "updated_value": "1.25",
                    "unit": "W/mK",
                },
                {
                    "label": "Density",
                    "base_value": "2400",
                    "updated_value": "2200",
                    "unit": "kg/m3",
                },
            ]
        )

        self.assertTrue(model.is_normalized)
        self.assertEqual(model.labels, ["Thickness", "Conductivity", "Density"])
        self.assertEqual(model.raw_base_series, [0.2, 1.75, 2400.0])
        self.assertEqual(model.raw_updated_series, [0.25, 1.25, 2200.0])
        self.assertEqual(model.base_series, [0.8, 1.0, 1.0])
        self.assertAlmostEqual(model.updated_series[0], 1.0)
        self.assertAlmostEqual(model.updated_series[1], 1.25 / 1.75)
        self.assertAlmostEqual(model.updated_series[2], 2200.0 / 2400.0)

    def test_parameter_value_overlay_model_keeps_raw_values_for_single_unit(self) -> None:
        model = build_parameter_value_overlay_model(
            [
                {
                    "label": "Thickness",
                    "base_value": "0.19",
                    "updated_value": "0.22",
                    "unit": "m",
                }
            ]
        )

        self.assertFalse(model.is_normalized)
        self.assertEqual(model.base_series, [0.19])
        self.assertEqual(model.updated_series, [0.22])
        self.assertEqual(model.missing_updated_labels, [])

    def test_parameter_value_overlay_model_tracks_missing_updated_values(self) -> None:
        model = build_parameter_value_overlay_model(
            [
                {
                    "label": "Thickness",
                    "base_value": "0.19",
                    "updated_value": "",
                    "unit": "m",
                },
                {
                    "label": "Conductivity",
                    "base_value": "1.75",
                    "updated_value": "1.25",
                    "unit": "W/mK",
                },
            ]
        )

        self.assertEqual(model.labels, ["Thickness", "Conductivity"])
        self.assertEqual(model.missing_updated_labels, ["Thickness"])
        self.assertIsNone(model.updated_series[0])
        self.assertIsNotNone(model.base_series[0])


if __name__ == "__main__":
    unittest.main()
