from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.estimator import EstimatorAssumptions, run_parametric, wall_performance
from engine.openstudio_runner import OpenStudioCase, build_workflow
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


class WorkflowTests(unittest.TestCase):
    def test_workflow_uses_eps_measure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workflow = build_workflow(
                OpenStudioCase(thickness_cm=12),
                ROOT / "data/input/bina_orijinal.osm",
                ROOT / "data/input/weather.epw",
                ROOT / "integrations/OpenStudio/Measures",
                Path(temp),
            )
            payload = json.loads(workflow.read_text(encoding="utf-8"))
        self.assertEqual(payload["steps"][0]["measure_dir_name"], "SetEpsThickness")
        self.assertEqual(payload["steps"][0]["arguments"]["eps_thickness_cm"], 12)


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
