from dataclasses import asdict, dataclass
from datetime import datetime
import json
import shutil
from pathlib import Path

from scenario_builder import sanitize_scenario_name


SCENARIO_RUNS_DIR = Path("scenario_runs")


class ScenarioRunWorkspaceError(Exception):
    pass


@dataclass(frozen=True)
class ScenarioRunWorkspace:
    scenario_name: str
    run_dir: Path
    base_model_source: Path
    base_model_copy: Path
    scenario_model_path: Path
    metadata_path: Path


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _build_variant_model_name(base_model_path: Path, scenario_name: str) -> str:
    return f"{base_model_path.stem}__{scenario_name}{base_model_path.suffix}"


def create_scenario_run_workspace(
    base_model_path: Path | str,
    scenario_name: str,
    runs_root: Path | str = SCENARIO_RUNS_DIR,
) -> ScenarioRunWorkspace:
    source_model_path = Path(base_model_path)
    if not source_model_path.exists():
        raise ScenarioRunWorkspaceError(f"Baz model bulunamadi: {source_model_path}")
    if not source_model_path.is_file():
        raise ScenarioRunWorkspaceError(f"Baz model bir dosya olmali: {source_model_path}")

    normalized_scenario_name = sanitize_scenario_name(scenario_name)
    run_dir = Path(runs_root) / normalized_scenario_name
    models_dir = run_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    base_model_copy = models_dir / source_model_path.name
    scenario_model_path = models_dir / _build_variant_model_name(
        source_model_path,
        normalized_scenario_name,
    )

    shutil.copy2(source_model_path, base_model_copy)
    shutil.copy2(base_model_copy, scenario_model_path)

    metadata_path = run_dir / "run_metadata.json"
    metadata = {
        "scenario_name": normalized_scenario_name,
        "created_at": _timestamp(),
        "base_model_source": str(source_model_path.resolve()),
        "base_model_copy": str(base_model_copy.resolve()),
        "scenario_model_path": str(scenario_model_path.resolve()),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return ScenarioRunWorkspace(
        scenario_name=normalized_scenario_name,
        run_dir=run_dir,
        base_model_source=source_model_path,
        base_model_copy=base_model_copy,
        scenario_model_path=scenario_model_path,
        metadata_path=metadata_path,
    )


def export_scenario_run_workspace(workspace: ScenarioRunWorkspace) -> dict[str, str]:
    exported = asdict(workspace)
    return {
        key: str(value) if isinstance(value, Path) else str(value)
        for key, value in exported.items()
    }
