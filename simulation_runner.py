import argparse
from copy import deepcopy
import json
import re
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from audit_trail import build_audit_event, build_audit_paths, write_audit_event
from apply_scenario_definition import load_scenario_definition, run_scenario_definition
from build_simulation_output import build_manifest, write_manifest
from comparison_model import build_unified_comparison_model, validate_common_comparison_items
from extract_simulation_metrics import discover_simulation_metrics_payload
from simulation_results_parser import METRIC_SPECS, parse_simulation_results, validate_common_result_rows
from simulation_results_parser import build_cost_summary_from_metrics
from scenario_model_preparation import (
    ScenarioModelPreparation,
    ScenarioModelPreparationError,
    prepare_scenario_model_variant,
)
from scenario_run_workspace import SCENARIO_RUNS_DIR
from update_csv_fields import CsvUpdateError, get_log_output_path, get_file_rules, load_rows, write_change_log, write_rows


class SimulationRunnerError(Exception):
    pass


RUNNER_STATUS_ORDER = [
    "hazir",
    "dogrulaniyor",
    "senaryo_hazirlaniyor",
    "model_guncelleniyor",
    "simulasyon_calisiyor",
    "sonuc_okunuyor",
    "tamamlandi",
    "hata",
]

RUNNER_STATUS_LABELS = {
    "hazir": "Hazir",
    "dogrulaniyor": "Dogrulaniyor",
    "senaryo_hazirlaniyor": "Senaryo Hazirlaniyor",
    "model_guncelleniyor": "Model Guncelleniyor",
    "simulasyon_calisiyor": "Simulasyon Calisiyor",
    "sonuc_okunuyor": "Sonuc Okunuyor",
    "tamamlandi": "Tamamlandi",
    "hata": "Hata",
}


@dataclass(frozen=True)
class RunnerStatusEvent:
    status: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class ComparativeSimulationResult:
    run_dir: Path
    baseline_output: Path
    baseline_log: Path
    scenario_output: Path
    scenario_log: Path
    comparison_report: Path
    preparation: ScenarioModelPreparation | None
    status_history: list[RunnerStatusEvent] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baseline ve senaryo ciktilarini ayri klasorlerde uretip karsilastirma raporu yazar."
    )
    parser.add_argument("--scenario-file", required=True, help="Calistirilacak senaryo dosyasi.")
    parser.add_argument("--base-model", help="Baz OSM model yolu.")
    parser.add_argument("--runs-root", default=str(SCENARIO_RUNS_DIR), help="scenario_runs kok klasoru.")
    return parser.parse_args()


def _build_run_paths(run_dir: Path, scenario_name: str, input_path: Path) -> dict[str, Path]:
    baseline_dir = run_dir / "baseline"
    scenario_dir = run_dir / "scenario"
    comparison_dir = run_dir / "comparison"

    return {
        "baseline_dir": baseline_dir,
        "scenario_dir": scenario_dir,
        "comparison_dir": comparison_dir,
        "baseline_output": baseline_dir / f"baseline__{input_path.stem}.csv",
        "baseline_log": baseline_dir / "baseline__changes.json",
        "baseline_manifest": baseline_dir / "baseline__manifest.json",
        "baseline_error_log": baseline_dir / "baseline__error.log",
        "scenario_output": scenario_dir / f"{scenario_name}__{input_path.stem}.csv",
        "scenario_log": scenario_dir / f"{scenario_name}__changes.json",
        "scenario_manifest": scenario_dir / f"{scenario_name}__manifest.json",
        "scenario_error_log": scenario_dir / f"{scenario_name}__error.log",
        "comparison_report": comparison_dir / f"{scenario_name}__comparison.json",
        "comparison_error_log": comparison_dir / f"{scenario_name}__comparison_error.log",
    }


def _write_error_log(path: Path, error: Exception) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{type(error).__name__}: {error}\n\n{traceback.format_exc()}",
        encoding="utf-8",
    )


def _run_baseline_output(input_path: Path, output_path: Path, log_path: Path) -> int:
    rows, fieldnames = load_rows(input_path)
    write_rows(output_path, rows, fieldnames)
    write_change_log(log_path, [])
    return 0


def _notify_status(
    callback: Callable[[RunnerStatusEvent], None] | None,
    history: list[RunnerStatusEvent],
    status: str,
    detail: str = "",
) -> None:
    event = RunnerStatusEvent(
        status=status,
        label=RUNNER_STATUS_LABELS.get(status, status.replace("_", " ").title()),
        detail=detail,
    )
    history.append(event)
    if callback is not None:
        callback(event)


def _build_row_map(rows: list[dict], key_columns: list[str]) -> dict[tuple[str, ...], dict]:
    row_map = {}
    for row in rows:
        key = tuple(str(row.get(column, "")).strip() for column in key_columns)
        if key in row_map:
            raise SimulationRunnerError(f"Karsilastirma anahtari tekrarli: {' | '.join(key)}")
        row_map[key] = row
    return row_map


def _extract_metric_source(rows: list[dict], fieldnames: list[str]) -> dict[str, object]:
    if not rows:
        return {}

    first_row = rows[0]
    source: dict[str, object] = {}
    for field in fieldnames:
        if field == "__row_number":
            continue
        source[field] = first_row.get(field, "")
    return source


def _load_json_if_exists(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_metric_payload_from_output_dir(output_path: Path) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    output_dir = output_path.parent
    stem = output_path.stem
    candidates = [
        output_dir / f"{stem}__simulation_metrics.json",
        output_dir / f"{stem}__results.json",
        output_dir / "simulation_metrics.json",
        output_dir / "results.json",
    ]
    for candidate in candidates:
        payload = _load_json_if_exists(candidate)
        if payload is not None:
            return payload, {
                "source_type": "json_metrics_file",
                "path": candidate.as_posix(),
            }
    discovered_payload = discover_simulation_metrics_payload(output_dir)
    if discovered_payload is not None:
        persisted_path = output_dir / "simulation_metrics.json"
        persisted_path.write_text(json.dumps(discovered_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return discovered_payload, {
            "source_type": str(discovered_payload.get("source_type", "json_scan")),
            "path": persisted_path.as_posix(),
        }
    return None, None


def _normalize_metric_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _build_metric_source_metadata(
    rows: list[dict],
    fieldnames: list[str],
    *,
    source_type: str = "csv_first_row",
    source_path: str = "",
) -> dict[str, object]:
    normalized_fields = {
        _normalize_metric_key(field)
        for field in fieldnames
        if str(field).strip() and str(field).strip() != "__row_number"
    }
    recognized_metric_ids: list[str] = []
    for spec in METRIC_SPECS:
        if any(_normalize_metric_key(alias) in normalized_fields for alias in spec.aliases):
            recognized_metric_ids.append(spec.metric_id)

    if not rows:
        return {
            "status": "unavailable",
            "row_count": 0,
            "recognized_metric_ids": [],
            "fieldnames": [field for field in fieldnames if field != "__row_number"],
            "source_type": source_type,
            "source_path": source_path,
            "message": "Output dosyasinda karsilastirilacak satir yok; simulasyon metrik kaynagi bulunamadi.",
        }

    if recognized_metric_ids:
        return {
            "status": "available",
            "row_count": len(rows),
            "recognized_metric_ids": recognized_metric_ids,
            "fieldnames": [field for field in fieldnames if field != "__row_number"],
            "source_type": source_type,
            "source_path": source_path,
            "message": "Output dosyasinda simulasyon metrik alanlari algilandi.",
        }

    return {
        "status": "unavailable",
        "row_count": len(rows),
        "recognized_metric_ids": [],
        "fieldnames": [field for field in fieldnames if field != "__row_number"],
        "source_type": source_type,
        "source_path": source_path,
        "message": (
            "Karsilastirilan output dosyasinda annual_heating/annual_cooling gibi simulasyon "
            "metrik alanlari yok; rapor su an sadece CSV farklarini ve degisen hucreleri gosteriyor."
        ),
    }


def compare_run_outputs(input_dataset_path: Path, baseline_output: Path, scenario_output: Path) -> dict[str, object]:
    rules = get_file_rules(input_dataset_path)
    baseline_rows, baseline_fieldnames = load_rows(baseline_output)
    scenario_rows, scenario_fieldnames = load_rows(scenario_output)
    key_columns = sorted(rules["key_columns"])

    baseline_map = _build_row_map(baseline_rows, key_columns)
    scenario_map = _build_row_map(scenario_rows, key_columns)
    comparable_columns = sorted((set(baseline_fieldnames) | set(scenario_fieldnames)) - {"__row_number"})

    changed_cells = []
    added_rows = []
    removed_rows = []

    baseline_keys = set(baseline_map)
    scenario_keys = set(scenario_map)

    for key in sorted(scenario_keys - baseline_keys):
        added_rows.append({"row_key": " | ".join(key)})
    for key in sorted(baseline_keys - scenario_keys):
        removed_rows.append({"row_key": " | ".join(key)})

    for key in sorted(baseline_keys & scenario_keys):
        baseline_row = baseline_map[key]
        scenario_row = scenario_map[key]
        for column in comparable_columns:
            baseline_value = str(baseline_row.get(column, ""))
            scenario_value = str(scenario_row.get(column, ""))
            if baseline_value == scenario_value:
                continue
            changed_cells.append(
                {
                    "row_key": " | ".join(key),
                    "column": column,
                    "baseline_value": baseline_value,
                    "scenario_value": scenario_value,
                }
            )

    baseline_metric_source = _extract_metric_source(baseline_rows, baseline_fieldnames)
    scenario_metric_source = _extract_metric_source(scenario_rows, scenario_fieldnames)
    baseline_metric_source_meta = _build_metric_source_metadata(
        baseline_rows,
        baseline_fieldnames,
        source_type="csv_first_row",
        source_path=baseline_output.as_posix(),
    )
    scenario_metric_source_meta = _build_metric_source_metadata(
        scenario_rows,
        scenario_fieldnames,
        source_type="csv_first_row",
        source_path=scenario_output.as_posix(),
    )

    baseline_metric_payload, baseline_metric_file_meta = _load_metric_payload_from_output_dir(baseline_output)
    if baseline_metric_payload is not None:
        baseline_metric_source = dict(baseline_metric_payload.get("metrics", baseline_metric_payload))
        baseline_metric_source_meta = _build_metric_source_metadata(
            [baseline_metric_source],
            list(baseline_metric_source.keys()),
            source_type=str((baseline_metric_file_meta or {}).get("source_type", "json_metrics_file")),
            source_path=str((baseline_metric_file_meta or {}).get("path", "")),
        )

    scenario_metric_payload, scenario_metric_file_meta = _load_metric_payload_from_output_dir(scenario_output)
    if scenario_metric_payload is not None:
        scenario_metric_source = dict(scenario_metric_payload.get("metrics", scenario_metric_payload))
        scenario_metric_source_meta = _build_metric_source_metadata(
            [scenario_metric_source],
            list(scenario_metric_source.keys()),
            source_type=str((scenario_metric_file_meta or {}).get("source_type", "json_metrics_file")),
            source_path=str((scenario_metric_file_meta or {}).get("path", "")),
        )

    baseline_metrics_payload = (
        {"metrics": baseline_metric_source}
        if baseline_metric_source_meta.get("status") == "available"
        else {"metrics": {}}
    )
    scenario_metrics_payload = (
        {"metrics": scenario_metric_source}
        if scenario_metric_source_meta.get("status") == "available"
        else {"metrics": {}}
    )

    if (
        baseline_metric_source_meta.get("status") == "available"
        and scenario_metric_source_meta.get("status") == "available"
    ):
        metric_source_status = "available"
        metric_source_message = "Comparison raporu gercek simulasyon metriklerini de iceriyor."
    elif (
        baseline_metric_source_meta.get("status") == "available"
        or scenario_metric_source_meta.get("status") == "available"
    ):
        metric_source_status = "partial"
        metric_source_message = (
            "Comparison raporunda simulasyon metrikleri kismen bulundu; bazi old/new metrikleri eksik olabilir."
        )
    else:
        metric_source_status = "unavailable"
        metric_source_message = (
            "Comparison raporu olustu, ancak bu rapor gercek simulasyon metrikleri icermiyor. "
            "Rapor su an agirlikla CSV farklari ve degisen hucreler uzerinden olustu."
        )

    metrics = parse_simulation_results(
        baseline_metrics_payload,
        scenario_metrics_payload,
    )
    validate_common_result_rows(metrics)
    cost_summary = build_cost_summary_from_metrics(metrics)
    unified_comparison = build_unified_comparison_model(
        changed_cells=changed_cells,
        metric_rows=metrics,
        cost_summary=cost_summary,
    )
    validate_common_comparison_items(unified_comparison["items"])

    return {
        "input_dataset": str(input_dataset_path),
        "baseline_output": str(baseline_output),
        "scenario_output": str(scenario_output),
        "summary": {
            "added_row_count": len(added_rows),
            "removed_row_count": len(removed_rows),
            "changed_cell_count": len(changed_cells),
        },
        "added_rows": added_rows,
        "removed_rows": removed_rows,
        "changed_cells": changed_cells,
        "metrics": metrics,
        "metric_source": {
            "status": metric_source_status,
            "message": metric_source_message,
            "baseline": baseline_metric_source_meta,
            "scenario": scenario_metric_source_meta,
        },
        "cost_summary": cost_summary,
        "comparison_model": unified_comparison,
    }


def run_comparative_simulation(
    scenario: dict[str, object],
    base_model_path: Path | str | None = None,
    runs_root: Path | str = SCENARIO_RUNS_DIR,
    status_callback: Callable[[RunnerStatusEvent], None] | None = None,
    source: str = "system",
) -> ComparativeSimulationResult:
    scenario_copy = deepcopy(scenario)
    status_history: list[RunnerStatusEvent] = []
    current_phase = "validation"
    _notify_status(status_callback, status_history, "hazir", "Calistirma istegi alindi.")
    scenario_name = str(scenario_copy.get("scenario_name", "")).strip()
    runs_root_path = Path(runs_root)
    audit_paths = build_audit_paths(
        root_dir=runs_root_path,
        scenario_name=scenario_name or "unknown_scenario",
    )
    write_audit_event(
        audit_paths,
        build_audit_event(
            event_type="user_action",
            scenario_name=scenario_name or "unknown_scenario",
            status="started",
            source=source,
            message="Comparative simulation requested.",
            details={
                "has_base_model": bool(base_model_path),
                "runs_root": str(runs_root_path),
            },
        ),
    )
    try:
        _notify_status(status_callback, status_history, "dogrulaniyor", "Senaryo ve girdi dosyalari kontrol ediliyor.")
        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="status_change",
                scenario_name=scenario_name or "unknown_scenario",
                status="dogrulaniyor",
                source="runner",
                message="Scenario validation started.",
            ),
        )
        if not scenario_name:
            raise SimulationRunnerError("Senaryo icinde 'scenario_name' zorunludur.")

        input_path = Path(str(scenario_copy.get("input", "")).strip())
        if not input_path.exists():
            raise SimulationRunnerError(f"Senaryo girdisi bulunamadi: {input_path}")

        preparation = None
        if base_model_path:
            _notify_status(
                status_callback,
                status_history,
                "senaryo_hazirlaniyor",
                "Scenario run klasoru ve model kopyalari hazirlaniyor.",
            )
            try:
                preparation = prepare_scenario_model_variant(
                    scenario=scenario_copy,
                    base_model_path=base_model_path,
                    runs_root=runs_root,
                )
                run_dir = preparation.workspace.run_dir
                audit_paths = build_audit_paths(
                    root_dir=runs_root_path,
                    scenario_name=scenario_name,
                    scenario_dir=run_dir,
                )
            except ScenarioModelPreparationError as error:
                raise SimulationRunnerError(str(error)) from error
            _notify_status(
                status_callback,
                status_history,
                "model_guncelleniyor",
                (
                    "OpenStudio ile varyant model kaydedildi."
                    if preparation.openstudio_available
                    else "Model workspace kopya modunda hazirlandi."
                ),
            )
        else:
            _notify_status(
                status_callback,
                status_history,
                "senaryo_hazirlaniyor",
                "Baz model verilmedi; yalnizca run klasoru hazirlaniyor.",
            )
            run_dir = Path(runs_root) / scenario_name
            run_dir.mkdir(parents=True, exist_ok=True)
            _notify_status(
                status_callback,
                status_history,
                "model_guncelleniyor",
                "CSV tabanli senaryo ciktilari icin run klasoru olusturuldu.",
            )
            audit_paths = build_audit_paths(
                root_dir=runs_root_path,
                scenario_name=scenario_name,
                scenario_dir=run_dir,
            )

        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="status_change",
                scenario_name=scenario_name,
                status="simulasyon_calisiyor",
                source="runner",
                message="Baseline and scenario runs are being generated.",
            ),
        )

        paths = _build_run_paths(run_dir, scenario_name, input_path)
        current_phase = "baseline"
        _notify_status(
            status_callback,
            status_history,
            "simulasyon_calisiyor",
            "Baseline ve senaryo ciktilari uretiliyor.",
        )
        _run_baseline_output(input_path, paths["baseline_output"], paths["baseline_log"])
        baseline_manifest = build_manifest(
            {
                "scenario_name": f"{scenario_name}_baseline",
                "operations": [],
            },
            Path("baseline"),
            input_path,
            paths["baseline_output"],
            paths["baseline_log"],
            0,
        )
        write_manifest(paths["baseline_manifest"], baseline_manifest)
        current_phase = "scenario"
        scenario_copy["output"] = str(paths["scenario_output"])
        scenario_copy["log_output"] = str(paths["scenario_log"])
        output_path, written_log_path, change_count = run_scenario_definition(scenario_copy)
        scenario_manifest = build_manifest(
            scenario_copy,
            Path("scenario"),
            input_path,
            output_path,
            written_log_path,
            change_count,
        )
        write_manifest(paths["scenario_manifest"], scenario_manifest)

        _notify_status(
            status_callback,
            status_history,
            "sonuc_okunuyor",
            "Karsilastirma raporu hazirlaniyor.",
        )
        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="status_change",
                scenario_name=scenario_name,
                status="sonuc_okunuyor",
                source="runner",
                message="Comparison report generation started.",
            ),
        )
        current_phase = "comparison"
        comparison_report = compare_run_outputs(
            input_path,
            paths["baseline_output"],
            paths["scenario_output"],
        )
        paths["comparison_report"].parent.mkdir(parents=True, exist_ok=True)
        paths["comparison_report"].write_text(
            json.dumps(comparison_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _notify_status(
            status_callback,
            status_history,
            "tamamlandi",
            "Baseline ve senaryo sonuclari karsilastirildi.",
        )
        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="run_finished",
                scenario_name=scenario_name,
                status="succeeded",
                source="runner",
                message="Comparative simulation completed.",
                details={
                    "run_dir": str(run_dir),
                    "comparison_report": str(paths["comparison_report"]),
                    "status_history": [event.status for event in status_history],
                },
            ),
        )
    except Exception as error:
        if "paths" in locals():
            if current_phase == "baseline":
                _write_error_log(paths["baseline_error_log"], error)
            elif current_phase == "scenario":
                _write_error_log(paths["scenario_error_log"], error)
            elif current_phase == "comparison":
                _write_error_log(paths["comparison_error_log"], error)
        _notify_status(
            status_callback,
            status_history,
            "hata",
            str(error),
        )
        write_audit_event(
            audit_paths,
            build_audit_event(
                event_type="run_finished",
                scenario_name=scenario_name or "unknown_scenario",
                status="failed",
                source="runner",
                message="Comparative simulation failed.",
                details={
                    "phase": current_phase,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            ),
        )
        raise

    return ComparativeSimulationResult(
        run_dir=run_dir,
        baseline_output=paths["baseline_output"],
        baseline_log=paths["baseline_log"],
        scenario_output=paths["scenario_output"],
        scenario_log=paths["scenario_log"],
        comparison_report=paths["comparison_report"],
        preparation=preparation,
        status_history=status_history,
    )


def run_comparative_simulation_from_file(
    scenario_file: Path | str,
    base_model_path: Path | str | None = None,
    runs_root: Path | str = SCENARIO_RUNS_DIR,
) -> ComparativeSimulationResult:
    scenario = load_scenario_definition(Path(scenario_file))
    return run_comparative_simulation(
        scenario=scenario,
        base_model_path=base_model_path,
        runs_root=runs_root,
    )


def main() -> int:
    args = parse_args()
    try:
        result = run_comparative_simulation_from_file(
            scenario_file=args.scenario_file,
            base_model_path=args.base_model,
            runs_root=args.runs_root,
        )
        print(
            "Karsilastirmali simulasyon tamamlandi. "
            f"Run klasoru: {result.run_dir}. "
            f"Baseline: {result.baseline_output}. "
            f"Scenario: {result.scenario_output}. "
            f"Comparison: {result.comparison_report}"
        )
        return 0
    except (SimulationRunnerError, CsvUpdateError) as error:
        print(f"Hata: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
