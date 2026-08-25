from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.estimator import EstimatorAssumptions, run_parametric, wall_performance
from engine.openstudio_runner import OpenStudioCase, build_workflow
from engine.parameters import MEASURE_ORDER, REPORTING_MEASURES
from engine.sql_results import ResultsRepository
from engine.star_study import StarStudy


ROOT = Path(__file__).resolve().parents[1]


class ResultsRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = ResultsRepository(ROOT / "data/archived_runs").load()

    def test_archived_scenarios_load(self) -> None:
        self.assertEqual(set(self.repository.scenarios), {5, 10, 15})
        self.assertAlmostEqual(self.repository.scenarios[5].site_energy_gj, 1941.59)
        self.assertEqual(self.repository.scenarios[5].run_status, "Success")

    def test_original_scenarios_are_identical(self) -> None:
        self.assertTrue(self.repository.archived_runs_are_identical)

    def test_annual_monthly_data_excludes_design_days(self) -> None:
        electricity = sum(
            self.repository.scenarios[5].monthly_gj["Electricity:Facility"]
        )
        gas = sum(self.repository.scenarios[5].monthly_gj["NaturalGas:Facility"])
        self.assertGreater(electricity, 1800)
        self.assertLess(electricity, 2000)
        self.assertGreater(gas, 30)
        self.assertLess(gas, 50)


class EstimatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = ResultsRepository(ROOT / "data/archived_runs").load().scenarios[5]

    def test_wall_u_value_decreases_with_thickness(self) -> None:
        _r5, u5 = wall_performance(5, 0.039)
        _r15, u15 = wall_performance(15, 0.039)
        self.assertLess(u15, u5)

    def test_parametric_energy_is_monotonic(self) -> None:
        points = run_parametric(
            [5, 10, 15, 20], self.baseline, EstimatorAssumptions()
        )
        self.assertEqual(points[0].savings_percent, 0.0)
        self.assertEqual(
            [point.site_energy_gj for point in points],
            sorted((point.site_energy_gj for point in points), reverse=True),
        )


MEASURES_ROOT = ROOT / "integrations/OpenStudio/Measures"


class WorkflowTests(unittest.TestCase):
    def _build(self, case: OpenStudioCase) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            workflow = build_workflow(
                case,
                ROOT / "data/input/gsf_fng_6mayis_onarilmis.osm",
                ROOT / "data/input/weather_tmyx.epw",
                ROOT / "integrations/OpenStudio/Measures",
                Path(temp),
            )
            return json.loads(workflow.read_text(encoding="utf-8"))

    def test_workflow_contains_every_measure_in_order(self) -> None:
        payload = self._build(OpenStudioCase({"eps_thickness_cm": 12}))
        names = [step["measure_dir_name"] for step in payload["steps"]]
        # Beklenen liste kayittan turetilir; yeni bir karar degiskeni eklenince
        # test kendiliginden guncel kalir.
        self.assertEqual(names, list(MEASURE_ORDER) + list(REPORTING_MEASURES))
        self.assertTrue(
            all((MEASURES_ROOT / name).is_dir() for name in names),
            "OSW adimlarindan biri icin measure klasoru yok.",
        )
        self.assertEqual(payload["steps"][0]["arguments"]["eps_thickness_cm"], 12)

    def test_unspecified_parameters_fall_back_to_baseline(self) -> None:
        payload = self._build(OpenStudioCase({"eps_thickness_cm": 12}))
        setpoints = next(
            step for step in payload["steps"]
            if step["measure_dir_name"] == "SetThermostatSetpoints"
        )
        self.assertEqual(setpoints["arguments"]["heating_setpoint_c"], 22.0)
        self.assertEqual(setpoints["arguments"]["cooling_setpoint_c"], 24.0)

    def test_case_id_is_stable_and_order_independent(self) -> None:
        first = OpenStudioCase({"chiller_cop": 4.0, "cooling_setpoint_c": 26.0})
        second = OpenStudioCase({"cooling_setpoint_c": 26.0, "chiller_cop": 4.0})
        self.assertEqual(first.case_id, second.case_id)
        self.assertNotEqual(first.case_id, OpenStudioCase().case_id)

    def test_unknown_parameter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpenStudioCase({"bilinmeyen_parametre": 1.0})

    def test_out_of_range_parameter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpenStudioCase({"chiller_cop": 99.0})

    def test_unknown_window_construction_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpenStudioCase({"window_construction": "olmayan_cam"})


class StarStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.study = StarStudy(ROOT / "data/star_study").load()

    def test_scenario_inventory_and_deduplication(self) -> None:
        self.assertEqual(len(self.study.scenarios), 20)
        self.assertEqual(len(self.study.unique_scenarios), 14)
        self.assertEqual(self.study.duplicate_count, 6)

    def test_baseline_is_better_than_tested_alternatives(self) -> None:
        self.assertAlmostEqual(self.study.baseline.hvac_gj, 31.82)
        self.assertAlmostEqual(self.study.best_tested.hvac_gj, 33.08)
        self.assertTrue(self.study.baseline_beats_all_tested)

    def test_summary_matches_verified_sql(self) -> None:
        verified = self.study.validate_sql()
        self.assertAlmostEqual(verified["baseline"]["heating_gj"], self.study.baseline.heating_gj)
        self.assertAlmostEqual(verified["best_tested"]["cooling_gj"], self.study.best_tested.cooling_gj)


if __name__ == "__main__":
    unittest.main()
