import unittest

from simulation_results_parser import (
    COMMON_RESULT_FIELDS,
    build_cost_summary_from_metrics,
    build_report_results_model,
    build_ui_results_model,
    parse_simulation_results,
    validate_common_result_rows,
)


class SimulationResultsParserTests(unittest.TestCase):
    def test_parse_simulation_results_computes_delta_and_percent_delta(self) -> None:
        base_results = {
            "metrics": {
                "annual_heating": 1000,
                "annual_cooling": 500,
                "eui": 85,
                "peak_heating": 120,
            }
        }
        scenario_results = {
            "metrics": {
                "annual_heating": 850,
                "annual_cooling": 530,
                "eui": 78,
                "peak_heating": 110,
            }
        }

        rows = parse_simulation_results(base_results, scenario_results)
        by_id = {row["metric_id"]: row for row in rows}

        self.assertEqual(by_id["annual_heating"]["delta"], -150.0)
        self.assertEqual(by_id["annual_heating"]["percent_delta"], -15.0)
        self.assertEqual(by_id["annual_cooling"]["delta"], 30.0)
        self.assertEqual(by_id["annual_cooling"]["percent_delta"], 6.0)

    def test_alias_resolution_works_with_human_readable_names(self) -> None:
        base_results = {"Annual Heating": "100", "EUI": "50"}
        scenario_results = {"annual heating": "90", "energy use intensity": "40"}

        rows = parse_simulation_results(base_results, scenario_results)
        by_id = {row["metric_id"]: row for row in rows}

        self.assertEqual(by_id["annual_heating"]["base_value"], "100")
        self.assertEqual(by_id["annual_heating"]["scenario_value"], "90")
        self.assertEqual(by_id["eui"]["base_value"], "50")
        self.assertEqual(by_id["eui"]["scenario_value"], "40")

    def test_percent_delta_is_none_when_base_value_is_zero(self) -> None:
        base_results = {"metrics": {"annual_cooling": 0}}
        scenario_results = {"metrics": {"annual_cooling": 25}}

        rows = parse_simulation_results(base_results, scenario_results)
        by_id = {row["metric_id"]: row for row in rows}

        self.assertEqual(by_id["annual_cooling"]["delta"], 25.0)
        self.assertIsNone(by_id["annual_cooling"]["percent_delta"])

    def test_ui_and_report_layers_share_exact_same_row_shape(self) -> None:
        base_results = {"metrics": {"annual_heating": 1000, "annual_cost": 3000}}
        scenario_results = {"metrics": {"annual_heating": 900, "annual_cost": 2700}}

        ui_rows = build_ui_results_model(base_results, scenario_results)
        report_rows = build_report_results_model(base_results, scenario_results)

        self.assertEqual(ui_rows, report_rows)
        validate_common_result_rows(ui_rows)
        for row in ui_rows:
            self.assertEqual(tuple(row.keys()), COMMON_RESULT_FIELDS)

    def test_cost_summary_uses_direct_annual_cost_when_available(self) -> None:
        rows = parse_simulation_results(
            {"metrics": {"annual_cost": 12000, "total_energy": 40000}},
            {"metrics": {"annual_cost": 10000, "total_energy": 35000}},
        )

        summary = build_cost_summary_from_metrics(rows, energy_unit_cost=0.5, currency="TRY")

        self.assertTrue(summary["has_data"])
        self.assertEqual(summary["method"], "annual_cost")
        self.assertEqual(summary["base_cost"], 12000.0)
        self.assertEqual(summary["scenario_cost"], 10000.0)
        self.assertEqual(summary["delta"], -2000.0)

    def test_cost_summary_falls_back_to_total_energy_estimate(self) -> None:
        rows = parse_simulation_results(
            {"metrics": {"total_energy": 1000}},
            {"metrics": {"total_energy": 800}},
        )

        summary = build_cost_summary_from_metrics(rows, energy_unit_cost=0.25, currency="TRY")

        self.assertTrue(summary["has_data"])
        self.assertEqual(summary["method"], "estimated_from_total_energy")
        self.assertEqual(summary["base_cost"], 250.0)
        self.assertEqual(summary["scenario_cost"], 200.0)
        self.assertEqual(summary["delta"], -50.0)

    def test_cost_summary_returns_explanation_when_data_missing(self) -> None:
        rows = parse_simulation_results(
            {"metrics": {"annual_heating": 100}},
            {"metrics": {"annual_heating": 90}},
        )

        summary = build_cost_summary_from_metrics(rows, energy_unit_cost=0.25, currency="TRY")

        self.assertFalse(summary["has_data"])
        self.assertEqual(summary["method"], "unavailable")
        self.assertTrue(str(summary["message"]).strip())


if __name__ == "__main__":
    unittest.main()
