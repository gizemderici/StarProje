import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from actions.scenario_runner import prepare_scenario_from_definition


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)


class ScenarioRunnerActionTests(unittest.TestCase):
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
            ],
        )

        self.scenario_file = self.root / "scenario.json"
        self.scenario_file.write_text(
            json.dumps(
                {
                    "scenario_name": "materials_upgrade_scenario",
                    "input": str(self.input_path),
                    "output": str(self.root / "placeholder.csv"),
                    "operations": [
                        {
                            "name": "increase_beton_thickness",
                            "match": {"column": "name", "value": "beton"},
                            "updates": {"thickness_m": "0.25"},
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_prepare_scenario_from_definition_writes_audit_events(self) -> None:
        output_root = self.root / "simulation_outputs"
        result = prepare_scenario_from_definition(
            scenario_path=self.scenario_file,
            simulation_output_dir=output_root,
        )

        self.assertTrue(result.output_path.exists())
        self.assertTrue(result.log_output_path.exists())
        self.assertTrue(result.manifest_path.exists())

        root_audit = output_root / "_audit" / "materials_upgrade_scenario__events.jsonl"
        scenario_audit = output_root / "materials_upgrade_scenario" / "audit_events.jsonl"
        self.assertTrue(root_audit.exists())
        self.assertTrue(scenario_audit.exists())

        events = [json.loads(line) for line in scenario_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(events)
        self.assertEqual(events[0]["event_type"], "user_action")
        self.assertEqual(events[-1]["status"], "succeeded")
        self.assertEqual(events[-1]["event_type"], "run_finished")


if __name__ == "__main__":
    unittest.main()
