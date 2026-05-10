import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scenario_model_preparation import (
    ScenarioModelPreparationError,
    prepare_scenario_model_variant,
)


class ScenarioModelPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))

        self.base_model_dir = self.root / "base_model"
        self.base_model_dir.mkdir(parents=True, exist_ok=True)
        self.base_model_path = self.base_model_dir / "building.osm"
        self.base_model_path.write_text("BASE MODEL CONTENT", encoding="utf-8")

        self.csv_dir = self.root / "csv_output"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.csv_input_path = self.csv_dir / "materials.csv"
        self.csv_input_path.write_text("name,thickness_m\nbeton,0.2\n", encoding="utf-8")

        self.scenario = {
            "scenario_name": "materials_upgrade_scenario",
            "input": str(self.csv_input_path),
            "output": str(self.root / "simulation_outputs" / "materials_upgrade_scenario" / "materials.csv"),
            "operations": [
                {
                    "name": "set_material_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_prepare_scenario_model_variant_creates_run_assets(self) -> None:
        result = prepare_scenario_model_variant(
            scenario=self.scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        self.assertTrue(result.workspace.run_dir.exists())
        self.assertTrue(result.scenario_snapshot_path.exists())
        self.assertTrue(result.workspace.base_model_copy.exists())
        self.assertTrue(result.workspace.scenario_model_path.exists())
        self.assertTrue(result.input_csv_copy_path is not None)
        self.assertTrue(result.input_csv_copy_path.exists())
        self.assertEqual(self.base_model_path.read_text(encoding="utf-8"), "BASE MODEL CONTENT")

    def test_prepare_scenario_model_variant_writes_metadata_and_snapshot(self) -> None:
        result = prepare_scenario_model_variant(
            scenario=self.scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        snapshot = json.loads(result.scenario_snapshot_path.read_text(encoding="utf-8"))
        metadata = json.loads(result.workspace.metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["scenario_name"], "materials_upgrade_scenario")
        self.assertEqual(metadata["scenario_name"], "materials_upgrade_scenario")
        self.assertIn("scenario_snapshot_path", metadata)
        self.assertIn("openstudio_available", metadata)

    def test_prepare_scenario_model_variant_requires_scenario_name(self) -> None:
        with self.assertRaises(ScenarioModelPreparationError):
            prepare_scenario_model_variant(
                scenario={"input": str(self.csv_input_path), "operations": []},
                base_model_path=self.base_model_path,
                runs_root=self.root / "scenario_runs",
            )


if __name__ == "__main__":
    unittest.main()
