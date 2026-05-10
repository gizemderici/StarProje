from dataclasses import dataclass
import json
import shutil
from pathlib import Path

from scenario_run_workspace import (
    SCENARIO_RUNS_DIR,
    ScenarioRunWorkspace,
    ScenarioRunWorkspaceError,
    create_scenario_run_workspace,
)


class ScenarioModelPreparationError(Exception):
    pass


@dataclass(frozen=True)
class ScenarioModelPreparation:
    workspace: ScenarioRunWorkspace
    scenario_snapshot_path: Path
    input_csv_copy_path: Path | None
    openstudio_available: bool


def _load_openstudio_module():
    try:
        import openstudio as openstudio  # type: ignore
    except ImportError:
        return None
    return openstudio


def _save_variant_model_with_openstudio(base_model_copy: Path, scenario_model_path: Path) -> bool:
    openstudio = _load_openstudio_module()
    if openstudio is None:
        return False

    translator = openstudio.osversion.VersionTranslator()
    model_optional = translator.loadModel(openstudio.path(str(base_model_copy)))
    if not model_optional.is_initialized():
        return False

    model = model_optional.get()
    if not model.save(openstudio.path(str(scenario_model_path)), True):
        return False
    return True


def prepare_scenario_model_variant(
    scenario: dict[str, object],
    base_model_path: Path | str,
    runs_root: Path | str = SCENARIO_RUNS_DIR,
) -> ScenarioModelPreparation:
    scenario_name = str(scenario.get("scenario_name", "")).strip()
    if not scenario_name:
        raise ScenarioModelPreparationError("Senaryo icinde 'scenario_name' zorunludur.")

    workspace = create_scenario_run_workspace(
        base_model_path=base_model_path,
        scenario_name=scenario_name,
        runs_root=runs_root,
    )

    scenario_snapshot_path = workspace.run_dir / "scenario_definition.json"
    scenario_snapshot_path.write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    input_csv_copy_path = None
    input_csv = str(scenario.get("input", "")).strip()
    if input_csv:
        source_input_path = Path(input_csv)
        if source_input_path.exists() and source_input_path.is_file():
            csv_input_dir = workspace.run_dir / "csv_inputs"
            csv_input_dir.mkdir(parents=True, exist_ok=True)
            input_csv_copy_path = csv_input_dir / source_input_path.name
            shutil.copy2(source_input_path, input_csv_copy_path)

    openstudio_available = _save_variant_model_with_openstudio(
        workspace.base_model_copy,
        workspace.scenario_model_path,
    )

    metadata_path = workspace.metadata_path
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "scenario_snapshot_path": str(scenario_snapshot_path.resolve()),
            "input_csv_copy_path": (
                str(input_csv_copy_path.resolve()) if input_csv_copy_path is not None else ""
            ),
            "openstudio_available": openstudio_available,
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return ScenarioModelPreparation(
        workspace=workspace,
        scenario_snapshot_path=scenario_snapshot_path,
        input_csv_copy_path=input_csv_copy_path,
        openstudio_available=openstudio_available,
    )
