from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from audit_trail import build_audit_event, build_audit_paths, write_audit_event
from apply_scenario_definition import load_scenario_definition, run_scenario_definition
from build_simulation_output import build_manifest, build_output_paths, write_manifest


@dataclass(frozen=True)
class ScenarioPreparationResult:
    scenario_name: str
    output_path: Path
    log_output_path: Path
    manifest_path: Path
    change_count: int


def prepare_scenario_from_definition(
    scenario_path: Path,
    simulation_output_dir: Path,
) -> ScenarioPreparationResult:
    scenario = load_scenario_definition(scenario_path)
    scenario_copy = deepcopy(scenario)
    scenario_name = str(scenario_copy["scenario_name"])
    input_path = Path(scenario_copy["input"])

    data_output, log_output, manifest_output = build_output_paths(
        scenario_name,
        input_path,
        simulation_output_dir,
    )
    scenario_dir = data_output.parent
    audit_paths = build_audit_paths(
        root_dir=simulation_output_dir,
        scenario_name=scenario_name,
        scenario_dir=scenario_dir,
    )
    write_audit_event(
        audit_paths,
        build_audit_event(
            event_type="user_action",
            scenario_name=scenario_name,
            status="started",
            source="ui",
            message="Scenario preparation requested from definition.",
            details={
                "scenario_file": str(scenario_path),
                "input_dataset": str(input_path),
            },
        ),
    )

    scenario_copy["output"] = str(data_output)
    scenario_copy["log_output"] = str(log_output)

    try:
        output_path, written_log_output, change_count = run_scenario_definition(scenario_copy)
        manifest = build_manifest(
            scenario_copy,
            scenario_path,
            input_path,
            output_path,
            written_log_output,
            change_count,
        )
        write_manifest(manifest_output, manifest)
        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="run_finished",
                scenario_name=scenario_name,
                status="succeeded",
                source="runner",
                message="Scenario preparation package created.",
                details={
                    "output_dataset": str(output_path),
                    "log_output": str(written_log_output),
                    "manifest": str(manifest_output),
                    "changed_field_count": change_count,
                },
            ),
        )
    except Exception as error:
        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="run_finished",
                scenario_name=scenario_name,
                status="failed",
                source="runner",
                message="Scenario preparation failed.",
                details={
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            ),
        )
        raise

    return ScenarioPreparationResult(
        scenario_name=scenario_name,
        output_path=output_path,
        log_output_path=written_log_output,
        manifest_path=manifest_output,
        change_count=change_count,
    )
