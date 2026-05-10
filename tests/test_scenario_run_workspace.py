import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scenario_run_workspace import (
    ScenarioRunWorkspaceError,
    create_scenario_run_workspace,
    export_scenario_run_workspace,
)


class ScenarioRunWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))
        self.base_model_dir = self.root / "base_model"
        self.base_model_dir.mkdir(parents=True, exist_ok=True)
        self.base_model_path = self.base_model_dir / "building.osm"
        self.base_model_path.write_text("BASE MODEL CONTENT", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_create_scenario_run_workspace_keeps_base_model_unchanged(self) -> None:
        workspace = create_scenario_run_workspace(
            base_model_path=self.base_model_path,
            scenario_name="Facade Upgrade Option A",
            runs_root=self.root / "scenario_runs",
        )

        self.assertEqual(
            self.base_model_path.read_text(encoding="utf-8"),
            "BASE MODEL CONTENT",
        )
        self.assertTrue(workspace.run_dir.exists())
        self.assertTrue(workspace.base_model_copy.exists())
        self.assertTrue(workspace.scenario_model_path.exists())
        self.assertEqual(
            workspace.base_model_copy.read_text(encoding="utf-8"),
            "BASE MODEL CONTENT",
        )
        self.assertEqual(
            workspace.scenario_model_path.read_text(encoding="utf-8"),
            "BASE MODEL CONTENT",
        )
        self.assertIn("scenario_runs", workspace.run_dir.as_posix())
        self.assertTrue(workspace.scenario_name.startswith("Facade_Upgrade_Option_A"))

    def test_workspace_creates_metadata_file(self) -> None:
        workspace = create_scenario_run_workspace(
            base_model_path=self.base_model_path,
            scenario_name="thermal retrofit",
            runs_root=self.root / "scenario_runs",
        )

        metadata = json.loads(workspace.metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["scenario_name"], "thermal_retrofit")
        self.assertIn("base_model_source", metadata)
        self.assertIn("scenario_model_path", metadata)

    def test_export_workspace_returns_stringified_paths(self) -> None:
        workspace = create_scenario_run_workspace(
            base_model_path=self.base_model_path,
            scenario_name="window upgrade",
            runs_root=self.root / "scenario_runs",
        )

        exported = export_scenario_run_workspace(workspace)
        self.assertEqual(exported["scenario_name"], "window_upgrade")
        self.assertTrue(exported["run_dir"].endswith("scenario_runs\\window_upgrade") or exported["run_dir"].endswith("scenario_runs/window_upgrade"))

    def test_missing_base_model_raises_error(self) -> None:
        with self.assertRaises(ScenarioRunWorkspaceError):
            create_scenario_run_workspace(
                base_model_path=self.root / "missing.osm",
                scenario_name="invalid",
                runs_root=self.root / "scenario_runs",
            )


if __name__ == "__main__":
    unittest.main()
