import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from comparison_model import COMMON_COMPARISON_FIELDS
from simulation_results_parser import COMMON_RESULT_FIELDS
from simulation_runner import run_comparative_simulation


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)


class SimulationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))

        self.input_path = self.root / "materials.csv"
        write_csv(
            self.input_path,
            [
                ["name", "type", "thickness_m", "conductivity_w_per_mk", "thermal_resistance_m2k_per_w"],
                ["beton", "OS_Material", "0.2", "1.75", ""],
                ["tugla", "OS_Material", "0.19", "0.5", ""],
            ],
        )

        self.base_model_path = self.root / "building.osm"
        self.base_model_path.write_text("BASE MODEL CONTENT", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_run_comparative_simulation_creates_baseline_scenario_and_comparison_outputs(self) -> None:
        scenario = {
            "scenario_name": "materials_upgrade_scenario",
            "input": str(self.input_path),
            "output": str(self.root / "placeholder.csv"),
            "log_output": str(self.root / "placeholder.json"),
            "operations": [
                {
                    "name": "increase_beton_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }

        result = run_comparative_simulation(
            scenario=scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        self.assertTrue(result.run_dir.exists())
        self.assertTrue(result.baseline_output.exists())
        self.assertTrue(result.scenario_output.exists())
        self.assertTrue(result.comparison_report.exists())

        comparison = json.loads(result.comparison_report.read_text(encoding="utf-8"))
        self.assertEqual(comparison["summary"]["changed_cell_count"], 1)
        self.assertEqual(comparison["changed_cells"][0]["column"], "thickness_m")
        self.assertEqual(comparison["changed_cells"][0]["baseline_value"], "0.2")
        self.assertEqual(comparison["changed_cells"][0]["scenario_value"], "0.25")
        self.assertIn("metrics", comparison)
        self.assertTrue(comparison["metrics"])
        for row in comparison["metrics"]:
            self.assertEqual(tuple(row.keys()), COMMON_RESULT_FIELDS)
        self.assertIn("comparison_model", comparison)
        self.assertIn("items", comparison["comparison_model"])
        self.assertTrue(comparison["comparison_model"]["items"])
        for item in comparison["comparison_model"]["items"]:
            self.assertEqual(tuple(item.keys()), COMMON_COMPARISON_FIELDS)
        self.assertIn("cost_summary", comparison)

        root_audit = self.root / "scenario_runs" / "_audit" / "materials_upgrade_scenario__events.jsonl"
        run_audit = self.root / "scenario_runs" / "materials_upgrade_scenario" / "audit_events.jsonl"
        self.assertTrue(root_audit.exists())
        self.assertTrue(run_audit.exists())

        run_events = [json.loads(line) for line in run_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(run_events)
        self.assertEqual(run_events[-1]["status"], "succeeded")
        self.assertEqual(run_events[-1]["event_type"], "run_finished")

    def test_run_comparative_simulation_keeps_input_dataset_unchanged(self) -> None:
        original_text = self.input_path.read_text(encoding="utf-8-sig")
        scenario = {
            "scenario_name": "materials_upgrade_scenario",
            "input": str(self.input_path),
            "output": str(self.root / "placeholder.csv"),
            "log_output": str(self.root / "placeholder.json"),
            "operations": [
                {
                    "name": "increase_beton_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }

        run_comparative_simulation(
            scenario=scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        self.assertEqual(self.input_path.read_text(encoding="utf-8-sig"), original_text)

    def test_run_comparative_simulation_writes_error_log_when_scenario_run_fails(self) -> None:
        scenario = {
            "scenario_name": "materials_upgrade_scenario",
            "input": str(self.input_path),
            "output": str(self.root / "placeholder.csv"),
            "log_output": str(self.root / "placeholder.json"),
            "operations": [
                {
                    "name": "invalid_update",
                    "match": {"column": "name", "value": "missing"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }

        with self.assertRaises(Exception):
            run_comparative_simulation(
                scenario=scenario,
                base_model_path=self.base_model_path,
                runs_root=self.root / "scenario_runs",
            )

        error_log = self.root / "scenario_runs" / "materials_upgrade_scenario" / "scenario" / "materials_upgrade_scenario__error.log"
        self.assertTrue(error_log.exists())
        root_audit = self.root / "scenario_runs" / "_audit" / "materials_upgrade_scenario__events.jsonl"
        self.assertTrue(root_audit.exists())
        events = [json.loads(line) for line in root_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(events)
        self.assertEqual(events[-1]["status"], "failed")
        self.assertEqual(events[-1]["event_type"], "run_finished")
        self.assertIn("error", events[-1]["details"])

    def test_run_comparative_simulation_reports_status_history(self) -> None:
        scenario = {
            "scenario_name": "materials_upgrade_scenario",
            "input": str(self.input_path),
            "output": str(self.root / "placeholder.csv"),
            "log_output": str(self.root / "placeholder.json"),
            "operations": [
                {
                    "name": "increase_beton_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }
        received_statuses = []

        result = run_comparative_simulation(
            scenario=scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
            status_callback=lambda event: received_statuses.append(event.status),
        )

        self.assertEqual(received_statuses[0], "hazir")
        self.assertIn("dogrulaniyor", received_statuses)
        self.assertIn("senaryo_hazirlaniyor", received_statuses)
        self.assertIn("model_guncelleniyor", received_statuses)
        self.assertIn("simulasyon_calisiyor", received_statuses)
        self.assertIn("sonuc_okunuyor", received_statuses)
        self.assertEqual(received_statuses[-1], "tamamlandi")
        self.assertEqual(result.status_history[-1].status, "tamamlandi")

    def test_run_comparative_simulation_prefers_json_metric_files_when_present(self) -> None:
        scenario = {
            "scenario_name": "materials_upgrade_scenario",
            "input": str(self.input_path),
            "output": str(self.root / "placeholder.csv"),
            "log_output": str(self.root / "placeholder.json"),
            "operations": [
                {
                    "name": "increase_beton_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }

        result = run_comparative_simulation(
            scenario=scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        baseline_metrics_path = result.baseline_output.parent / "simulation_metrics.json"
        scenario_metrics_path = result.scenario_output.parent / "simulation_metrics.json"
        baseline_metrics_path.write_text(
            json.dumps(
                {
                    "metrics": {
                        "annual_heating": 1000,
                        "annual_cooling": 500,
                        "total_energy": 1500,
                    }
                }
            ),
            encoding="utf-8",
        )
        scenario_metrics_path.write_text(
            json.dumps(
                {
                    "metrics": {
                        "annual_heating": 900,
                        "annual_cooling": 480,
                        "total_energy": 1380,
                    }
                }
            ),
            encoding="utf-8",
        )

        from simulation_runner import compare_run_outputs

        comparison = compare_run_outputs(self.input_path, result.baseline_output, result.scenario_output)
        by_id = {row["metric_id"]: row for row in comparison["metrics"]}

        self.assertEqual(by_id["annual_heating"]["base_value"], 1000)
        self.assertEqual(by_id["annual_heating"]["scenario_value"], 900)
        self.assertEqual(comparison["metric_source"]["status"], "available")
        self.assertEqual(comparison["metric_source"]["baseline"]["source_type"], "json_metrics_file")
        self.assertEqual(comparison["metric_source"]["scenario"]["source_type"], "json_metrics_file")


if __name__ == "__main__":
    unittest.main()
