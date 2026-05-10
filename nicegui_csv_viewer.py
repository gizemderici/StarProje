import csv
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
import json
import logging
from pathlib import Path
import re
import socket
from urllib.parse import quote, urlencode

from nicegui import ui
from nicegui import run as nicegui_run
from overlay_chart_model import (
    BASE_SCENARIO_ALIAS_TEXT,
    BASE_SCENARIO_LABEL,
    build_overlay_chart_model,
    build_parameter_value_overlay_model,
    overlay_chart_model_to_echart_series,
)

from analyze_csv_dependencies import CsvRepository, DependencyAnalysisError
from dependency_analysis_service import (
    analyze_dependency_for_match,
    analyze_specific_row,
    build_dependency_service_model_for_row,
)
from apply_scenario_definition import load_scenario_definition, run_scenario_definition
from build_simulation_output import build_manifest, build_output_paths, write_manifest
from parameter_catalog import (
    DATASET_KEY_COLUMNS,
    ParameterDefinition,
    build_parameter_groups_for_ui,
    list_parameter_definitions,
)
from parameter_explanations import build_parameter_explanation
from scenario_builder import (
    SelectedParameterChange,
    build_apply_scenario_definition_payload,
    build_scenario_from_selected_changes,
    sanitize_scenario_name,
)
from scenario_management import (
    build_copied_scenario_definition,
    build_multi_scenario_chart_model,
    build_multi_scenario_commentary,
    build_multi_scenario_comparison_rows,
    build_multi_scenario_decision_commentary,
    build_multi_scenario_score_rows,
    build_renamed_scenario_definition,
    build_scenario_diff_rows,
    build_version_history_entries,
    ensure_management_metadata,
    filter_multi_scenario_comparison_rows,
    filter_scenario_diff_rows,
)
from actions.scenario_runner import prepare_scenario_from_definition
from scenario_model_preparation import (
    ScenarioModelPreparationError,
    prepare_scenario_model_variant,
)
from simulation_results_parser import build_cost_summary_from_metrics
from simulation_runner import (
    RUNNER_STATUS_LABELS,
    RUNNER_STATUS_ORDER,
    RunnerStatusEvent,
    SimulationRunnerError,
    run_comparative_simulation,
)
from scenario_run_workspace import SCENARIO_RUNS_DIR, ScenarioRunWorkspaceError
from update_csv_fields import CsvUpdateError, SUPPORTED_FILES
from view_models.comparison_reports import (
    EXPECTED_COMPARISON_METRIC_IDS,
    build_run_to_run_trend_model,
    list_preparation_only_scenarios,
    read_comparison_report_entries as load_comparison_report_entries,
)
from view_models.parameter_effects import (
    PARAMETER_IMPACT_DIMENSIONS,
    analyze_parameter_change_state,
    build_change_direction_badge,
    build_change_strength_badge,
    build_change_summary_card_classes,
    build_change_summary_icon,
    build_multi_parameter_impact_chart_options,
    build_parameter_change_summary_text,
    build_parameter_expected_effect_text,
    build_parameter_impact_map_model,
    build_parameter_impact_summary_cards,
    format_impact_dimension_label,
)
from ui_sections.analytics import (
    build_analytics_tab_section,
    build_commentary_panel_markdown,
    build_missing_metrics_markdown,
    build_run_artifacts_markdown,
    build_selected_analysis_signature,
    build_status_panel_markdown,
)
from ui_sections.parameter_sections import (
    PARAMETER_SECTION_LABELS,
    build_parameter_card_classes,
    build_parameter_section_counts,
    filter_parameters_for_section,
    resolve_default_category_for_section,
    resolve_parameter_section_for_category,
    resolve_parameter_section_categories,
)


CSV_SEARCH_DIRS = [Path("csv_output"), Path("simulation_outputs")]


_ORIGINAL_NICEGUI_RUN_SETUP = nicegui_run.setup


def _setup_nicegui_run_with_permission_fallback() -> None:
    try:
        _ORIGINAL_NICEGUI_RUN_SETUP()
    except PermissionError:
        logging.warning(
            "NiceGUI process pool could not be initialized; continuing without cpu-bound pool."
        )
        nicegui_run.process_pool = None


nicegui_run.setup = _setup_nicegui_run_with_permission_fallback
SCENARIO_DIR = Path("scenario_definitions")
SIMULATION_OUTPUT_DIR = Path("simulation_outputs")
SCENARIO_RUNS_ANALYTICS_DIR = SCENARIO_RUNS_DIR
COST_PROFILE_CONFIG_PATH = SCENARIO_DIR / "cost_profiles.json"
MAX_PREVIEW_ROWS = 500
DEFAULT_ROWS_PER_PAGE = 20
COMMON_CSV_ORDER = [
    "csv_output/materials.csv",
    "csv_output/construction_layers.csv",
    "csv_output/walls.csv",
    "csv_output/floors.csv",
    "csv_output/windows.csv",
]

KEY_COLUMN_TYPES = {
    "materials.csv": {
        "name": "string",
    },
    "construction_layers.csv": {
        "construction_name": "string",
        "layer_index": "integer",
        "name": "string",
    },
}

DEFAULT_COST_PROFILES = {
    "tr_electricity_residential": {
        "label": "TR Elektrik Mesken (TRY/kWh)",
        "unit_cost": 2.35,
        "currency": "TRY",
    },
    "eu_electricity_average": {
        "label": "EU Elektrik Ortalama (EUR/kWh)",
        "unit_cost": 0.28,
        "currency": "EUR",
    },
    "us_electricity_average": {
        "label": "US Elektrik Ortalama (USD/kWh)",
        "unit_cost": 0.12,
        "currency": "USD",
    },
    "custom": {
        "label": "Ozel Deger",
        "unit_cost": 0.12,
        "currency": "TRY",
    },
}

BASE_SCENARIO_VISUAL_PROFILE = {
    "label": "base_scenario",
    "legend_name": "Base Scenario",
    "line_type": "solid",
    "marker": "circle",
    "accent_color": "#1f2937",
    "symbol_size": 8,
    "order": 0,
}

SCENARIO_VISUAL_PRESETS = [
    {
        "line_type": "dashed",
        "marker": "diamond",
        "accent_color": "#0f766e",
    },
    {
        "line_type": "dotted",
        "marker": "triangle",
        "accent_color": "#2563eb",
    },
    {
        "line_type": "dashed",
        "marker": "rect",
        "accent_color": "#dc2626",
    },
    {
        "line_type": "dotted",
        "marker": "pin",
        "accent_color": "#7c3aed",
    },
]


def find_available_port(preferred_port: int, host: str = "0.0.0.0") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind((host, int(preferred_port)))
            return int(preferred_port)
        except OSError:
            candidate.bind((host, 0))
            return int(candidate.getsockname()[1])


def get_base_scenario_visual_profile() -> dict[str, object]:
    return dict(BASE_SCENARIO_VISUAL_PROFILE)


def build_scenario_visual_profile(
    scenario_name: str = "",
    scenario_order: int = 0,
) -> dict[str, object]:
    preset = SCENARIO_VISUAL_PRESETS[scenario_order % len(SCENARIO_VISUAL_PRESETS)]
    legend_name = str(scenario_name or "").strip() or f"Scenario {scenario_order + 1}"
    normalized_label = re.sub(r"[^a-z0-9]+", "_", legend_name.lower()).strip("_") or "scenario"
    return {
        "label": normalized_label,
        "legend_name": legend_name,
        "line_type": preset["line_type"],
        "marker": preset["marker"],
        "accent_color": preset["accent_color"],
        "symbol_size": 9,
        "order": scenario_order + 1,
    }


def build_scenario_visual_registry(scenario_names: list[str]) -> dict[str, dict[str, object]]:
    registry: dict[str, dict[str, object]] = {}
    for scenario_order, scenario_name in enumerate(scenario_names):
        normalized_name = str(scenario_name or "").strip()
        if not normalized_name:
            continue
        registry[normalized_name] = build_scenario_visual_profile(
            scenario_name=normalized_name,
            scenario_order=scenario_order,
        )
    return registry


def build_line_series_style(
    profile: dict[str, object],
    color: str | None = None,
    width: int = 3,
) -> dict[str, object]:
    resolved_color = str(color or profile.get("accent_color") or "#0f766e")
    symbol_size = int(profile.get("symbol_size", 8) or 8)
    return {
        "lineStyle": {
            "color": resolved_color,
            "type": str(profile.get("line_type", "solid") or "solid"),
            "width": width,
        },
        "itemStyle": {"color": resolved_color},
        "symbol": str(profile.get("marker", "circle") or "circle"),
        "symbolSize": symbol_size,
        "showSymbol": True,
    }


def _describe_line_type(line_type: object) -> str:
    normalized = str(line_type or "").strip().lower()
    if normalized == "dashed":
        return "kesikli cizgi"
    if normalized == "dotted":
        return "noktali cizgi"
    return "duz cizgi"


def _describe_marker(marker: object) -> str:
    marker_name = str(marker or "").strip().lower()
    marker_labels = {
        "circle": "daire",
        "diamond": "elmas",
        "triangle": "ucgen",
        "rect": "kare",
        "pin": "isaret pini",
    }
    return marker_labels.get(marker_name, marker_name or "isaretci")


def build_overlay_legend_labels(
    base_profile: dict[str, object],
    scenario_profile: dict[str, object],
    prefix: str = "",
) -> list[str]:
    base_label = str(base_profile.get("legend_name", "Base Scenario"))
    scenario_label = str(scenario_profile.get("legend_name", "Updated Scenario"))
    labels = [
        f"Base Scenario{f' - {base_label}' if base_label != 'Base Scenario' else ''}",
        f"Updated Scenario - {scenario_label}",
    ]
    if prefix:
        return [f"{prefix} {label}" for label in labels]
    return labels


def build_overlay_series_name(
    profile: dict[str, object],
    prefix: str = "",
    is_base: bool = False,
) -> str:
    if is_base:
        label = "Base Scenario"
    else:
        label = f"Updated Scenario - {profile.get('legend_name', 'Scenario')}"
    return f"{prefix} {label}".strip() if prefix else label


def normalize_overlay_selection(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        values = raw_value
    elif raw_value in (None, ""):
        values = []
    else:
        values = [raw_value]

    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def resolve_overlay_scenario_names(
    available_names: list[str],
    selected_names: list[str],
    scenario_limit: int = 3,
) -> list[str]:
    normalized_available = [str(name or "").strip() for name in available_names if str(name or "").strip()]
    resolved = [name for name in normalize_overlay_selection(selected_names) if name in normalized_available]
    if not resolved and normalized_available:
        resolved = normalized_available[:1]
    return resolved[:scenario_limit]


def build_overlay_tooltip_formatter(axis_label: str, unit: str = "") -> str:
    safe_axis_label = axis_label.replace("'", "\\'")
    safe_unit = unit.replace("'", "\\'")
    return (
        "function (params) {"
        "  if (!params || !params.length) return '';"
        "  const axisValue = params[0].axisValueLabel || params[0].axisValue || '-';"
        "  const baseParam = params.find(function (item) { return String(item.seriesName).indexOf('Base Scenario') !== -1; });"
        "  const baseValue = baseParam && baseParam.data != null && baseParam.data !== '' ? Number(baseParam.data) : null;"
        f"  const unit = '{safe_unit}';"
        "  const formatValue = function (value) {"
        "    if (value == null || value === '') return '-';"
        "    const number = Number(value);"
        "    if (Number.isNaN(number)) return String(value);"
        "    return number.toFixed(2) + (unit ? ' ' + unit : '');"
        "  };"
        f"  const lines = ['{safe_axis_label}: ' + axisValue];"
        "  params.forEach(function (item) {"
        "    let line = item.marker + ' ' + item.seriesName + ': ' + formatValue(item.data);"
        "    if (baseValue !== null && String(item.seriesName).indexOf('Base Scenario') === -1 && item.data != null && item.data !== '') {"
        "      const delta = Number(item.data) - baseValue;"
        "      if (!Number.isNaN(delta)) {"
        "        const sign = delta > 0 ? '+' : '';"
        "        line += ' | Delta: ' + sign + delta.toFixed(2) + (unit ? ' ' + unit : '');"
        "      }"
        "    }"
        "    lines.push(line);"
        "  });"
        "  return lines.join('<br/>');"
        "}"
    )


def build_overlay_explanation(
    subject: str,
    base_profile: dict[str, object],
    scenario_profile: dict[str, object],
    zone_name: str = "",
) -> str:
    zone_text = f" Secilen zone: {zone_name}." if zone_name else ""
    return (
        f"Bu grafik {subject} once ve sonra egirilerini ayni overlay alanda gosterir.{zone_text} "
        f"Base Scenario {_describe_line_type(base_profile.get('line_type'))} ve "
        f"{_describe_marker(base_profile.get('marker'))} isaretci ile; "
        f"Updated Scenario - {scenario_profile.get('legend_name', 'Scenario')} ise "
        f"{_describe_line_type(scenario_profile.get('line_type'))} ve "
        f"{_describe_marker(scenario_profile.get('marker'))} isaretci ile gosterilir."
    )


def build_monthly_energy_overlay_model(
    comparison_entries: list[dict[str, object]],
    selected_scenario_names: list[str],
    scenario_limit: int = 3,
) -> dict[str, object]:
    available_names = [str(item.get("scenario_name", "")).strip() for item in comparison_entries]
    resolved_names = resolve_overlay_scenario_names(available_names, selected_scenario_names, scenario_limit)
    reports_by_name = {
        str(item.get("scenario_name", "")).strip(): item
        for item in comparison_entries
        if str(item.get("scenario_name", "")).strip()
    }
    scenario_styles = build_scenario_visual_registry(available_names)
    base_profile = get_base_scenario_visual_profile()

    months = list(MONTH_LABELS_TR)
    unit = "kWh"
    base_heating: list[float | None] = [None] * len(months)
    base_cooling: list[float | None] = [None] * len(months)
    heating_series: list[dict[str, object]] = []
    cooling_series: list[dict[str, object]] = []

    if resolved_names:
        first_report = reports_by_name.get(resolved_names[0], {})
        first_model = build_monthly_energy_chart_model(
            list(first_report.get("metrics", [])) if isinstance(first_report, dict) else [],
            scenario_name=resolved_names[0],
            scenario_order=max(int(scenario_styles.get(resolved_names[0], {}).get("order", 1)) - 1, 0),
        )
        months = list(first_model.get("months", MONTH_LABELS_TR))
        unit = str(first_model.get("unit", "kWh"))
        base_heating = list(first_model.get("base_heating", []))
        base_cooling = list(first_model.get("base_cooling", []))

    heating_series.append(
        {
            "name": build_overlay_series_name(base_profile, prefix="Heating", is_base=True),
            "values": base_heating,
            "profile": base_profile,
            "color": "#1f2937",
        }
    )
    cooling_series.append(
        {
            "name": build_overlay_series_name(base_profile, prefix="Cooling", is_base=True),
            "values": base_cooling,
            "profile": base_profile,
            "color": "#92400e",
        }
    )

    for scenario_name in resolved_names:
        report = reports_by_name.get(scenario_name, {})
        profile = scenario_styles.get(scenario_name, build_scenario_visual_profile(scenario_name))
        chart_model = build_monthly_energy_chart_model(
            list(report.get("metrics", [])) if isinstance(report, dict) else [],
            scenario_name=scenario_name,
            scenario_order=max(int(profile.get("order", 1)) - 1, 0),
        )
        heating_series.append(
            {
                "name": build_overlay_series_name(profile, prefix="Heating"),
                "values": list(chart_model.get("scenario_heating", [])),
                "profile": profile,
                "color": str(profile.get("accent_color", "#0f766e")),
            }
        )
        cooling_series.append(
            {
                "name": build_overlay_series_name(profile, prefix="Cooling"),
                "values": list(chart_model.get("scenario_cooling", [])),
                "profile": profile,
                "color": str(profile.get("accent_color", "#0f766e")),
            }
        )

    return {
        "months": months,
        "unit": unit,
        "selected_scenarios": resolved_names,
        "base_profile": base_profile,
        "heating_series": heating_series,
        "cooling_series": cooling_series,
        "has_data": bool(resolved_names),
    }


def build_zone_temperature_overlay_model(
    comparison_entries: list[dict[str, object]],
    selected_scenario_names: list[str],
    selected_zone: str = "",
    scenario_limit: int = 3,
) -> dict[str, object]:
    available_names = [str(item.get("scenario_name", "")).strip() for item in comparison_entries]
    resolved_names = resolve_overlay_scenario_names(available_names, selected_scenario_names, scenario_limit)
    reports_by_name = {
        str(item.get("scenario_name", "")).strip(): item
        for item in comparison_entries
        if str(item.get("scenario_name", "")).strip()
    }
    scenario_styles = build_scenario_visual_registry(available_names)
    base_profile = get_base_scenario_visual_profile()

    candidate_models: list[dict[str, object]] = []
    zone_options_set: set[str] = set()
    for scenario_name in resolved_names:
        report = reports_by_name.get(scenario_name, {})
        profile = scenario_styles.get(scenario_name, build_scenario_visual_profile(scenario_name))
        chart_model = build_zone_temperature_chart_model(
            list(report.get("metrics", [])) if isinstance(report, dict) else [],
            selected_zone=selected_zone,
            scenario_name=scenario_name,
            scenario_order=max(int(profile.get("order", 1)) - 1, 0),
        )
        candidate_models.append({"scenario_name": scenario_name, "profile": profile, "chart_model": chart_model})
        zone_options_set.update(str(zone) for zone in chart_model.get("zone_options", []) if str(zone).strip())

    zone_options = sorted(zone_options_set)
    resolved_zone = selected_zone if selected_zone in zone_options else (zone_options[0] if zone_options else "")

    labels: list[str] = []
    base_values: list[float | None] = []
    scenario_series: list[dict[str, object]] = []
    unit = "C"

    for index, item in enumerate(candidate_models):
        scenario_name = str(item["scenario_name"])
        profile = item["profile"] if isinstance(item["profile"], dict) else build_scenario_visual_profile(scenario_name)
        report = reports_by_name.get(scenario_name, {})
        chart_model = build_zone_temperature_chart_model(
            list(report.get("metrics", [])) if isinstance(report, dict) else [],
            selected_zone=resolved_zone,
            scenario_name=scenario_name,
            scenario_order=max(int(profile.get("order", 1)) - 1, 0),
        )
        time_labels = list(chart_model.get("time_labels", []))
        if len(time_labels) > len(labels):
            labels = time_labels
        if index == 0:
            base_values = list(chart_model.get("base_values", []))
            unit = str(chart_model.get("unit", "C"))
        scenario_series.append(
            {
                "name": build_overlay_series_name(profile),
                "values": list(chart_model.get("scenario_values", [])),
                "profile": profile,
                "color": str(profile.get("accent_color", "#0f766e")),
            }
        )

    if labels:
        base_values = _align_zone_values(labels, base_values)
        for series in scenario_series:
            series["values"] = _align_zone_values(labels, list(series.get("values", [])))

    base_series = {
        "name": build_overlay_series_name(base_profile, is_base=True),
        "values": base_values,
        "profile": base_profile,
        "color": "#1f2937",
    }

    return {
        "zone_options": zone_options,
        "selected_zone": resolved_zone,
        "time_labels": labels,
        "unit": unit,
        "selected_scenarios": resolved_names,
        "base_series": base_series,
        "scenario_series": scenario_series,
        "has_data": bool(labels) or any(series.get("values") for series in scenario_series),
    }


def build_zone_last_known_point_model(
    metrics_rows: list[dict[str, object]],
    selected_zone: str = "",
) -> dict[str, object]:
    zone_model = build_zone_portfolio_analysis(metrics_rows)
    zone_rows = [row for row in list(zone_model.get("zones", [])) if isinstance(row, dict)]
    if not zone_rows:
        return {
            "zone": "",
            "label": "Last Known",
            "base_value": None,
            "scenario_value": None,
            "has_data": False,
        }

    resolved_row = next(
        (
            row
            for row in zone_rows
            if str(row.get("zone", "")).strip() == selected_zone
        ),
        zone_rows[0],
    )
    base_value = try_parse_number(resolved_row.get("base_avg"))
    scenario_value = try_parse_number(resolved_row.get("scenario_avg"))

    return {
        "zone": str(resolved_row.get("zone", "")),
        "label": "Last Known",
        "base_value": base_value,
        "scenario_value": scenario_value,
        "has_data": base_value is not None or scenario_value is not None,
    }


def find_max_delta_point(
    labels: list[str],
    base_values: list[float | None],
    comparison_series: list[dict[str, object]],
) -> dict[str, object] | None:
    best_point: dict[str, object] | None = None
    for series in comparison_series:
        series_name = str(series.get("name", "Scenario"))
        values = list(series.get("values", []))
        for index, (label, base_value, series_value) in enumerate(zip(labels, base_values, values)):
            if base_value is None or series_value is None:
                continue
            delta = float(series_value) - float(base_value)
            if best_point is None or abs(delta) > abs(float(best_point["delta"])):
                best_point = {
                    "label": label,
                    "index": index,
                    "base_value": float(base_value),
                    "series_value": float(series_value),
                    "delta": float(delta),
                    "series_name": series_name,
                }
    return best_point


def build_delta_summary_text(
    subject: str,
    max_delta_point: dict[str, object] | None,
    unit: str,
) -> str:
    if not max_delta_point:
        return f"{subject} icin belirgin bir delta noktasi bulunamadi."
    delta = float(max_delta_point["delta"])
    trend = "daha yuksek" if delta > 0 else "daha dusuk"
    return (
        f"En buyuk fark {max_delta_point['label']} noktasinda goruldu. "
        f"{max_delta_point['series_name']} base cizgisinden {abs(delta):.2f} {unit} {trend}."
    )

def collect_csv_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*.csv")))
    return files


def collect_log_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*changes.json")))
            files.extend(sorted(directory.rglob("*changes.csv")))
    return files


def collect_scenario_files() -> list[Path]:
    if not SCENARIO_DIR.exists():
        return []
    return sorted(SCENARIO_DIR.rglob("*.json"))


def collect_manifest_files() -> list[Path]:
    if not SIMULATION_OUTPUT_DIR.exists():
        return []
    return sorted(SIMULATION_OUTPUT_DIR.rglob("*__manifest.json"))


def collect_audit_files() -> list[Path]:
    files: list[Path] = []
    for directory in [SIMULATION_OUTPUT_DIR, SCENARIO_RUNS_ANALYTICS_DIR]:
        if directory.exists():
            files.extend(sorted(directory.rglob("*events.jsonl")))
    # Same file can be discovered twice across overlapping roots.
    unique_paths = {path.resolve() for path in files}
    return sorted(unique_paths)


def read_json_file(path: Path) -> dict | list:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_csv_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            return [], []

        rows = []
        for index, row in enumerate(reader, start=1):
            normalized_row = {key: value for key, value in row.items()}
            normalized_row["__row_id"] = index
            rows.append(normalized_row)

        return rows, reader.fieldnames


def read_log_rows(log_path: Path) -> tuple[list[dict], list[str]]:
    if log_path.suffix.lower() == ".json":
        raw_data = read_json_file(log_path)
        if not isinstance(raw_data, list):
            return [], []

        rows = []
        fieldnames = []
        for index, item in enumerate(raw_data, start=1):
            if not isinstance(item, dict):
                continue
            row = {key: value for key, value in item.items()}
            row["__row_id"] = index
            rows.append(row)
            for key in row.keys():
                if key != "__row_id" and key not in fieldnames:
                    fieldnames.append(key)
        return rows, fieldnames

    return read_csv_rows(log_path)


def read_audit_rows(audit_path: Path) -> tuple[list[dict], list[str]]:
    if not audit_path.exists():
        return [], []

    rows: list[dict] = []
    fieldnames: list[str] = [
        "timestamp",
        "event_type",
        "scenario_name",
        "status",
        "source",
        "message",
        "error_type",
        "error",
        "phase",
        "details_text",
    ]
    with audit_path.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file, start=1):
            raw_line = line.strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            details = payload.get("details", {})
            if not isinstance(details, dict):
                details = {}

            row = {
                "__row_id": index,
                "timestamp": str(payload.get("timestamp", "")),
                "event_type": str(payload.get("event_type", "")),
                "scenario_name": str(payload.get("scenario_name", "")),
                "status": str(payload.get("status", "")),
                "source": str(payload.get("source", "")),
                "message": str(payload.get("message", "")),
                "error_type": str(details.get("error_type", "")),
                "error": str(details.get("error", "")),
                "phase": str(details.get("phase", "")),
                "details_text": json.dumps(details, ensure_ascii=False),
            }
            rows.append(row)

    rows.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return rows, fieldnames


def read_manifest_entries() -> list[dict]:
    manifests = []
    for manifest_path in collect_manifest_files():
        raw_data = read_json_file(manifest_path)
        if not isinstance(raw_data, dict):
            continue

        entry = dict(raw_data)
        entry["manifest_path"] = manifest_path.as_posix()
        entry["manifest_mtime"] = manifest_path.stat().st_mtime
        manifests.append(entry)

    manifests.sort(key=lambda item: item.get("manifest_mtime", 0))
    return manifests


def read_comparison_report_entries() -> list[dict]:
    return load_comparison_report_entries(
        SCENARIO_RUNS_ANALYTICS_DIR,
        EXPECTED_COMPARISON_METRIC_IDS,
    )


def _format_comparison_highlight(summary: dict, title: str) -> list[str]:
    item = summary.get(title)
    if not isinstance(item, dict) or not item:
        return [f"- {title}: -"]

    percent_text = "-"
    try:
        if item.get("percent_delta") is not None:
            percent_text = f"{float(item.get('percent_delta')):.2f}%"
    except (TypeError, ValueError):
        percent_text = str(item.get("percent_delta", "-"))

    severity = str(item.get("severity_level", "-")).strip() or "-"
    trend = str(item.get("trend", "-")).strip() or "-"
    label = str(item.get("label", "-")).strip() or "-"
    comment = str(item.get("auto_comment", "")).strip()
    lines = [f"- {title}: {label} | {percent_text} | {severity} | {trend}"]
    if comment:
        lines.append(f"  yorum: {comment}")
    return lines


def format_cost_value(value: object, currency: str = "TRY") -> str:
    if value is None:
        return "-"
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return "-"
    return f"{number:,.2f} {currency}".replace(",", " ")


def build_cost_comparison_chart_model(cost_summary: dict[str, object]) -> dict[str, object]:
    base_cost = try_parse_number(cost_summary.get("base_cost"))
    scenario_cost = try_parse_number(cost_summary.get("scenario_cost"))
    savings = None
    if base_cost is not None and scenario_cost is not None:
        savings = base_cost - scenario_cost

    bars = [
        {"label": "Old Annual Cost", "value": base_cost, "color": "#94a3b8"},
        {"label": "New Annual Cost", "value": scenario_cost, "color": "#0f766e"},
        {
            "label": "Savings",
            "value": savings,
            "color": "#059669" if savings is not None and savings >= 0 else "#dc2626",
        },
    ]

    return {
        "labels": [bar["label"] for bar in bars],
        "values": [
            {"value": bar["value"], "itemStyle": {"color": bar["color"]}}
            for bar in bars
        ],
        "has_data": base_cost is not None and scenario_cost is not None,
        "savings": savings,
    }


def _copy_default_cost_profiles() -> dict[str, dict[str, object]]:
    return {
        profile_id: {
            "label": str(profile.get("label", "")),
            "unit_cost": float(profile.get("unit_cost", 0.12)),
            "currency": str(profile.get("currency", "TRY")),
        }
        for profile_id, profile in DEFAULT_COST_PROFILES.items()
    }


def normalize_cost_profiles(raw_profiles: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw_profiles, dict):
        return _copy_default_cost_profiles()

    normalized: dict[str, dict[str, object]] = {}
    for raw_id, payload in raw_profiles.items():
        profile_id = str(raw_id).strip()
        if not profile_id or not isinstance(payload, dict):
            continue

        label = str(payload.get("label", profile_id)).strip() or profile_id
        currency = str(payload.get("currency", "TRY")).strip().upper() or "TRY"
        try:
            unit_cost = float(payload.get("unit_cost", 0))
        except (TypeError, ValueError):
            continue
        if unit_cost <= 0:
            continue

        normalized[profile_id] = {
            "label": label,
            "unit_cost": unit_cost,
            "currency": currency,
        }

    if not normalized:
        normalized = _copy_default_cost_profiles()

    if "custom" not in normalized:
        normalized["custom"] = _copy_default_cost_profiles()["custom"]

    return normalized


@lru_cache(maxsize=1)
def load_cost_profiles(config_path: str | Path = COST_PROFILE_CONFIG_PATH) -> dict[str, dict[str, object]]:
    path = Path(config_path)
    if not path.exists():
        return _copy_default_cost_profiles()

    try:
        raw_data = read_json_file(path)
    except Exception:
        return _copy_default_cost_profiles()

    if isinstance(raw_data, dict) and isinstance(raw_data.get("profiles"), dict):
        return normalize_cost_profiles(raw_data.get("profiles"))
    return normalize_cost_profiles(raw_data)


def get_cost_profile_options() -> dict[str, str]:
    profiles = load_cost_profiles()
    return {profile_id: str(item["label"]) for profile_id, item in profiles.items()}


def resolve_cost_profile(profile_id: str) -> dict[str, object]:
    profiles = load_cost_profiles()
    normalized_id = str(profile_id or "").strip()
    if normalized_id not in profiles:
        normalized_id = "custom"

    profile = dict(profiles[normalized_id])
    profile["id"] = normalized_id
    return profile


def get_initial_csv(options: list[str]) -> str | None:
    for expected in COMMON_CSV_ORDER:
        if expected in options:
            return expected
    return options[0] if options else None


def get_initial_log(options: list[str]) -> str | None:
    return options[0] if options else None


def get_initial_scenario(options: list[str]) -> str | None:
    return options[0] if options else None


def get_initial_audit(options: list[str]) -> str | None:
    return options[0] if options else None


def filter_parameter_definitions(
    parameters: list[ParameterDefinition],
    category: str = "Tum Kategoriler",
    query: str = "",
) -> list[ParameterDefinition]:
    filtered = parameters
    normalized_query = query.strip().lower()

    if category and category != "Tum Kategoriler":
        filtered = [parameter for parameter in filtered if parameter.category == category]

    if normalized_query:
        filtered = [
            parameter
            for parameter in filtered
            if any(
                normalized_query in str(value).lower()
                for value in (
                    parameter.id,
                    parameter.label,
                    parameter.dataset,
                    parameter.field_name,
                    parameter.description,
                    parameter.category,
                )
            )
        ]

    return filtered


@lru_cache(maxsize=256)
def get_parameter_current_value_preview(dataset: str, field_name: str) -> str:
    csv_path = Path("csv_output") / dataset
    if not csv_path.exists():
        return "-"

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or field_name not in reader.fieldnames:
            return "-"

        for row in reader:
            value = str(row.get(field_name, "")).strip()
            if value:
                return value

    return "-"


def filter_rows(
    rows: list[dict],
    global_query: str = "",
    column_name: str = "",
    column_query: str = "",
) -> list[dict]:
    filtered_rows = rows
    normalized_global = global_query.strip().lower()
    normalized_column = column_query.strip().lower()

    if normalized_global:
        filtered_rows = [
            row
            for row in filtered_rows
            if any(
                normalized_global in str(value).lower()
                for key, value in row.items()
                if key != "__row_id"
            )
        ]

    if column_name and normalized_column:
        filtered_rows = [
            row
            for row in filtered_rows
            if normalized_column in str(row.get(column_name, "")).lower()
        ]

    return filtered_rows


def open_row_detail(title: str, row: dict, fieldnames: list[str]) -> None:
    with ui.dialog() as dialog, ui.card().classes("min-w-[24rem] max-w-3xl w-full"):
        ui.label(title).classes("text-lg font-medium")
        with ui.column().classes("w-full gap-2"):
            for field in fieldnames:
                with ui.row().classes("w-full justify-between items-start gap-4"):
                    ui.label(field).classes("text-sm text-slate-500")
                    ui.label(str(row.get(field, ""))).classes("text-sm text-right break-all")
        ui.button("Kapat", on_click=dialog.close).props("flat color=primary")
    dialog.open()


def format_scenario_markdown(scenario: dict) -> str:
    operations = scenario.get("operations", [])
    operation_lines = []
    for operation in operations:
        match = operation.get("match", {})
        updates = operation.get("updates", {})
        updates_text = ", ".join(f"{key}={value}" for key, value in updates.items()) or "-"
        operation_lines.append(
            f"- **{operation.get('name', 'islem')}**: "
            f"`{match.get('column', '-')}` = `{match.get('value', '-')}` -> {updates_text}"
        )

    return "\n".join(
        [
            f"**Senaryo:** {scenario.get('scenario_name', '-')}",
            f"**Aciklama:** {scenario.get('description', '-')}",
            f"**Girdi:** `{scenario.get('input', '-')}`",
            "",
            "**Islemler:**",
            *operation_lines,
        ]
    )


def format_scenario_change_summary_markdown(scenario: dict) -> str:
    changes = scenario.get("changes", [])
    if not isinstance(changes, list) or not changes:
        return "Bu senaryo icin kayitli degisiklik ozeti bulunamadi."

    lines = ["**Degisiklik Ozeti**"]
    for change in changes:
        if not isinstance(change, dict):
            continue
        lines.append(
            f"- `{change.get('label', '-')}` | "
            f"kayit=`{change.get('record_label', '-')}` | "
            f"`{change.get('field_name', '-')}`: "
            f"`{change.get('old_value', '-')}` -> `{change.get('new_value', '-')}`"
        )
    return "\n".join(lines)


def get_scenario_build_status(
    scenario_path: Path,
    state: dict[str, list[str]],
) -> dict[str, bool]:
    output_path, log_path, _ = scenario_output_targets(scenario_path)
    output_ready = output_path.as_posix() in state["csv_files"]
    log_ready = log_path.as_posix() in state["log_files"]
    return {
        "ready": output_ready and log_ready,
        "output_ready": output_ready,
        "log_ready": log_ready,
    }


def try_parse_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(" ", "")
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def format_delta(old_value: object, new_value: object) -> tuple[str, str]:
    old_number = try_parse_number(old_value)
    new_number = try_parse_number(new_value)
    if old_number is None or new_number is None:
        return "-", "Degisim"

    delta = new_number - old_number
    if delta > 0:
        direction = "Artis"
    elif delta < 0:
        direction = "Azalis"
    else:
        direction = "Sabit"
    return f"{delta:.4f}".rstrip("0").rstrip("."), direction


def validate_parameter_new_value(
    parameter: ParameterDefinition,
    current_value: object,
    new_value: object,
) -> list[str]:
    warnings: list[str] = []
    new_text = str(new_value or "").strip()
    if not new_text:
        warnings.append("Yeni deger bos birakilamaz.")
        return warnings

    value_type = str(parameter.value_type or "").strip().lower()
    if value_type in {"float", "integer"}:
        numeric = try_parse_number(new_text)
        if numeric is None:
            warnings.append("Sayisal bir deger girin.")
            return warnings

        if value_type == "integer" and not float(numeric).is_integer():
            warnings.append("Bu alan tam sayi bekliyor.")

        field_name = str(parameter.field_name or "").strip().lower()
        min_value = parameter.min_value
        max_value = parameter.max_value
        if min_value is not None and numeric < float(min_value):
            warnings.append(f"Deger onerilen minimumun altinda: {min_value}")
        if max_value is not None and numeric > float(max_value):
            warnings.append(f"Deger onerilen maksimumun ustunde: {max_value}")

        if "setpoint" in field_name and (numeric < 10 or numeric > 35):
            warnings.append("Setpoint icin makul aralik 10-35 C civarinda olmali.")
        elif numeric < 0 and field_name not in {"temperature_offset", "delta"}:
            warnings.append("Negatif deger beklenmiyor; degeri kontrol edin.")
        elif abs(numeric) > 1_000_000:
            warnings.append("Deger cok yuksek gorunuyor; lutfen kontrol edin.")

        current_number = try_parse_number(current_value)
        if current_number is not None and current_number != 0:
            percent_change = abs(((numeric - current_number) / current_number) * 100.0)
            if percent_change > 300:
                warnings.append("Degisim orani cok yuksek; girdi dogrulugu kontrol edilmeli.")

    return warnings


def build_parameter_recommended_range_text(parameter: ParameterDefinition) -> str:
    min_value = parameter.min_value
    max_value = parameter.max_value
    if min_value is None and max_value is None:
        return "Onerilen aralik: serbest"

    unit = str(parameter.unit or "").strip()
    unit_suffix = f" {unit}" if unit else ""
    if min_value is not None and max_value is not None:
        return f"Onerilen aralik: {min_value} - {max_value}{unit_suffix}"
    if min_value is not None:
        return f"Onerilen minimum: {min_value}{unit_suffix}"
    return f"Onerilen maksimum: {max_value}{unit_suffix}"


def build_parameter_recommended_range_style(
    parameter: ParameterDefinition,
    new_value: object,
) -> str:
    min_value = parameter.min_value
    max_value = parameter.max_value
    if min_value is None and max_value is None:
        return "text-xs text-slate-600"

    text_value = str(new_value or "").strip()
    if not text_value:
        return "text-xs text-slate-600"

    if str(parameter.value_type or "").strip().lower() not in {"float", "integer"}:
        return "text-xs text-slate-600"

    numeric = try_parse_number(text_value)
    if numeric is None:
        return "text-xs text-rose-700"

    if min_value is not None and numeric < float(min_value):
        return "text-xs text-rose-700"
    if max_value is not None and numeric > float(max_value):
        return "text-xs text-rose-700"
    return "text-xs text-emerald-700"


def build_percent_change_text(old_value: object, new_value: object) -> str:
    old_number = try_parse_number(old_value)
    new_number = try_parse_number(new_value)
    if old_number is None or new_number is None:
        return "-"
    if old_number == 0:
        return "-"
    percent = ((new_number - old_number) / old_number) * 100.0
    return f"{percent:.2f}%"


def format_chart_value(value: object, unit: str = "") -> str:
    number = try_parse_number(value)
    if number is None:
        return "-"
    suffix = f" {unit}" if unit else ""
    return f"{number:.4f}".rstrip("0").rstrip(".") + suffix


def build_value_transition_chart_options(
    label: str,
    base_value: object,
    updated_value: object,
    unit: str = "",
) -> dict[str, object]:
    safe_label = str(label).replace("'", "\\'")
    safe_unit = str(unit or "").replace("'", "\\'")
    base_number = try_parse_number(base_value)
    updated_number = try_parse_number(updated_value)
    plotted_values = [value for value in [base_number, updated_number] if value is not None]
    min_value = min(plotted_values) if plotted_values else 0.0
    max_value = max(plotted_values) if plotted_values else 1.0
    spread = max_value - min_value
    padding = spread * 0.25 if spread else max(abs(max_value) * 0.15, 1.0)
    axis_min = min_value - padding
    axis_max = max_value + padding

    def build_label_formatter(prefix: str) -> str:
        safe_prefix = prefix.replace("'", "\\'")
        return (
            "function(params) {"
            " const value = Array.isArray(params.value) ? params.value[1] : params.value;"
            " if (value == null || value === '') return '';"
            " const num = Number(value);"
            " if (Number.isNaN(num)) return String(value);"
            f" const unit = '{safe_unit}';"
            f" const prefix = '{safe_prefix}';"
            " const formatted = num.toFixed(4).replace(/\\.0+$/, '').replace(/(\\.\\d*?)0+$/, '$1');"
            " return prefix + formatted + (unit ? ' ' + unit : '');"
            "}"
        )

    tooltip_formatter = (
        "function(params) {"
        " if (!params || !params.length) return '';"
        f" const title = '{safe_label}';"
        f" const unit = '{safe_unit}';"
        " const formatValue = function(value) {"
        "   if (value == null || value === '') return '-';"
        "   const num = Number(value);"
        "   if (Number.isNaN(num)) return String(value);"
        "   return num.toFixed(4).replace(/\\.0+$/, '').replace(/(\\.\\d*?)0+$/, '$1') + (unit ? ' ' + unit : '');"
        " };"
        " const lines = [title];"
        " params.forEach(function(item) {"
        "   const pointValue = Array.isArray(item.value) ? item.value[1] : item.value;"
        "   lines.push(item.marker + ' ' + item.seriesName + ': ' + formatValue(pointValue));"
        " });"
        " return lines.join('<br/>');"
        "}"
    )

    return {
        "animation": False,
        "tooltip": {"trigger": "axis", "formatter": tooltip_formatter},
        "grid": {"left": 56, "right": 28, "top": 28, "bottom": 44, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": ["Ilk Deger", "Yeni Deger"],
            "axisTick": {"alignWithLabel": True},
        },
        "yAxis": {
            "type": "value",
            "name": unit,
            "min": axis_min,
            "max": axis_max,
            "splitLine": {"lineStyle": {"color": "#d1d5db"}},
        },
        "series": [
            {
                "name": "Gecis",
                "type": "line",
                "data": [base_number, updated_number],
                "lineStyle": {"type": "dashed", "width": 3, "color": "#94a3b8"},
                "symbol": "none",
                "z": 1,
            },
            {
                "name": "Ilk Deger",
                "type": "scatter",
                "data": [["Ilk Deger", base_number]],
                "symbolSize": 18,
                "itemStyle": {"color": "#2563eb"},
                "label": {
                    "show": True,
                    "position": "right",
                    "color": "#1d4ed8",
                    "fontWeight": "bold",
                    "fontSize": 18,
                    "formatter": build_label_formatter(""),
                },
                "z": 3,
            },
            {
                "name": "Yeni Deger",
                "type": "scatter",
                "data": [["Yeni Deger", updated_number]],
                "symbolSize": 18,
                "itemStyle": {"color": "#dc2626"},
                "label": {
                    "show": True,
                    "position": "right",
                    "color": "#dc2626",
                    "fontWeight": "bold",
                    "fontSize": 18,
                    "formatter": build_label_formatter(""),
                },
                "z": 3,
            },
        ],
    }


def build_parameter_transition_rows(chart_model: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    labels = list(chart_model.get("labels", []))
    base_values = list(chart_model.get("base_values", []))
    updated_values = list(chart_model.get("updated_values", []))
    units = list(chart_model.get("units", []))

    for index in chart_model.get("changed_indexes", []):
        if index >= len(labels):
            continue
        rows.append(
            {
                "label": str(labels[index]),
                "base_value": base_values[index] if index < len(base_values) else None,
                "updated_value": updated_values[index] if index < len(updated_values) else None,
                "unit": str(units[index] or "") if index < len(units) else "",
            }
        )
    return rows


def build_impact_transition_rows(impact_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped_rows: dict[tuple[str, str], dict[str, object]] = {}
    for row in impact_rows:
        source = str(row.get("kaynak", "")).strip()
        field_name = str(row.get("degisen_alan", "")).strip()
        if not source and not field_name:
            continue
        base_value = row.get("eski_deger")
        updated_value = row.get("yeni_deger")
        base_number = try_parse_number(base_value)
        updated_number = try_parse_number(updated_value)
        if base_number is None or updated_number is None or float(base_number) == float(updated_number):
            continue
        key = (source, field_name)
        if key not in grouped_rows:
            grouped_rows[key] = {
                "label": build_chart_change_label(source, field_name),
                "base_value": base_value,
                "updated_value": updated_value,
                "unit": "",
            }
    return list(grouped_rows.values())


def build_parameter_overlay_tooltip_formatter(chart_model: dict[str, object]) -> str:
    labels = list(chart_model.get("labels", []))
    base_values = list(chart_model.get("base_values", []))
    updated_values = list(chart_model.get("updated_values", []))
    units = list(chart_model.get("units", []))

    tooltip_rows = {
        str(label): {
            "base": base_values[index] if index < len(base_values) else None,
            "updated": updated_values[index] if index < len(updated_values) else None,
            "unit": units[index] if index < len(units) else "",
        }
        for index, label in enumerate(labels)
    }
    rows_json = json.dumps(tooltip_rows)

    return (
        "function (params) {"
        "  if (!params || !params.length) return '';"
        f"  const rows = {rows_json};"
        "  const axisValue = params[0].axisValueLabel || params[0].axisValue || '-';"
        "  const detail = rows[String(axisValue)] || {};"
        "  const unit = detail.unit || '';"
        "  const formatValue = function (value) {"
        "    if (value == null || value === '') return '-';"
        "    const number = Number(value);"
        "    if (Number.isNaN(number)) return String(value);"
        "    return number.toFixed(4).replace(/\\.0+$/, '').replace(/(\\.\\d*?)0+$/, '$1') + (unit ? ' ' + unit : '');"
        "  };"
        "  const lines = ['Parametre: ' + axisValue];"
        "  lines.push('Base: ' + formatValue(detail.base));"
        "  lines.push('Updated: ' + formatValue(detail.updated));"
        "  if (detail.base != null && detail.updated != null) {"
        "    const delta = Number(detail.updated) - Number(detail.base);"
        "    if (!Number.isNaN(delta)) {"
        "      const sign = delta > 0 ? '+' : '';"
        "      lines.push('Δ: ' + sign + formatValue(delta));"
        "      if (Number(detail.base) !== 0) {"
        "        const percent = (delta / Number(detail.base)) * 100;"
        "        if (!Number.isNaN(percent)) {"
        "          const percentSign = percent > 0 ? '+' : '';"
        "          lines.push('%Δ: ' + percentSign + percent.toFixed(2) + '%');"
        "        }"
        "      }"
        "    }"
        "  }"
        "  return lines.join('<br/>');"
        "}"
    )


def build_dumbbell_energy_tooltip_formatter(chart_model: dict[str, object]) -> str:
    labels = list(chart_model.get("labels", []))
    before_values = list(chart_model.get("before_values", []))
    after_values = list(chart_model.get("after_values", []))
    unit = str(chart_model.get("unit", "")).strip()

    lookup: dict[str, dict[str, object]] = {}
    for label, before_value, after_value in zip(labels, before_values, after_values):
        lookup[str(label)] = {
            "base": before_value,
            "scenario": after_value,
            "unit": unit,
        }

    lookup_json = json.dumps(lookup, ensure_ascii=False)
    safe_unit = unit.replace("'", "\\'")
    return (
        "function (params) {"
        "  const rows = Array.isArray(params) ? params : [params];"
        "  if (!rows || !rows.length) return '';"
        f"  const lookup = {lookup_json};"
        "  const candidate = rows.find(function (item) {"
        "    return item && Array.isArray(item.value) && item.value.length > 1;"
        "  }) || rows[0];"
        "  let label = '-';"
        "  if (candidate && candidate.axisValueLabel) label = String(candidate.axisValueLabel);"
        "  else if (candidate && Array.isArray(candidate.value) && candidate.value.length > 1) label = String(candidate.value[1]);"
        "  else if (candidate && candidate.name != null) label = String(candidate.name);"
        "  const detail = lookup[label] || {};"
        "  const unit = String(detail.unit || '') || '" + safe_unit + "';"
        "  const baseRaw = detail.base;"
        "  const scenarioRaw = detail.scenario;"
        "  const base = baseRaw == null || baseRaw === '' ? null : Number(baseRaw);"
        "  const scenario = scenarioRaw == null || scenarioRaw === '' ? null : Number(scenarioRaw);"
        "  const format = function (value) {"
        "    if (value == null || Number.isNaN(value)) return '-';"
        "    return value.toFixed(2) + (unit ? ' ' + unit : '');"
        "  };"
        "  let deltaText = '-';"
        "  let percentText = '-';"
        "  if (base !== null && scenario !== null && !Number.isNaN(base) && !Number.isNaN(scenario)) {"
        "    const delta = scenario - base;"
        "    const sign = delta > 0 ? '+' : '';"
        "    deltaText = sign + delta.toFixed(2) + (unit ? ' ' + unit : '');"
        "    if (base !== 0) {"
        "      const percent = (delta / base) * 100;"
        "      const percentSign = percent > 0 ? '+' : '';"
        "      percentText = percentSign + percent.toFixed(2) + '%';"
        "    }"
        "  }"
        "  const badge = function (title, value, color) {"
        "    return '<span style=\"display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;border-radius:999px;background:' + color + ';font-size:11px;\">'"
        "      + title + ': <b>' + value + '</b></span>';"
        "  };"
        "  const lines = ["
        "    '<b>' + label + '</b>',"
        "    badge('Base', format(base), '#e2e8f0'),"
        "    badge('Scenario', format(scenario), '#ccfbf1'),"
        "    badge('Δ', deltaText, '#fef3c7'),"
        "    badge('%Δ', percentText, '#dbeafe')"
        "  ];"
        "  return lines.join('<br/>');"
        "}"
    )


def build_parameter_delta_summary(chart_model: dict[str, object], index: int) -> str:
    labels = list(chart_model.get("labels", []))
    base_values = list(chart_model.get("base_values", []))
    updated_values = list(chart_model.get("updated_values", []))
    units = list(chart_model.get("units", []))

    label = str(labels[index]) if index < len(labels) else "-"
    base_value = base_values[index] if index < len(base_values) else None
    updated_value = updated_values[index] if index < len(updated_values) else None
    unit = str(units[index] or "") if index < len(units) else ""

    base_number = try_parse_number(base_value)
    updated_number = try_parse_number(updated_value)
    if base_number is None or updated_number is None:
        return f"{label} icin fark hesabi yapilamadi."

    delta = updated_number - base_number
    sign = "+" if delta > 0 else ""
    summary = (
        f"{label} | Base: {format_chart_value(base_number, unit)} | "
        f"Updated: {format_chart_value(updated_number, unit)} | "
        f"Δ: {sign}{format_chart_value(delta, unit)}"
    )
    if base_number != 0:
        percent = (delta / base_number) * 100.0
        percent_sign = "+" if percent > 0 else ""
        summary += f" | %Δ: {percent_sign}{percent:.2f}%"
    return summary


def build_metric_change_commentary(
    label: str,
    base_value: object,
    updated_value: object,
    unit: str,
) -> str | None:
    base_number = try_parse_number(base_value)
    updated_number = try_parse_number(updated_value)
    if base_number is None or updated_number is None:
        return None

    delta = updated_number - base_number
    if abs(delta) < 1e-9:
        return f"{label}: anlamli bir degisim yok."

    percent_text = ""
    if base_number != 0:
        percent = (delta / base_number) * 100.0
        percent_text = f" (%{percent:+.1f})"

    if delta < 0:
        return (
            f"{label}: {format_chart_value(abs(delta), unit)} azaldi{percent_text}. "
            f"Yeni deger {format_chart_value(updated_number, unit)}."
        )
    return (
        f"{label}: {format_chart_value(delta, unit)} artti{percent_text}. "
        f"Yeni deger {format_chart_value(updated_number, unit)}."
    )


def build_real_output_delta_chart_options(chart_model: dict[str, object]) -> dict[str, object]:
    labels = list(chart_model.get("labels", []))
    deltas = list(chart_model.get("delta_values", []))
    units = list(chart_model.get("units", []))
    is_normalized = bool(chart_model.get("is_normalized"))
    payload: list[dict[str, object]] = []

    for label, delta, unit in zip(labels, deltas, units):
        if delta is None:
            payload.append(
                {
                    "value": 0,
                    "itemStyle": {"color": "#cbd5e1"},
                    "meta": {"label": label, "unit": unit, "missing": True},
                }
            )
            continue

        color = "#dc2626" if float(delta) > 0 else "#16a34a"
        if abs(float(delta)) < 1e-9:
            color = "#64748b"
        payload.append(
            {
                "value": float(delta),
                "itemStyle": {"color": color},
                "meta": {"label": label, "unit": unit, "missing": False},
            }
        )

    tooltip_formatter = (
        "function(params) {"
        "  const meta = params.data && params.data.meta ? params.data.meta : {};"
        "  if (meta.missing) { return params.name + '<br/>Veri yok'; }"
        "  const unit = meta.unit ? ' ' + meta.unit : '';"
        "  return params.name + '<br/>Delta: ' + params.value + unit;"
        "}"
    )

    return {
        "xAxis": {"data": labels},
        "yAxis": {"name": "Normalize Delta" if is_normalized else "Yeni - Eski"},
        "series": [{"data": payload}],
        "tooltip": {"formatter": tooltip_formatter},
    }


PARAMETER_IMPACT_DIMENSIONS = (
    "heating",
    "cooling",
    "cost",
    "comfort",
)
PARAMETER_IMPACT_LABELS: dict[str, str] = {
    "heating": "Isitma",
    "cooling": "Sogutma",
    "cost": "Maliyet",
    "comfort": "Konfor",
}
PARAMETER_IMPACT_WEIGHTS: dict[str, dict[str, int]] = {
    "u_value": {"heating": 2, "cost": 2},
    "thermal_mass": {"comfort": 3, "cooling": 2},
    "assembly_thickness": {"heating": 2, "cost": 2, "comfort": 1},
    "heat_transfer": {"cooling": 2},
    "envelope_performance": {"heating": 1, "cooling": 2, "cost": 2},
    "heat_loss": {"heating": 2, "cost": 2},
    "heat_storage": {"comfort": 2, "cooling": 1},
    "temperature_response": {"comfort": 2, "cooling": 1},
    "surface_exchange": {"cooling": 1, "comfort": 1},
    "radiative_behavior": {"cooling": 1, "comfort": 1},
    "solar_gain": {"cooling": 2, "comfort": 1},
    "surface_temperature": {"cooling": 1, "comfort": 2},
    "daylight_reflectance": {"comfort": 1},
    "surface_optics": {"cooling": 1, "comfort": 1},
    "assembly_behavior": {"comfort": 1, "heating": 1},
    "assembly_composition": {"heating": 1, "cooling": 1, "cost": 1},
    "thermal_performance": {"heating": 2, "cooling": 2, "cost": 2},
    "wall_u_value": {"heating": 2, "cooling": 1, "cost": 1},
    "roof_u_value": {"heating": 1, "cooling": 2, "comfort": 1},
    "floor_u_value": {"heating": 1, "cost": 1},
    "window_heat_transfer": {"heating": 2, "cooling": 2, "cost": 2},
    "heating_load": {"heating": 2, "cost": 2},
    "cooling_load": {"cooling": 2, "comfort": 1, "cost": 2},
    "daylight_balance": {"comfort": 1, "cost": 1},
    "construction_mapping": {"heating": 1, "cooling": 1, "cost": 1},
    "surface_assignment": {"cooling": 1, "comfort": 1},
    "layer_order": {"comfort": 1, "heating": 1},
    "surface_behavior": {"cooling": 1, "comfort": 1},
}


def format_impact_dimension_label(dimension: str) -> str:
    return PARAMETER_IMPACT_LABELS.get(str(dimension), str(dimension).replace("_", " ").title())


def analyze_parameter_change_state(
    parameter: ParameterDefinition,
    current_value: object,
    new_value: object,
) -> dict[str, object]:
    new_text = str(new_value or "").strip()
    current_text = str(current_value or "").strip()
    if not new_text:
        return {
            "has_effective_change": False,
            "reason": "Yeni deger girilmedi.",
            "multiplier": 0,
            "direction": "none",
        }

    value_type = str(parameter.value_type or "").strip().lower()
    if value_type in {"float", "integer"}:
        current_number = try_parse_number(current_value)
        new_number = try_parse_number(new_value)
        if current_number is None or new_number is None:
            return {
                "has_effective_change": False,
                "reason": "Gecerli sayisal deger girilmedi.",
                "multiplier": 0,
                "direction": "none",
            }
        delta = float(new_number) - float(current_number)
        if delta == 0:
            return {
                "has_effective_change": False,
                "reason": "Yeni deger mevcut degerle ayni.",
                "multiplier": 0,
                "direction": "none",
            }
        if current_number == 0:
            relative_change = abs(delta)
        else:
            relative_change = abs(delta / float(current_number))
        if relative_change < 0.05:
            multiplier = 1
        elif relative_change < 0.20:
            multiplier = 2
        else:
            multiplier = 3
        return {
            "has_effective_change": True,
            "reason": "",
            "multiplier": multiplier,
            "direction": "up" if delta > 0 else "down",
        }

    if new_text == current_text:
        return {
            "has_effective_change": False,
            "reason": "Yeni deger mevcut degerle ayni.",
            "multiplier": 0,
            "direction": "none",
        }
    return {
        "has_effective_change": True,
        "reason": "",
        "multiplier": 2,
        "direction": "changed",
    }


def build_parameter_change_summary_text(
    parameter: ParameterDefinition,
    current_value: object,
    new_value: object,
    change_state: dict[str, object],
) -> str:
    if not bool(change_state.get("has_effective_change")):
        return str(change_state.get("reason", "Yeni deger bekleniyor."))

    unit = str(parameter.unit or "").strip()
    direction = str(change_state.get("direction", "changed"))
    value_type = str(parameter.value_type or "").strip().lower()

    if value_type in {"float", "integer"}:
        current_number = try_parse_number(current_value)
        new_number = try_parse_number(new_value)
        if current_number is None or new_number is None:
            return "Degisim ozeti hesaplanamadi."
        delta = new_number - current_number
        sign = "+" if delta > 0 else ""
        direction_text = {
            "up": "artis",
            "down": "azalis",
            "changed": "degisim",
        }.get(direction, "degisim")
        return (
            f"{format_chart_value(current_number, unit)} -> {format_chart_value(new_number, unit)} | "
            f"{direction_text}: {sign}{format_chart_value(delta, unit)}"
        )

    return f"{str(current_value or '-')} -> {str(new_value or '-')} | deger guncellendi"


def build_parameter_expected_effect_text(
    parameter_impact_row: dict[str, object],
) -> str:
    ranked_dimensions: list[tuple[str, int]] = []
    for dimension in PARAMETER_IMPACT_DIMENSIONS:
        score = int(dict(parameter_impact_row.get(dimension, {})).get("score", 0))
        if score > 0:
            ranked_dimensions.append((dimension, score))

    if not ranked_dimensions:
        return "Beklenen etki henuz hesaplanmadi."

    ranked_dimensions.sort(key=lambda item: item[1], reverse=True)
    top_dimensions = [format_impact_dimension_label(item[0]) for item in ranked_dimensions[:3]]
    return "Beklenen en guclu etkiler: " + ", ".join(top_dimensions)


def build_change_direction_badge(change_state: dict[str, object]) -> tuple[str, str]:
    direction = str(change_state.get("direction", "none"))
    if direction == "up":
        return "Artis", "positive"
    if direction == "down":
        return "Azalis", "negative"
    if direction == "changed":
        return "Guncellendi", "primary"
    return "Bekleniyor", "warning"


def build_change_strength_badge(change_state: dict[str, object]) -> tuple[str, str]:
    multiplier = int(change_state.get("multiplier", 0) or 0)
    if multiplier >= 3:
        return "Guclu Etki", "negative"
    if multiplier == 2:
        return "Orta Etki", "warning"
    if multiplier == 1:
        return "Sinirli Etki", "primary"
    return "Etki Yok", "grey"


def build_change_summary_card_classes(change_state: dict[str, object]) -> str:
    if not bool(change_state.get("has_effective_change")):
        return "w-full border border-slate-200 bg-slate-50 gap-2"

    direction = str(change_state.get("direction", "none"))
    multiplier = int(change_state.get("multiplier", 0) or 0)
    if direction == "up":
        if multiplier >= 3:
            return "w-full border border-rose-200 bg-rose-50 gap-2"
        return "w-full border border-amber-200 bg-amber-50 gap-2"
    if direction == "down":
        if multiplier >= 3:
            return "w-full border border-emerald-200 bg-emerald-50 gap-2"
        return "w-full border border-sky-200 bg-sky-50 gap-2"
    return "w-full border border-indigo-200 bg-indigo-50 gap-2"


def build_change_summary_icon(change_state: dict[str, object]) -> tuple[str, str]:
    if not bool(change_state.get("has_effective_change")):
        return "info", "text-slate-500"

    direction = str(change_state.get("direction", "none"))
    multiplier = int(change_state.get("multiplier", 0) or 0)
    if direction == "up":
        if multiplier >= 3:
            return "trending_up", "text-rose-700"
        return "north_east", "text-amber-700"
    if direction == "down":
        if multiplier >= 3:
            return "trending_down", "text-emerald-700"
        return "south_east", "text-sky-700"
    return "tune", "text-indigo-700"


def _build_impact_level(score: int) -> dict[str, str | int]:
    if score >= 4:
        return {
            "score": score,
            "label": "guclu",
            "emoji": "🟢",
            "text": "guclu",
            "classes": "bg-emerald-50 text-emerald-800 border border-emerald-200",
        }
    if score >= 2:
        return {
            "score": score,
            "label": "orta",
            "emoji": "🟡",
            "text": "orta",
            "classes": "bg-amber-50 text-amber-800 border border-amber-200",
        }
    if score >= 1:
        return {
            "score": score,
            "label": "dusuk",
            "emoji": "⚪",
            "text": "dusuk",
            "classes": "bg-slate-50 text-slate-700 border border-slate-200",
        }
    return {
        "score": score,
        "label": "sinirli",
        "emoji": "⚪",
        "text": "sinirli",
        "classes": "bg-slate-50 text-slate-500 border border-slate-200",
    }


def build_parameter_impact_map_model(
    selected_parameter_state: dict[str, dict[str, object]],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []

    for parameter_id, item in selected_parameter_state.items():
        parameter = item.get("definition")
        if parameter is None:
            continue

        current_value = item.get("current_value")
        new_value = item.get("new_value")
        has_explicit_values = (
            current_value is not None
            or new_value is not None
            or "current_value" in item
            or "new_value" in item
        )

        if has_explicit_values:
            change_state = analyze_parameter_change_state(
                parameter=parameter,
                current_value=current_value,
                new_value=new_value,
            )
            if not bool(change_state.get("has_effective_change")):
                continue
            multiplier = int(change_state.get("multiplier", 1) or 1)
        else:
            # Backward compatibility: when only parameter definition is provided,
            # render expected impact using base multiplier.
            change_state = {
                "has_effective_change": True,
                "reason": "",
                "multiplier": 1,
                "direction": "changed",
            }
            multiplier = 1

        scores = {dimension: 0 for dimension in PARAMETER_IMPACT_DIMENSIONS}
        matched_impacts: list[str] = []
        for raw_impact in getattr(parameter, "expected_impacts", ()) or ():
            impact_key = str(raw_impact or "").strip().lower()
            if not impact_key:
                continue
            matched_impacts.append(impact_key)
            for dimension, weight in PARAMETER_IMPACT_WEIGHTS.get(impact_key, {}).items():
                if dimension in scores:
                    scores[dimension] += int(weight) * multiplier

        row: dict[str, object] = {
            "parameter_id": parameter_id,
            "parameter_label": str(getattr(parameter, "label", parameter_id)),
            "matched_impacts": matched_impacts,
            "change_state": change_state,
        }
        for dimension in PARAMETER_IMPACT_DIMENSIONS:
            row[dimension] = _build_impact_level(scores[dimension])
        rows.append(row)

    return {
        "rows": rows,
        "has_data": bool(rows),
        "columns": list(PARAMETER_IMPACT_DIMENSIONS),
    }


def build_parameter_impact_summary_cards(impact_map_model: dict[str, object]) -> list[dict[str, str | int]]:
    rows = list(impact_map_model.get("rows", []))
    if not rows:
        return []

    cards: list[dict[str, str | int]] = []
    for dimension in PARAMETER_IMPACT_DIMENSIONS:
        best_row = max(
            rows,
            key=lambda item: int(dict(item.get(dimension, {})).get("score", 0)),
        )
        best_cell = dict(best_row.get(dimension, {}))
        cards.append(
            {
                "dimension": dimension,
                "title": f"En cok {format_impact_dimension_label(dimension)} etkileyen",
                "parameter_label": str(best_row.get("parameter_label", "-")),
                "level_text": str(best_cell.get("text", "sinirli")),
                "emoji": str(best_cell.get("emoji", "S")),
                "score": int(best_cell.get("score", 0)),
                "classes": str(best_cell.get("classes", "bg-slate-50 text-slate-700")),
            }
        )
    return cards


def build_parameter_impact_line_series(impact_map_model: dict[str, object]) -> list[dict[str, object]]:
    rows = list(impact_map_model.get("rows", []))
    if not rows:
        return []

    series: list[dict[str, object]] = [
        {
            "name": "Mevcut Durum",
            "values": [0 for _ in PARAMETER_IMPACT_DIMENSIONS],
            "color": "#64748b",
            "line_type": "dashed",
        }
    ]

    palette = ["#2563eb", "#0f766e", "#dc2626", "#ca8a04", "#7c3aed", "#0891b2"]
    combined_values = [0 for _ in PARAMETER_IMPACT_DIMENSIONS]

    for index, row in enumerate(rows):
        values: list[int] = []
        for dim_index, dimension in enumerate(PARAMETER_IMPACT_DIMENSIONS):
            score = int(dict(row.get(dimension, {})).get("score", 0))
            values.append(score)
            combined_values[dim_index] += score
        series.append(
            {
                "name": str(row.get("parameter_label", f"Parametre {index + 1}")),
                "values": values,
                "color": palette[index % len(palette)],
                "line_type": "solid",
            }
        )

    if len(rows) > 1:
        series.append(
            {
                "name": "Birlesik Senaryo",
                "values": combined_values,
                "color": "#111827",
                "line_type": "solid",
                "line_width": 4,
            }
        )

    return series


def build_single_parameter_impact_chart_options(
    parameter_label: str,
    dimension_scores: dict[str, int],
) -> dict[str, object]:
    labels = [format_impact_dimension_label(str(dimension)) for dimension in PARAMETER_IMPACT_DIMENSIONS]
    new_values = [int(dimension_scores.get(dimension, 0)) for dimension in PARAMETER_IMPACT_DIMENSIONS]
    axis_max = max([3, *new_values]) + 1
    safe_title = str(parameter_label).replace("'", "\\'")

    tooltip_formatter = (
        "function(params) {"
        " if (!params || !params.length) return '';"
        f" const title = '{safe_title}';"
        " const lines = [title];"
        " params.forEach(function(item) {"
        "   const value = Array.isArray(item.value) ? item.value[1] : item.value;"
        "   lines.push(item.marker + ' ' + item.seriesName + ': ' + String(value));"
        " });"
        " return lines.join('<br/>');"
        "}"
    )

    return {
        "tooltip": {"trigger": "axis", "formatter": tooltip_formatter},
        "legend": {"data": ["Mevcut Durum", "Yeni Durum"], "top": 4},
        "grid": {"left": 44, "right": 24, "top": 36, "bottom": 32, "containLabel": True},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {
            "type": "value",
            "name": "Goreli Etki",
            "min": 0,
            "max": axis_max,
            "splitLine": {"lineStyle": {"color": "#e2e8f0"}},
        },
        "series": [
            {
                "name": "Mevcut Durum",
                "type": "line",
                "data": [0 for _ in PARAMETER_IMPACT_DIMENSIONS],
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 8,
                "lineStyle": {"type": "dashed", "width": 2, "color": "#94a3b8"},
                "itemStyle": {"color": "#94a3b8"},
            },
            {
                "name": "Yeni Durum",
                "type": "line",
                "data": new_values,
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 8,
                "lineStyle": {"width": 3, "color": "#2563eb"},
                "itemStyle": {"color": "#2563eb"},
                "areaStyle": {"color": "rgba(37,99,235,0.10)"},
            },
        ],
    }


def build_multi_parameter_impact_chart_options(impact_map_model: dict[str, object]) -> dict[str, object]:
    labels = [format_impact_dimension_label(str(dimension)) for dimension in PARAMETER_IMPACT_DIMENSIONS]
    series_rows = build_parameter_impact_line_series(impact_map_model)
    max_value = 0
    chart_series: list[dict[str, object]] = []

    for row in series_rows:
        values = [int(value) for value in list(row.get("values", []))]
        if values:
            max_value = max(max_value, max(values))
        chart_series.append(
            {
                "name": str(row.get("name", "Seri")),
                "type": "line",
                "data": values,
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 9,
                "lineStyle": {
                    "type": str(row.get("line_type", "solid")),
                    "width": int(row.get("line_width", 3)),
                    "color": str(row.get("color", "#2563eb")),
                },
                "itemStyle": {"color": str(row.get("color", "#2563eb"))},
                "areaStyle": (
                    {"color": "rgba(15,118,110,0.08)"}
                    if str(row.get("name", "")) == "Birlesik Senaryo"
                    else None
                ),
            }
        )

    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 4},
        "grid": {"left": 44, "right": 24, "top": 44, "bottom": 32, "containLabel": True},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {
            "type": "value",
            "name": "Goreli Etki",
            "min": 0,
            "max": max(3, max_value) + 1,
            "splitLine": {"lineStyle": {"color": "#e2e8f0"}},
        },
        "series": chart_series,
    }

def parse_extra_match_text(extra_match_text: str) -> dict[str, str]:
    extra_matches = {}
    normalized = extra_match_text.strip()
    if not normalized:
        return extra_matches

    for part in normalized.split(","):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise DependencyAnalysisError(
                "Ek eslesme alani 'kolon=deger, kolon=deger' formatinda olmali."
            )
        column, value = item.split("=", 1)
        column = column.strip()
        value = value.strip()
        if not column or not value:
            raise DependencyAnalysisError(
                "Ek eslesme alani icinde kolon ve deger bos birakilamaz."
            )
        extra_matches[column] = value
    return extra_matches


def validate_match_value_type(dataset_name: str, match_column: str, match_value: str) -> None:
    column_types = KEY_COLUMN_TYPES.get(dataset_name, {})
    value_type = column_types.get(match_column, "string")
    if value_type == "integer":
        try:
            int(match_value)
        except ValueError as error:
            raise DependencyAnalysisError(
                f"{dataset_name} icin '{match_column}' sayisal olmalidir. Girilen deger: {match_value}"
            ) from error


def build_match_hint(dataset_name: str) -> str:
    if dataset_name == "construction_layers.csv":
        return (
            "Opsiyonel: construction_name=disduvar,name=beton "
            "(tek kaydi netlestirmek icin kullanin)"
        )
    return "Opsiyonel: kolon=deger, kolon=deger"


def build_simulation_record_choices(dataset_name: str) -> dict[str, dict[str, str]]:
    csv_path = Path("csv_output") / dataset_name
    if not csv_path.exists():
        return {}

    rows, _ = read_csv_rows(csv_path)
    choices: dict[str, dict[str, str]] = {}

    for row in rows:
        if dataset_name == "materials.csv":
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            choices[name] = {
                "match_column": "name",
                "match_value": name,
                "extra_matches": "",
            }
            continue

        if dataset_name == "construction_layers.csv":
            construction_name = str(row.get("construction_name", "")).strip()
            layer_index = str(row.get("layer_index", "")).strip()
            name = str(row.get("name", "")).strip()
            if not all([construction_name, layer_index, name]):
                continue
            label = f"{construction_name} | {layer_index} | {name}"
            choices[label] = {
                "match_column": "name",
                "match_value": name,
                "extra_matches": f"construction_name={construction_name},layer_index={layer_index}",
            }
            continue

    return choices


@lru_cache(maxsize=64)
def build_parameter_record_choices(dataset_name: str) -> dict[str, dict[str, object]]:
    csv_path = Path("csv_output") / dataset_name
    if not csv_path.exists():
        return {}

    rows, _ = read_csv_rows(csv_path)
    key_columns = list(DATASET_KEY_COLUMNS.get(dataset_name, {"name": "string"}).keys())
    choices: dict[str, dict[str, object]] = {}

    for row in rows:
        values = [str(row.get(column, "")).strip() for column in key_columns]
        if not all(values):
            continue

        label = values[0] if len(values) == 1 else " | ".join(values)
        extra_matches = {
            column: value
            for column, value in zip(key_columns[1:], values[1:])
            if value
        }
        choices[label] = {
            "match_column": key_columns[0],
            "match_value": values[0],
            "extra_matches": extra_matches,
            "row": {key: value for key, value in row.items() if key != "__row_id"},
        }

    return choices


def shorten_text(value: object, max_length: int = 36) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def build_chart_change_label(source_text: str, changed_field: str) -> str:
    source_text = str(source_text or "").strip()
    changed_field = str(changed_field or "").strip()

    if ":" in source_text:
        dataset_name, row_key = source_text.split(":", 1)
        dataset_name = dataset_name.replace(".csv", "")
        parts = [shorten_text(dataset_name, 18)]

        row_bits = [bit.strip() for bit in row_key.split("|") if bit.strip()]
        if row_bits:
            last_bit = row_bits[-1]
            if "=" in last_bit:
                _, value = last_bit.split("=", 1)
                parts.append(shorten_text(value, 18))
            else:
                parts.append(shorten_text(last_bit, 18))

        if changed_field:
            parts.append(shorten_text(changed_field, 18))
        return " / ".join(parts)

    return shorten_text(f"{source_text} / {changed_field}", 36)


def build_impact_rows_for_scenario(
    scenario_path: Path, scenario: dict, log_path: Path
) -> tuple[list[dict], str]:
    if not log_path.exists():
        return [], "Senaryo etkilerini gormek icin once hazirlik akislarini calistirin."

    log_rows, _ = read_log_rows(log_path)
    if not log_rows:
        return [], "Secili senaryo icin degisiklik kaydi bulunamadi."

    input_path = Path(scenario["input"])
    repo = CsvRepository(input_path.parent)
    operations_by_name = {
        operation.get("name", f"operation_{index}"): operation
        for index, operation in enumerate(scenario.get("operations", []), start=1)
    }

    impact_rows = []
    for log_row in log_rows:
        operation_name = str(log_row.get("islem", ""))
        operation = operations_by_name.get(operation_name)
        if operation is None:
            continue

        match = operation.get("match", {})
        match_column = str(match.get("column", "")).strip()
        match_value = str(match.get("value", "")).strip()
        changed_column = str(log_row.get("kolon", "")).strip()
        if not match_column or not match_value or not changed_column:
            continue

        try:
            impact_report = analyze_dependency_for_match(
                csv_root=input_path.parent,
                dataset_name=input_path.name,
                match_column=match_column,
                match_value=match_value,
                changed_column=changed_column,
            )
        except DependencyAnalysisError:
            continue

        old_value = str(log_row.get("eski_deger", ""))
        new_value = str(log_row.get("yeni_deger", ""))
        delta_text, direction = format_delta(old_value, new_value)
        old_number = try_parse_number(old_value)
        new_number = try_parse_number(new_value)
        delta_numeric = None
        if old_number is not None and new_number is not None:
            delta_numeric = new_number - old_number

        for item in impact_report["reports"]:
            impacts = item.get("impacts", [])
            if not impacts:
                impact_rows.append(
                    {
                        "id": f"{operation_name}-{changed_column}-empty",
                        "degisen_alan": changed_column,
                        "eski_deger": old_value or "-",
                        "yeni_deger": new_value or "-",
                        "degisim_miktari": delta_text,
                        "degisim_numeric": delta_numeric,
                        "yon": direction,
                        "etki_tipi": "Yok",
                        "etkilenen_veri": "-",
                        "etkilenen_satir": 0,
                        "kaynak": f"{match_column}={match_value}",
                        "neden": "Bagli etki bulunamadi.",
                    }
                )
                continue

            for impact in impacts:
                impact_rows.append(
                    {
                        "id": (
                            f"{operation_name}-{changed_column}-"
                            f"{impact['impact_type']}-{impact['dataset']}"
                        ),
                        "degisen_alan": changed_column,
                        "eski_deger": old_value or "-",
                        "yeni_deger": new_value or "-",
                        "degisim_miktari": delta_text,
                        "degisim_numeric": delta_numeric,
                        "yon": direction,
                        "etki_tipi": "Dogrudan" if impact["impact_type"] == "direct" else "Dolayli",
                        "etkilenen_veri": impact["dataset"],
                        "etkilenen_satir": impact["affected_row_count"],
                        "kaynak": f"{match_column}={match_value}",
                        "neden": impact["reason"],
                    }
                )

    if not impact_rows:
        return [], "Etki analizi icin uygun degisiklik kaydi bulunamadi."

    return impact_rows, (
        f"Senaryo: {scenario.get('scenario_name', scenario_path.stem)} | "
        f"Toplam etki kaydi: {len(impact_rows)}"
    )


def build_impact_rows_for_change_items(
    csv_root: Path, change_items: list[dict]
) -> tuple[list[dict], str]:
    if len(change_items) < 3:
        raise DependencyAnalysisError("Simulasyon icin en az 3 degisiklik girilmelidir.")

    repo = CsvRepository(csv_root)
    impact_rows = []

    for index, change_item in enumerate(change_items, start=1):
        dataset_name = str(change_item.get("dataset", "")).strip()
        match_column = str(change_item.get("match_column", "")).strip()
        match_value = str(change_item.get("match_value", "")).strip()
        changed_column = str(change_item.get("changed_column", "")).strip()
        new_value = str(change_item.get("new_value", "")).strip()
        extra_matches = parse_extra_match_text(str(change_item.get("extra_matches", "")))

        if not all([dataset_name, match_column, match_value, changed_column, new_value]):
            raise DependencyAnalysisError(f"{index}. degisiklik satiri eksik alan iceriyor.")

        if dataset_name not in SUPPORTED_FILES:
            raise DependencyAnalysisError(
                f"{dataset_name} coklu degisim simulasyonunda desteklenmiyor."
            )

        rules = SUPPORTED_FILES[dataset_name]
        if match_column not in rules["key_columns"]:
            allowed = ", ".join(sorted(rules["key_columns"]))
            raise DependencyAnalysisError(
                f"{dataset_name} icin eslestirme kolonu gecersiz: {match_column}. Izin verilenler: {allowed}"
            )
        if changed_column not in rules["editable_columns"]:
            allowed = ", ".join(sorted(rules["editable_columns"]))
            raise DependencyAnalysisError(
                f"{dataset_name} icin guncelleme kolonu gecersiz: {changed_column}. Izin verilenler: {allowed}"
            )

        validate_match_value_type(dataset_name, match_column, match_value)
        for extra_column, extra_value in extra_matches.items():
            if extra_column not in rules["key_columns"]:
                allowed = ", ".join(sorted(rules["key_columns"]))
                raise DependencyAnalysisError(
                    f"{dataset_name} icin ek eslesme kolonu gecersiz: {extra_column}. Izin verilenler: {allowed}"
                )
            validate_match_value_type(dataset_name, extra_column, extra_value)

        matched_rows = repo.find_rows(dataset_name, match_column, match_value)
        if extra_matches:
            matched_rows = [
                row
                for row in matched_rows
                if all(str(row.get(column, "")) == value for column, value in extra_matches.items())
            ]
        if not matched_rows:
            raise DependencyAnalysisError(
                f"{dataset_name} icinde {match_column}={match_value} icin kayit bulunamadi."
            )
        if dataset_name == "construction_layers.csv" and len(matched_rows) > 1:
            raise DependencyAnalysisError(
                "construction_layers.csv icin birden fazla kayit eslesti. "
                "Ek eslesme alanina ornek olarak 'construction_name=disduvar,name=beton' yazabilirsiniz."
            )

        old_values = sorted({str(row.get(changed_column, "")) for row in matched_rows})
        old_value = old_values[0] if len(old_values) == 1 else f"{len(old_values)} farkli deger"
        delta_text, direction = format_delta(old_value, new_value)
        old_number = try_parse_number(old_value)
        new_number = try_parse_number(new_value)
        delta_numeric = None
        if old_number is not None and new_number is not None:
            delta_numeric = new_number - old_number

        reports = [
            analyze_specific_row(repo, dataset_name, matched_row, changed_column)
            for matched_row in matched_rows
        ]

        for item in reports:
            source_text = f"{dataset_name}:{item['matched_row']['row_key']}"
            impacts = item.get("impacts", [])
            if not impacts:
                impact_rows.append(
                    {
                        "id": f"simulation-{index}-empty",
                        "degisen_alan": changed_column,
                        "eski_deger": old_value or "-",
                        "yeni_deger": new_value or "-",
                        "degisim_miktari": delta_text,
                        "degisim_numeric": delta_numeric,
                        "yon": direction,
                        "etki_tipi": "Yok",
                        "etkilenen_veri": "-",
                        "etkilenen_satir": 0,
                        "kaynak": source_text,
                        "neden": "Bagli etki bulunamadi.",
                    }
                )
                continue

            for impact in impacts:
                impact_rows.append(
                    {
                        "id": f"simulation-{index}-{impact['impact_type']}-{impact['dataset']}",
                        "degisen_alan": changed_column,
                        "eski_deger": old_value or "-",
                        "yeni_deger": new_value or "-",
                        "degisim_miktari": delta_text,
                        "degisim_numeric": delta_numeric,
                        "yon": direction,
                        "etki_tipi": "Dogrudan" if impact["impact_type"] == "direct" else "Dolayli",
                        "etkilenen_veri": impact["dataset"],
                        "etkilenen_satir": impact["affected_row_count"],
                        "kaynak": source_text,
                        "neden": impact["reason"],
                    }
                )

    return impact_rows, f"Coklu degisim simulasyonu | Degisiklik sayisi: {len(change_items)} | Toplam etki kaydi: {len(impact_rows)}"
def filter_impact_rows(
    impact_rows: list[dict],
    query: str = "",
    impact_type: str = "Tum Etkiler",
    sort_mode: str = "Varsayilan",
) -> list[dict]:
    filtered_rows = impact_rows
    normalized_query = query.strip().lower()

    if normalized_query:
        filtered_rows = [
            row
            for row in filtered_rows
            if any(
                normalized_query in str(row.get(field, "")).lower()
                for field in ["degisen_alan", "etkilenen_veri", "kaynak", "neden"]
            )
        ]

    if impact_type == "Sadece Dogrudan":
        filtered_rows = [row for row in filtered_rows if row.get("etki_tipi") == "Dogrudan"]
    elif impact_type == "Sadece Dolayli":
        filtered_rows = [row for row in filtered_rows if row.get("etki_tipi") == "Dolayli"]

    if sort_mode == "En Buyuk Degisim":
        filtered_rows = sorted(
            filtered_rows,
            key=lambda row: abs(row.get("degisim_numeric") or 0),
            reverse=True,
        )
    elif sort_mode == "En Fazla Etki":
        filtered_rows = sorted(
            filtered_rows,
            key=lambda row: int(row.get("etkilenen_satir", 0)),
            reverse=True,
        )

    return filtered_rows


def build_impact_summary(impact_rows: list[dict]) -> dict:
    if not impact_rows:
        return {
            "changed_fields": "-",
            "total_rows": 0,
            "direct_rows": 0,
            "indirect_rows": 0,
            "critical_message": "Henuz ozet olusturulacak etki kaydi yok.",
            "critical_tone": "neutral",
        }

    changed_fields = sorted(
        {
            str(row.get("degisen_alan", "")).strip()
            for row in impact_rows
            if str(row.get("degisen_alan", "")).strip()
        }
    )
    direct_rows = sum(
        int(row.get("etkilenen_satir", 0))
        for row in impact_rows
        if row.get("etki_tipi") == "Dogrudan"
    )
    indirect_rows = sum(
        int(row.get("etkilenen_satir", 0))
        for row in impact_rows
        if row.get("etki_tipi") == "Dolayli"
    )
    total_rows = direct_rows + indirect_rows

    if total_rows >= 20 or indirect_rows >= 15:
        critical_message = "Kritik etki: degisiklik genis bir bagimlilik zincirine yayiliyor."
        critical_tone = "critical"
    elif total_rows > 0:
        critical_message = "Degisiklik birden fazla bagli alani etkiliyor."
        critical_tone = "warning"
    else:
        critical_message = "Belirgin bagli etki tespit edilmedi."
        critical_tone = "neutral"

    return {
        "changed_fields": ", ".join(changed_fields) if changed_fields else "-",
        "total_rows": total_rows,
        "direct_rows": direct_rows,
        "indirect_rows": indirect_rows,
        "critical_message": critical_message,
        "critical_tone": critical_tone,
    }


def build_impact_chart_model(impact_rows: list[dict]) -> dict:
    change_groups = {}
    dataset_groups = {}

    for row in impact_rows:
        change_key = (str(row.get("kaynak", "")), str(row.get("degisen_alan", "")))
        if change_key not in change_groups:
            change_groups[change_key] = {
                "label": build_chart_change_label(change_key[0], change_key[1]),
                "old_value": row.get("eski_deger", "-"),
                "new_value": row.get("yeni_deger", "-"),
                "direct_rows": 0,
                "indirect_rows": 0,
            }
        if row.get("etki_tipi") == "Dogrudan":
            change_groups[change_key]["direct_rows"] += int(row.get("etkilenen_satir", 0))
        elif row.get("etki_tipi") == "Dolayli":
            change_groups[change_key]["indirect_rows"] += int(row.get("etkilenen_satir", 0))

        dataset_name = str(row.get("etkilenen_veri", "-"))
        impact_type = str(row.get("etki_tipi", "Yok"))
        dataset_groups.setdefault(
            dataset_name,
            {"dataset": dataset_name, "Dogrudan": 0, "Dolayli": 0},
        )
        if impact_type in {"Dogrudan", "Dolayli"}:
            dataset_groups[dataset_name][impact_type] += int(row.get("etkilenen_satir", 0))

    comparison_labels = []
    old_values = []
    new_values = []
    highlight_values = []
    for item in change_groups.values():
        comparison_labels.append(item["label"])
        old_number = try_parse_number(item["old_value"])
        new_number = try_parse_number(item["new_value"])
        delta_number = None
        if old_number is not None and new_number is not None:
            delta_number = new_number - old_number

        common_meta = {
            "old_value": item["old_value"],
            "new_value": item["new_value"],
            "delta": delta_number,
            "direct_rows": item["direct_rows"],
            "indirect_rows": item["indirect_rows"],
        }
        old_values.append(
            {
                "value": old_number,
                "meta": common_meta,
                "itemStyle": {"color": "#94a3b8"},
            }
        )
        new_values.append(
            {
                "value": new_number,
                "meta": common_meta,
                "itemStyle": {
                    "color": "#0f766e",
                    "borderColor": "#134e4a",
                    "borderWidth": 2,
                },
            }
        )
        highlight_values.append(
            {
                "value": new_number,
                "meta": common_meta,
                "itemStyle": {"color": "#dc2626"},
            }
        )

    dataset_labels = []
    direct_values = []
    indirect_values = []
    for item in sorted(
        dataset_groups.values(),
        key=lambda value: value["Dogrudan"] + value["Dolayli"],
        reverse=True,
    ):
        dataset_labels.append(shorten_text(item["dataset"], 20))
        direct_values.append(item["Dogrudan"])
        indirect_values.append(item["Dolayli"])

    relation_nodes = []
    relation_links = []
    source_nodes = {}
    direct_nodes = {}
    indirect_nodes = {}
    direct_link_totals = defaultdict(int)
    indirect_link_totals = defaultdict(int)

    for row in impact_rows:
        source_key = (str(row.get("kaynak", "-")), str(row.get("degisen_alan", "-")))
        source_id = f"source::{source_key[0]}::{source_key[1]}"
        source_label = build_chart_change_label(source_key[0], source_key[1]).replace(" / ", "\n")
        if source_id not in source_nodes:
            source_nodes[source_id] = {
                "id": source_id,
                "name": source_label,
                "symbolSize": 58,
                "category": 0,
                "x": 0,
                "y": 0,
                "fixed": True,
                "itemStyle": {"color": "#0f766e", "borderColor": "#134e4a", "borderWidth": 3},
                "value": {
                    "type": "source",
                    "label": source_label,
                },
            }

        target_dataset = str(row.get("etkilenen_veri", "-"))
        impact_type = str(row.get("etki_tipi", "Yok"))
        affected_rows = int(row.get("etkilenen_satir", 0))

        if impact_type == "Dogrudan":
            direct_id = f"direct::{target_dataset}"
            if direct_id not in direct_nodes:
                direct_nodes[direct_id] = {
                    "id": direct_id,
                    "name": shorten_text(target_dataset, 18),
                    "symbolSize": 38,
                    "category": 1,
                    "itemStyle": {"color": "#84cc16", "borderColor": "#4d7c0f", "borderWidth": 2},
                    "value": {
                        "type": "direct",
                        "label": target_dataset,
                    },
                }
            direct_link_totals[(source_id, direct_id)] += affected_rows
            continue

        if impact_type == "Dolayli":
            indirect_id = f"indirect::{target_dataset}"
            if indirect_id not in indirect_nodes:
                indirect_nodes[indirect_id] = {
                    "id": indirect_id,
                    "name": shorten_text(target_dataset, 18),
                    "symbolSize": 30,
                    "category": 2,
                    "itemStyle": {"color": "#f59e0b", "borderColor": "#b45309", "borderWidth": 2},
                    "value": {
                        "type": "indirect",
                        "label": target_dataset,
                    },
                }
            indirect_link_totals[(source_id, indirect_id)] += affected_rows

    relation_nodes.extend(source_nodes.values())
    relation_nodes.extend(direct_nodes.values())
    relation_nodes.extend(indirect_nodes.values())

    for (source_id, direct_id), total in direct_link_totals.items():
        relation_links.append(
            {
                "source": source_id,
                "target": direct_id,
                "value": total,
                "lineStyle": {"color": "#84cc16", "width": 3, "curveness": 0.08},
                "label": {"show": total > 0, "formatter": str(total)},
            }
        )

    for (source_id, indirect_id), total in indirect_link_totals.items():
        relation_links.append(
            {
                "source": source_id,
                "target": indirect_id,
                "value": total,
                "lineStyle": {"color": "#f59e0b", "type": "dashed", "width": 2, "curveness": 0.2},
                "label": {"show": False},
            }
        )

    return {
        "comparison": {
            "labels": comparison_labels,
            "old_values": old_values,
            "new_values": new_values,
            "highlight_values": highlight_values,
        },
        "distribution": {
            "labels": dataset_labels,
            "direct_values": direct_values,
            "indirect_values": indirect_values,
        },
        "relations": {
            "nodes": relation_nodes,
            "links": relation_links,
            "categories": [
                {"name": "Ana Degisim"},
                {"name": "Dogrudan Etki"},
                {"name": "Dolayli Etki"},
            ],
        },
    }


def build_parameter_change_chart_model(selected_parameter_state: dict[str, dict[str, object]]) -> dict:
    parameter_rows: list[dict[str, object]] = []
    skipped_labels: list[str] = []

    for parameter_id, item in selected_parameter_state.items():
        parameter = item.get("definition")
        if parameter is None:
            continue

        label = str(getattr(parameter, "label", parameter_id)).strip() or parameter_id
        before_number = try_parse_number(item.get("current_value"))
        if before_number is None:
            skipped_labels.append(label)
            continue

        parameter_rows.append(
            {
                "label": label,
                "base_value": before_number,
                "updated_value": item.get("new_value"),
                "unit": str(getattr(parameter, "unit", "") or "").strip(),
            }
        )

    overlay_model = build_parameter_value_overlay_model(parameter_rows)
    delta_values = [
        (
            float(updated_value) - float(base_value)
            if base_value is not None and updated_value is not None
            else None
        )
        for base_value, updated_value in zip(
            overlay_model.raw_base_series,
            overlay_model.raw_updated_series,
        )
    ]
    comparable_indexes = [index for index, value in enumerate(delta_values) if value is not None]
    changed_indexes = [
        index
        for index in comparable_indexes
        if delta_values[index] is not None and float(delta_values[index]) != 0.0
    ]

    return {
        "labels": overlay_model.labels,
        "before_values": overlay_model.base_series,
        "after_values": overlay_model.updated_series,
        "base_values": overlay_model.raw_base_series,
        "updated_values": overlay_model.raw_updated_series,
        "delta_values": delta_values,
        "units": overlay_model.units,
        "is_normalized": overlay_model.is_normalized,
        "missing_updated_labels": overlay_model.missing_updated_labels,
        "has_updated_data": bool(comparable_indexes),
        "changed_indexes": changed_indexes,
        "skipped_labels": skipped_labels,
        "skipped_count": len(skipped_labels),
        "has_data": bool(overlay_model.labels),
    }


def build_parameter_overlay_series(
    labels: list[str],
    before_values: list[float],
    after_values: list[float],
    max_step_lines: int = 4,
) -> list[dict[str, object]]:
    if not labels or not before_values or not after_values:
        return []

    series: list[dict[str, object]] = [
        {
            "name": BASE_SCENARIO_LABEL,
            "data": list(before_values),
            "origin": "base",
            "line_type": "line",
            "line_style": "solid",
            "color": "#1f2937",
        }
    ]

    changed_indexes = [
        index
        for index, (before_value, after_value) in enumerate(zip(before_values, after_values))
        if float(before_value) != float(after_value)
    ]

    step_palette = ["#0f766e", "#0369a1", "#ca8a04", "#9333ea"]
    running_values = list(before_values)
    step_indexes = changed_indexes[: max(0, int(max_step_lines))]

    for step_order, changed_index in enumerate(step_indexes, start=1):
        running_values[changed_index] = after_values[changed_index]
        line_color = step_palette[(step_order - 1) % len(step_palette)]
        series.append(
            {
                "name": f"Degisim {step_order}: {labels[changed_index]}",
                "data": list(running_values),
                "origin": "scenario",
                "line_type": "line",
                "line_style": "dashed",
                "color": line_color,
            }
        )

    # Always keep the final, fully updated line visible for quick before/after reading.
    if changed_indexes:
        series.append(
            {
                "name": "Scenario (Final)",
                "data": list(after_values),
                "origin": "scenario",
                "line_type": "line",
                "line_style": "dashed",
                "color": "#0f766e",
            }
        )
    else:
        series.append(
            {
                "name": "Scenario",
                "data": list(after_values),
                "origin": "scenario",
                "line_type": "line",
                "line_style": "dashed",
                "color": "#0f766e",
            }
        )

    return series


def build_energy_performance_chart_model(metrics_rows: list[dict[str, object]]) -> dict[str, object]:
    metric_order = [
        ("annual_heating", "Annual Heating"),
        ("annual_cooling", "Annual Cooling"),
        ("total_energy", "Total Energy"),
    ]
    metric_map = {
        str(row.get("metric_id", "")).strip(): row
        for row in metrics_rows
        if isinstance(row, dict)
    }

    labels: list[str] = []
    before_values: list[float | None] = []
    after_values: list[float | None] = []
    missing_labels: list[str] = []
    unit = "kWh"

    for metric_id, label in metric_order:
        labels.append(label)
        row = metric_map.get(metric_id, {})
        if isinstance(row, dict):
            row_unit = str(row.get("unit", "")).strip()
            if row_unit:
                unit = row_unit
        before_value = try_parse_number(row.get("base_value") if isinstance(row, dict) else None)
        after_value = try_parse_number(row.get("scenario_value") if isinstance(row, dict) else None)
        before_values.append(before_value)
        after_values.append(after_value)
        if before_value is None or after_value is None:
            missing_labels.append(label)

    has_data = any(
        before is not None and after is not None
        for before, after in zip(before_values, after_values)
    )

    return {
        "labels": labels,
        "before_values": before_values,
        "after_values": after_values,
        "missing_labels": missing_labels,
        "missing_count": len(missing_labels),
        "unit": unit,
        "has_data": has_data,
    }


def build_real_output_comparison_chart_model(
    metrics_rows: list[dict[str, object]],
    energy_unit_cost: float = 2.35,
    currency: str = "TRY",
) -> dict[str, object]:
    parameter_rows: list[dict[str, object]] = []

    energy_model = build_energy_performance_chart_model(metrics_rows)
    peak_model = build_peak_load_analysis(metrics_rows)
    zone_model = build_zone_portfolio_analysis(metrics_rows)
    cost_summary = build_cost_summary_from_metrics(
        metrics_rows,
        energy_unit_cost=energy_unit_cost,
        currency=currency,
    )

    for label, base_value, scenario_value in zip(
        list(energy_model.get("labels", [])),
        list(energy_model.get("before_values", [])),
        list(energy_model.get("after_values", [])),
    ):
        parameter_rows.append(
            {
                "label": label,
                "base_value": base_value,
                "updated_value": scenario_value,
                "unit": str(energy_model.get("unit", "kWh")),
            }
        )

    parameter_rows.extend(
        [
            {
                "label": "Peak Heating",
                "base_value": peak_model.get("peak_heating_base"),
                "updated_value": peak_model.get("peak_heating_scenario"),
                "unit": str(peak_model.get("unit", "kW")),
            },
            {
                "label": "Peak Cooling",
                "base_value": peak_model.get("peak_cooling_base"),
                "updated_value": peak_model.get("peak_cooling_scenario"),
                "unit": str(peak_model.get("unit", "kW")),
            },
        ]
    )

    zone_rows = [row for row in list(zone_model.get("zones", [])) if isinstance(row, dict)]
    if zone_rows:
        base_hot_hours = sum(int(row.get("base_hot_hours", 0)) for row in zone_rows)
        scenario_hot_hours = sum(int(row.get("scenario_hot_hours", 0)) for row in zone_rows)
        base_stability_values = [
            float(row.get("base_stability_std"))
            for row in zone_rows
            if row.get("base_stability_std") is not None
        ]
        scenario_stability_values = [
            float(row.get("scenario_stability_std"))
            for row in zone_rows
            if row.get("scenario_stability_std") is not None
        ]
        parameter_rows.extend(
            [
                {
                    "label": "Hot Hours",
                    "base_value": base_hot_hours,
                    "updated_value": scenario_hot_hours,
                    "unit": "hours",
                },
                {
                    "label": "Temp Stability Std",
                    "base_value": _safe_average(base_stability_values),
                    "updated_value": _safe_average(scenario_stability_values),
                    "unit": "C",
                },
            ]
        )

    parameter_rows.append(
        {
            "label": "Annual Cost",
            "base_value": cost_summary.get("base_cost"),
            "updated_value": cost_summary.get("scenario_cost"),
            "unit": currency,
        }
    )

    overlay_model = build_parameter_value_overlay_model(parameter_rows)
    delta_values = [
        (
            float(updated_value) - float(base_value)
            if base_value is not None and updated_value is not None
            else None
        )
        for base_value, updated_value in zip(
            overlay_model.raw_base_series,
            overlay_model.raw_updated_series,
        )
    ]
    comparable_indexes = [index for index, value in enumerate(delta_values) if value is not None]

    return {
        "labels": overlay_model.labels,
        "before_values": overlay_model.base_series,
        "after_values": overlay_model.updated_series,
        "base_values": overlay_model.raw_base_series,
        "updated_values": overlay_model.raw_updated_series,
        "delta_values": delta_values,
        "units": overlay_model.units,
        "is_normalized": overlay_model.is_normalized,
        "missing_updated_labels": overlay_model.missing_updated_labels,
        "has_data": bool(comparable_indexes),
    }


def build_parameter_waterfall_chart_model(change_chart_model: dict[str, object]) -> dict[str, object]:
    labels = list(change_chart_model.get("labels", []))
    deltas = list(change_chart_model.get("delta_values", []))
    units = list(change_chart_model.get("units", []))

    contribution_rows: list[tuple[str, float, str]] = []
    for label, delta, unit in zip(labels, deltas, units):
        if delta is None:
            continue
        numeric_delta = float(delta)
        if numeric_delta == 0.0:
            continue
        contribution_rows.append((str(label), numeric_delta, str(unit or "")))

    contribution_rows.sort(key=lambda item: abs(item[1]), reverse=True)

    if not contribution_rows:
        return {
            "labels": [],
            "helper_values": [],
            "increase_values": [],
            "decrease_values": [],
            "total_values": [],
            "running_values": [],
            "has_data": False,
            "summary": "Waterfall icin yeterli degisim bulunamadi.",
            "unit": "",
        }

    helper_values: list[float] = []
    increase_values: list[float] = []
    decrease_values: list[float] = []
    total_values: list[float | None] = []
    running_values: list[float] = []
    waterfall_labels: list[str] = []

    running = 0.0
    for label, delta, _ in contribution_rows:
        waterfall_labels.append(label)
        if delta >= 0:
            helper_values.append(running)
            increase_values.append(delta)
            decrease_values.append(0.0)
        else:
            helper_values.append(running + delta)
            increase_values.append(0.0)
            decrease_values.append(abs(delta))
        running += delta
        running_values.append(running)
        total_values.append(None)

    waterfall_labels.append("Net Total")
    helper_values.append(0.0)
    increase_values.append(0.0)
    decrease_values.append(0.0)
    total_values.append(running)
    running_values.append(running)

    dominant_unit = next((unit for _, _, unit in contribution_rows if unit), "")
    summary = (
        f"{len(contribution_rows)} parametre toplama {running:+.2f}"
        + (f" {dominant_unit}" if dominant_unit else "")
        + " etki etti."
    )

    return {
        "labels": waterfall_labels,
        "helper_values": helper_values,
        "increase_values": increase_values,
        "decrease_values": decrease_values,
        "total_values": total_values,
        "running_values": running_values,
        "has_data": True,
        "summary": summary,
        "unit": dominant_unit,
    }


MONTH_LABELS_TR = [
    "Ocak",
    "Subat",
    "Mart",
    "Nisan",
    "Mayis",
    "Haziran",
    "Temmuz",
    "Agustos",
    "Eylul",
    "Ekim",
    "Kasim",
    "Aralik",
]

COMFORT_BAND_MIN_C = 20.0
COMFORT_BAND_MAX_C = 26.0


def _month_key_to_index(raw_key: object) -> int | None:
    key = str(raw_key or "").strip().lower()
    if not key:
        return None

    month_aliases = {
        "1": 0,
        "01": 0,
        "jan": 0,
        "january": 0,
        "ocak": 0,
        "2": 1,
        "02": 1,
        "feb": 1,
        "february": 1,
        "subat": 1,
        "3": 2,
        "03": 2,
        "mar": 2,
        "march": 2,
        "mart": 2,
        "4": 3,
        "04": 3,
        "apr": 3,
        "april": 3,
        "nisan": 3,
        "5": 4,
        "05": 4,
        "may": 4,
        "mayis": 4,
        "6": 5,
        "06": 5,
        "jun": 5,
        "june": 5,
        "haziran": 5,
        "7": 6,
        "07": 6,
        "jul": 6,
        "july": 6,
        "temmuz": 6,
        "8": 7,
        "08": 7,
        "aug": 7,
        "august": 7,
        "agustos": 7,
        "9": 8,
        "09": 8,
        "sep": 8,
        "september": 8,
        "eylul": 8,
        "10": 9,
        "oct": 9,
        "october": 9,
        "ekim": 9,
        "11": 10,
        "nov": 10,
        "november": 10,
        "kasim": 10,
        "12": 11,
        "dec": 11,
        "december": 11,
        "aralik": 11,
    }
    return month_aliases.get(key)


def _build_month_vector(raw_values: object) -> list[float | None]:
    vector: list[float | None] = [None] * 12

    if isinstance(raw_values, list):
        for index, item in enumerate(raw_values[:12]):
            vector[index] = try_parse_number(item)
        return vector

    if isinstance(raw_values, dict):
        for month_key, value in raw_values.items():
            month_index = _month_key_to_index(month_key)
            if month_index is None:
                continue
            vector[month_index] = try_parse_number(value)
        return vector

    return vector


def _normalize_monthly_raw_value(raw_value: object) -> object:
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return raw_value


def _extract_monthly_pair(raw_value: object) -> tuple[list[float | None], list[float | None]]:
    normalized = _normalize_monthly_raw_value(raw_value)
    heating: list[float | None] = [None] * 12
    cooling: list[float | None] = [None] * 12

    if isinstance(normalized, dict):
        heating_source = None
        cooling_source = None
        for key, value in normalized.items():
            normalized_key = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalized_key in {"heating", "monthly_heating", "monthly_heating_kwh"}:
                heating_source = value
            elif normalized_key in {"cooling", "monthly_cooling", "monthly_cooling_kwh"}:
                cooling_source = value

        if heating_source is not None:
            heating = _build_month_vector(heating_source)
        if cooling_source is not None:
            cooling = _build_month_vector(cooling_source)

        if heating_source is None and cooling_source is None:
            heating = _build_month_vector(normalized)
        return heating, cooling

    if isinstance(normalized, list):
        heating = _build_month_vector(normalized)
        return heating, cooling

    return heating, cooling


def build_monthly_energy_chart_model(
    metrics_rows: list[dict[str, object]],
    scenario_name: str = "",
    scenario_order: int = 0,
) -> dict[str, object]:
    monthly_row = next(
        (
            row
            for row in metrics_rows
            if isinstance(row, dict)
            and str(row.get("metric_id", "")).strip() == "monthly_heating_cooling"
        ),
        {},
    )

    base_heating, base_cooling = _extract_monthly_pair(monthly_row.get("base_value"))
    scenario_heating, scenario_cooling = _extract_monthly_pair(monthly_row.get("scenario_value"))

    has_heating_data = any(item is not None for item in (base_heating + scenario_heating))
    has_cooling_data = any(item is not None for item in (base_cooling + scenario_cooling))

    missing_series: list[str] = []
    if not has_heating_data:
        missing_series.append("Heating")
    if not has_cooling_data:
        missing_series.append("Cooling")

    base_profile = get_base_scenario_visual_profile()
    scenario_profile = build_scenario_visual_profile(
        scenario_name=scenario_name,
        scenario_order=scenario_order,
    )

    return {
        "months": MONTH_LABELS_TR,
        "base_heating": base_heating,
        "scenario_heating": scenario_heating,
        "base_cooling": base_cooling,
        "scenario_cooling": scenario_cooling,
        "missing_series": missing_series,
        "has_data": has_heating_data or has_cooling_data,
        "unit": "kWh",
        "base_series_profile": base_profile,
        "scenario_series_profile": scenario_profile,
    }


def _normalize_zone_temperature_raw_value(raw_value: object) -> object:
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return raw_value


def _build_numeric_vector(values: object) -> list[float | None]:
    if not isinstance(values, list):
        return []
    return [try_parse_number(item) for item in values]


def _extract_zone_series(zone_value: object) -> tuple[list[str], list[float | None]]:
    if isinstance(zone_value, list):
        if zone_value and all(isinstance(item, dict) for item in zone_value):
            labels: list[str] = []
            values: list[float | None] = []
            for index, item in enumerate(zone_value):
                row = item if isinstance(item, dict) else {}
                label = str(
                    row.get("timestamp")
                    or row.get("time")
                    or row.get("label")
                    or f"t{index + 1}"
                )
                value = try_parse_number(
                    row.get("temperature")
                    or row.get("temp")
                    or row.get("value")
                )
                labels.append(label)
                values.append(value)
            return labels, values

        values = _build_numeric_vector(zone_value)
        labels = [f"t{index + 1}" for index in range(len(values))]
        return labels, values

    if isinstance(zone_value, dict):
        if "values" in zone_value:
            values = _build_numeric_vector(zone_value.get("values"))
            raw_labels = zone_value.get("timestamps") or zone_value.get("times") or zone_value.get("labels")
            if isinstance(raw_labels, list) and raw_labels:
                labels = [str(item) for item in raw_labels[: len(values)]]
                if len(labels) < len(values):
                    labels.extend(f"t{index + 1}" for index in range(len(labels), len(values)))
            else:
                labels = [f"t{index + 1}" for index in range(len(values))]
            return labels, values

        labels = [str(key) for key in zone_value.keys()]
        values = [try_parse_number(value) for value in zone_value.values()]
        return labels, values

    return [], []


def _extract_zone_temperature_map(raw_value: object) -> dict[str, dict[str, list[object]]]:
    normalized = _normalize_zone_temperature_raw_value(raw_value)
    zone_map: dict[str, dict[str, list[object]]] = {}

    if isinstance(normalized, dict):
        zones_object = normalized.get("zones")
        if isinstance(zones_object, dict):
            for zone_name, zone_value in zones_object.items():
                labels, values = _extract_zone_series(zone_value)
                zone_map[str(zone_name)] = {"labels": labels, "values": values}
            return zone_map

        if "zone" in normalized and "values" in normalized:
            labels, values = _extract_zone_series(normalized)
            zone_map[str(normalized.get("zone", "Zone"))] = {"labels": labels, "values": values}
            return zone_map

        ignored_keys = {"unit", "meta", "timestamps", "times", "labels", "time", "values"}
        for key, value in normalized.items():
            if str(key).strip().lower() in ignored_keys:
                continue
            if not isinstance(value, (list, dict)):
                continue
            labels, values = _extract_zone_series(value)
            if labels or values:
                zone_map[str(key)] = {"labels": labels, "values": values}
        return zone_map

    if isinstance(normalized, list) and normalized and all(isinstance(item, dict) for item in normalized):
        grouped_rows: dict[str, list[dict]] = {}
        for item in normalized:
            row = item if isinstance(item, dict) else {}
            zone_name = str(row.get("zone") or row.get("zone_name") or "Zone")
            grouped_rows.setdefault(zone_name, []).append(row)
        for zone_name, rows in grouped_rows.items():
            labels, values = _extract_zone_series(rows)
            zone_map[zone_name] = {"labels": labels, "values": values}

    return zone_map


def _align_zone_values(labels: list[str], values: list[float | None]) -> list[float | None]:
    aligned = list(values[: len(labels)])
    if len(aligned) < len(labels):
        aligned.extend([None] * (len(labels) - len(aligned)))
    return aligned


def build_zone_temperature_chart_model(
    metrics_rows: list[dict[str, object]],
    selected_zone: str = "",
    scenario_name: str = "",
    scenario_order: int = 0,
) -> dict[str, object]:
    zone_row = next(
        (
            row
            for row in metrics_rows
            if isinstance(row, dict)
            and str(row.get("metric_id", "")).strip() == "zone_temperatures"
        ),
        {},
    )

    base_map = _extract_zone_temperature_map(zone_row.get("base_value"))
    scenario_map = _extract_zone_temperature_map(zone_row.get("scenario_value"))

    zone_options = sorted(set(base_map.keys()) | set(scenario_map.keys()))
    resolved_zone = selected_zone if selected_zone in zone_options else (zone_options[0] if zone_options else "")

    base_series = base_map.get(resolved_zone, {"labels": [], "values": []})
    scenario_series = scenario_map.get(resolved_zone, {"labels": [], "values": []})

    labels = list(base_series.get("labels", []))
    if len(scenario_series.get("labels", [])) > len(labels):
        labels = list(scenario_series.get("labels", []))

    base_values = list(base_series.get("values", []))
    scenario_values = list(scenario_series.get("values", []))
    max_len = max(len(labels), len(base_values), len(scenario_values))

    if not labels and max_len > 0:
        labels = [f"t{index + 1}" for index in range(max_len)]
    elif len(labels) < max_len:
        labels.extend(f"t{index + 1}" for index in range(len(labels), max_len))

    base_values = _align_zone_values(labels, base_values)
    scenario_values = _align_zone_values(labels, scenario_values)

    has_base = any(value is not None for value in base_values)
    has_scenario = any(value is not None for value in scenario_values)
    missing_series: list[str] = []
    if not has_base:
        missing_series.append("Base Scenario")
    if not has_scenario:
        missing_series.append("Scenario")

    base_profile = get_base_scenario_visual_profile()
    scenario_profile = build_scenario_visual_profile(
        scenario_name=scenario_name,
        scenario_order=scenario_order,
    )

    return {
        "zone_options": zone_options,
        "selected_zone": resolved_zone,
        "time_labels": labels,
        "base_values": base_values,
        "scenario_values": scenario_values,
        "missing_series": missing_series,
        "has_data": has_base or has_scenario,
        "unit": "C",
        "base_series_profile": base_profile,
        "scenario_series_profile": scenario_profile,
    }


def _zone_numeric_values(values: list[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None]


def build_zone_temperature_comfort_summary(
    base_values: list[float | None],
    scenario_values: list[float | None],
    comfort_min_c: float = COMFORT_BAND_MIN_C,
    comfort_max_c: float = COMFORT_BAND_MAX_C,
) -> dict[str, object]:
    def count_out_of_band(series: list[float | None]) -> int:
        return sum(
            1
            for value in series
            if value is not None and (float(value) < comfort_min_c or float(value) > comfort_max_c)
        )

    base_numeric = _zone_numeric_values(base_values)
    scenario_numeric = _zone_numeric_values(scenario_values)

    return {
        "has_base": bool(base_numeric),
        "has_scenario": bool(scenario_numeric),
        "base_out_of_band": count_out_of_band(base_values),
        "scenario_out_of_band": count_out_of_band(scenario_values),
        "base_peak": max(base_numeric) if base_numeric else None,
        "scenario_peak": max(scenario_numeric) if scenario_numeric else None,
        "base_range": ((max(base_numeric) - min(base_numeric)) if base_numeric else None),
        "scenario_range": ((max(scenario_numeric) - min(scenario_numeric)) if scenario_numeric else None),
        "comfort_min_c": comfort_min_c,
        "comfort_max_c": comfort_max_c,
    }


def _safe_average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / float(len(values))


def _safe_stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = _safe_average(values)
    if mean is None:
        return None
    variance = sum((value - mean) ** 2 for value in values) / float(len(values))
    return variance**0.5


def _count_hot_cold_in_band(
    values: list[float | None],
    comfort_min_c: float,
    comfort_max_c: float,
) -> tuple[int, int, int]:
    hot_count = 0
    cold_count = 0
    in_band_count = 0
    for value in values:
        if value is None:
            continue
        numeric = float(value)
        if numeric > comfort_max_c:
            hot_count += 1
        elif numeric < comfort_min_c:
            cold_count += 1
        else:
            in_band_count += 1
    return hot_count, cold_count, in_band_count


def build_zone_portfolio_analysis(
    metrics_rows: list[dict[str, object]],
    comfort_min_c: float = COMFORT_BAND_MIN_C,
    comfort_max_c: float = COMFORT_BAND_MAX_C,
) -> dict[str, object]:
    zone_row = next(
        (
            row
            for row in metrics_rows
            if isinstance(row, dict)
            and str(row.get("metric_id", "")).strip() == "zone_temperatures"
        ),
        {},
    )

    base_map = _extract_zone_temperature_map(zone_row.get("base_value"))
    scenario_map = _extract_zone_temperature_map(zone_row.get("scenario_value"))
    zone_names = sorted(set(base_map.keys()) | set(scenario_map.keys()))

    zone_rows: list[dict[str, object]] = []
    for zone_name in zone_names:
        base_series = base_map.get(zone_name, {"labels": [], "values": []})
        scenario_series = scenario_map.get(zone_name, {"labels": [], "values": []})

        labels = list(base_series.get("labels", []))
        if len(scenario_series.get("labels", [])) > len(labels):
            labels = list(scenario_series.get("labels", []))
        max_len = max(
            len(labels),
            len(list(base_series.get("values", []))),
            len(list(scenario_series.get("values", []))),
        )
        if not labels and max_len > 0:
            labels = [f"t{index + 1}" for index in range(max_len)]
        elif len(labels) < max_len:
            labels.extend(f"t{index + 1}" for index in range(len(labels), max_len))

        base_values = _align_zone_values(labels, list(base_series.get("values", [])))
        scenario_values = _align_zone_values(labels, list(scenario_series.get("values", [])))
        base_numeric = _zone_numeric_values(base_values)
        scenario_numeric = _zone_numeric_values(scenario_values)

        base_avg = _safe_average(base_numeric)
        scenario_avg = _safe_average(scenario_numeric)
        base_hot, base_cold, base_in_band = _count_hot_cold_in_band(
            base_values,
            comfort_min_c,
            comfort_max_c,
        )
        scenario_hot, scenario_cold, scenario_in_band = _count_hot_cold_in_band(
            scenario_values,
            comfort_min_c,
            comfort_max_c,
        )

        sample_count = len([value for value in scenario_values if value is not None])
        zone_rows.append(
            {
                "zone": zone_name,
                "base_avg": base_avg,
                "scenario_avg": scenario_avg,
                "avg_delta": (
                    (float(scenario_avg) - float(base_avg))
                    if base_avg is not None and scenario_avg is not None
                    else None
                ),
                "base_hot_hours": base_hot,
                "scenario_hot_hours": scenario_hot,
                "base_cold_hours": base_cold,
                "scenario_cold_hours": scenario_cold,
                "base_in_band_hours": base_in_band,
                "scenario_in_band_hours": scenario_in_band,
                "scenario_in_band_ratio": (
                    (float(scenario_in_band) / float(sample_count) * 100.0)
                    if sample_count > 0
                    else None
                ),
                "base_stability_std": _safe_stddev(base_numeric),
                "scenario_stability_std": _safe_stddev(scenario_numeric),
                "scenario_peak": (max(scenario_numeric) if scenario_numeric else None),
                "sample_count": sample_count,
            }
        )

    most_heat_loss_zone = None
    loss_candidates = [
        row
        for row in zone_rows
        if row.get("avg_delta") is not None
    ]
    if loss_candidates:
        most_heat_loss_zone = min(loss_candidates, key=lambda item: float(item["avg_delta"]))

    most_overheating_zone = None
    overheating_candidates = [
        row
        for row in zone_rows
        if row.get("scenario_hot_hours") is not None
    ]
    if overheating_candidates:
        most_overheating_zone = max(
            overheating_candidates,
            key=lambda item: (
                int(item.get("scenario_hot_hours", 0)),
                float(item.get("scenario_peak") or float("-inf")),
            ),
        )

    return {
        "has_data": bool(zone_rows),
        "zones": zone_rows,
        "most_heat_loss_zone": most_heat_loss_zone,
        "most_overheating_zone": most_overheating_zone,
        "comfort_min_c": comfort_min_c,
        "comfort_max_c": comfort_max_c,
    }


def build_zone_heatmap_model(
    zone_model: dict[str, object],
    metric_mode: str = "temperature_vs_comfort",
) -> dict[str, object]:
    zone_rows = [row for row in list(zone_model.get("zones", [])) if isinstance(row, dict)]
    if not zone_rows:
        return {
            "x_labels": [],
            "y_labels": ["Avg Delta (C)", "Comfort Hours"],
            "data": [],
            "has_data": False,
            "summary": "Heatmap verisi bulunamadi.",
        }

    x_labels = [str(row.get("zone", "-")).strip() or "-" for row in zone_rows]
    metric_pairs = {
        "temperature_vs_comfort": (
            {
                "title": "Avg Delta (C)",
                "unit": "C",
                "values": [try_parse_number(row.get("avg_delta")) for row in zone_rows],
            },
            {
                "title": "Comfort Hours",
                "unit": "hours",
                "values": [
                    try_parse_number(row.get("scenario_in_band_hours")) for row in zone_rows
                ],
            },
            "Sicaklik sapmasi ve konfor saatleri birlikte izleniyor.",
        ),
        "overheat_vs_cold": (
            {
                "title": "Hot Hours",
                "unit": "hours",
                "values": [try_parse_number(row.get("scenario_hot_hours")) for row in zone_rows],
            },
            {
                "title": "Cold Hours",
                "unit": "hours",
                "values": [try_parse_number(row.get("scenario_cold_hours")) for row in zone_rows],
            },
            "Asiri isinma ve asiri soguma saatleri karsilastiriliyor.",
        ),
        "stability_vs_peak": (
            {
                "title": "Stability Std (C)",
                "unit": "C",
                "values": [
                    try_parse_number(row.get("scenario_stability_std")) for row in zone_rows
                ],
            },
            {
                "title": "Peak Temp (C)",
                "unit": "C",
                "values": [try_parse_number(row.get("scenario_peak")) for row in zone_rows],
            },
            "Sicaklik dalgalanmasi ve tepe degerleri birlikte degerlendiriliyor.",
        ),
    }
    selected_pair = metric_pairs.get(metric_mode, metric_pairs["temperature_vs_comfort"])
    first_metric = selected_pair[0]
    second_metric = selected_pair[1]
    mode_note = str(selected_pair[2])

    first_values = list(first_metric["values"])
    second_values = list(second_metric["values"])

    def normalize(values: list[float | None]) -> list[float | None]:
        numeric_values = [float(value) for value in values if value is not None]
        if not numeric_values:
            return [None for _ in values]
        min_value = min(numeric_values)
        max_value = max(numeric_values)
        if max_value == min_value:
            return [50.0 if value is not None else None for value in values]
        normalized_values: list[float | None] = []
        for value in values:
            if value is None:
                normalized_values.append(None)
            else:
                normalized_values.append((float(value) - min_value) / (max_value - min_value) * 100.0)
        return normalized_values

    first_norm = normalize(first_values)
    second_norm = normalize(second_values)

    metric_rows: list[dict[str, object]] = []
    if any(value is not None for value in first_values):
        metric_rows.append(
            {
                "title": str(first_metric["title"]),
                "unit": str(first_metric["unit"]),
                "raw": first_values,
                "norm": first_norm,
            }
        )
    if any(value is not None for value in second_values):
        metric_rows.append(
            {
                "title": str(second_metric["title"]),
                "unit": str(second_metric["unit"]),
                "raw": second_values,
                "norm": second_norm,
            }
        )

    if not metric_rows:
        return {
            "x_labels": x_labels,
            "y_labels": [str(first_metric["title"]), str(second_metric["title"])],
            "data": [],
            "has_data": False,
            "summary": "Heatmap metriklerinde cizilebilir veri bulunamadi.",
        }

    heatmap_data: list[list[object]] = []
    for y_index, metric_row in enumerate(metric_rows):
        norm_values = list(metric_row["norm"])
        raw_values = list(metric_row["raw"])
        for x_index, _ in enumerate(x_labels):
            if norm_values[x_index] is None:
                continue
            heatmap_data.append(
                [
                    x_index,
                    y_index,
                    float(norm_values[x_index]),
                    float(raw_values[x_index]) if raw_values[x_index] is not None else None,
                    str(metric_row["unit"]),
                ]
            )

    best_comfort_zone = max(
        (
            row for row in zone_rows
            if try_parse_number(row.get("scenario_in_band_hours")) is not None
        ),
        key=lambda item: float(try_parse_number(item.get("scenario_in_band_hours")) or 0),
        default=None,
    )
    worst_delta_zone = max(
        (
            row for row in zone_rows
            if try_parse_number(row.get("avg_delta")) is not None
        ),
        key=lambda item: abs(float(try_parse_number(item.get("avg_delta")) or 0)),
        default=None,
    )
    summary_parts = []
    if best_comfort_zone is not None:
        summary_parts.append(
            f"En cok konfor saati: {best_comfort_zone.get('zone', '-')}"
        )
    if worst_delta_zone is not None:
        summary_parts.append(
            f"En buyuk sicaklik sapmasi: {worst_delta_zone.get('zone', '-')}"
        )
    missing_metric_titles = []
    if not any(value is not None for value in first_values):
        missing_metric_titles.append(str(first_metric["title"]))
    if not any(value is not None for value in second_values):
        missing_metric_titles.append(str(second_metric["title"]))
    if missing_metric_titles:
        summary_parts.append("Eksik metrik: " + ", ".join(missing_metric_titles))
    summary_parts.append(mode_note)

    return {
        "x_labels": x_labels,
        "y_labels": [str(item["title"]) for item in metric_rows],
        "data": heatmap_data,
        "has_data": bool(heatmap_data),
        "summary": " | ".join(summary_parts) if summary_parts else "Heatmap hazirlandi.",
    }


def build_peak_load_analysis(metrics_rows: list[dict[str, object]]) -> dict[str, object]:
    metric_map = {
        str(row.get("metric_id", "")).strip(): row
        for row in metrics_rows
        if isinstance(row, dict)
    }

    def parse_metric(metric_id: str) -> tuple[float | None, float | None]:
        row = metric_map.get(metric_id, {})
        if not isinstance(row, dict):
            return None, None
        return (
            try_parse_number(row.get("base_value")),
            try_parse_number(row.get("scenario_value")),
        )

    peak_heating_base, peak_heating_scenario = parse_metric("peak_heating")
    peak_cooling_base, peak_cooling_scenario = parse_metric("peak_cooling")

    peak_heating_time_base, peak_heating_time_scenario = parse_metric("peak_heating_time")
    peak_cooling_time_base, peak_cooling_time_scenario = parse_metric("peak_cooling_time")

    return {
        "has_data": any(
            value is not None
            for value in [
                peak_heating_base,
                peak_heating_scenario,
                peak_cooling_base,
                peak_cooling_scenario,
            ]
        ),
        "peak_heating_base": peak_heating_base,
        "peak_heating_scenario": peak_heating_scenario,
        "peak_cooling_base": peak_cooling_base,
        "peak_cooling_scenario": peak_cooling_scenario,
        "peak_heating_time_base": peak_heating_time_base,
        "peak_heating_time_scenario": peak_heating_time_scenario,
        "peak_cooling_time_base": peak_cooling_time_base,
        "peak_cooling_time_scenario": peak_cooling_time_scenario,
        "unit": "kW",
    }


def build_seasonal_energy_analysis(monthly_chart_model: dict[str, object]) -> dict[str, object]:
    months = list(monthly_chart_model.get("months", MONTH_LABELS_TR))
    base_heating = list(monthly_chart_model.get("base_heating", []))
    scenario_heating = list(monthly_chart_model.get("scenario_heating", []))
    base_cooling = list(monthly_chart_model.get("base_cooling", []))
    scenario_cooling = list(monthly_chart_model.get("scenario_cooling", []))

    seasons = {
        "kis": [11, 0, 1],
        "yaz": [5, 6, 7],
        "gecis": [2, 3, 4, 8, 9, 10],
    }

    def sum_series(values: list[object], indices: list[int]) -> float:
        total = 0.0
        for index in indices:
            if index >= len(values):
                continue
            parsed = try_parse_number(values[index])
            if parsed is not None:
                total += float(parsed)
        return total

    season_rows: list[dict[str, object]] = []
    for season_key, indices in seasons.items():
        base_total = (
            sum_series(base_heating, indices)
            + sum_series(base_cooling, indices)
        )
        scenario_total = (
            sum_series(scenario_heating, indices)
            + sum_series(scenario_cooling, indices)
        )
        season_rows.append(
            {
                "season": season_key,
                "months": [months[index] for index in indices if index < len(months)],
                "base_total": base_total,
                "scenario_total": scenario_total,
                "delta": scenario_total - base_total,
            }
        )

    return {
        "has_data": bool(monthly_chart_model.get("has_data")),
        "seasons": season_rows,
        "unit": str(monthly_chart_model.get("unit", "kWh")),
    }


def build_structural_impact_view_model(structural_impact_model: dict[str, object]) -> dict:
    direct_rows = list(structural_impact_model.get("direct_rows", []))
    indirect_rows = list(structural_impact_model.get("indirect_rows", []))
    layer_rows = list(structural_impact_model.get("layer_rows", []))

    direct_dataset_count = len({str(row.get("dataset", "")) for row in direct_rows if row.get("dataset")})
    indirect_dataset_count = len({str(row.get("dataset", "")) for row in indirect_rows if row.get("dataset")})
    layer_dataset_count = len({str(row.get("target_dataset", "")) for row in layer_rows if row.get("target_dataset")})
    total_direct_rows = sum(int(row.get("affected_row_count", 0)) for row in direct_rows)

    nodes = []
    links = []
    seen_nodes = set()

    for row in direct_rows:
        trigger = str(row.get("trigger", "-"))
        dataset = str(row.get("dataset", "-"))
        trigger_id = f"trigger::{trigger}"
        dataset_id = f"direct::{dataset}"
        if trigger_id not in seen_nodes:
            nodes.append(
                {
                    "name": trigger_id,
                    "value": trigger,
                    "symbolSize": 40,
                    "category": 0,
                    "dataset_filter": "",
                }
            )
            seen_nodes.add(trigger_id)
        if dataset_id not in seen_nodes:
            nodes.append(
                {
                    "name": dataset_id,
                    "value": dataset,
                    "symbolSize": 26,
                    "category": 1,
                    "dataset_filter": dataset,
                }
            )
            seen_nodes.add(dataset_id)
        links.append(
            {
                "source": trigger_id,
                "target": dataset_id,
                "value": int(row.get("affected_row_count", 0)),
            }
        )

    for row in indirect_rows:
        trigger = str(row.get("trigger", "-"))
        dataset = str(row.get("dataset", "-"))
        trigger_id = f"trigger::{trigger}"
        dataset_id = f"indirect::{dataset}"
        if trigger_id not in seen_nodes:
            nodes.append(
                {
                    "name": trigger_id,
                    "value": trigger,
                    "symbolSize": 40,
                    "category": 0,
                    "dataset_filter": "",
                }
            )
            seen_nodes.add(trigger_id)
        if dataset_id not in seen_nodes:
            nodes.append(
                {
                    "name": dataset_id,
                    "value": dataset,
                    "symbolSize": 24,
                    "category": 2,
                    "dataset_filter": dataset,
                }
            )
            seen_nodes.add(dataset_id)
        links.append(
            {
                "source": trigger_id,
                "target": dataset_id,
                "value": 1,
            }
        )

    for row in layer_rows:
        source_key = str(row.get("source_row_key", "-"))
        target_dataset = str(row.get("target_dataset", "-"))
        source_id = f"layer-source::{source_key}"
        target_id = f"layer-target::{target_dataset}"
        if source_id not in seen_nodes:
            nodes.append(
                {
                    "name": source_id,
                    "value": shorten_text(source_key, 26),
                    "symbolSize": 22,
                    "category": 3,
                    "dataset_filter": "",
                }
            )
            seen_nodes.add(source_id)
        if target_id not in seen_nodes:
            nodes.append(
                {
                    "name": target_id,
                    "value": target_dataset,
                    "symbolSize": 20,
                    "category": 4,
                    "dataset_filter": target_dataset,
                }
            )
            seen_nodes.add(target_id)
        links.append(
            {
                "source": source_id,
                "target": target_id,
                "value": 1,
            }
        )

    graph = {
        "tooltip": {"show": True},
        "legend": [{"data": ["Degisen Parametre", "Dogrudan Tablo", "Dolayli Veri", "Katman Kaynagi", "Katman Hedefi"]}],
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "roam": True,
                "label": {"show": True, "formatter": "{b}"},
                "force": {"repulsion": 220, "edgeLength": 110},
                "data": nodes,
                "links": links,
                "categories": [
                    {"name": "Degisen Parametre"},
                    {"name": "Dogrudan Tablo"},
                    {"name": "Dolayli Veri"},
                    {"name": "Katman Kaynagi"},
                    {"name": "Katman Hedefi"},
                ],
                "lineStyle": {"opacity": 0.8, "width": 2, "curveness": 0.12},
            }
        ],
    }

    return {
        "summary_cards": {
            "direct_dataset_count": direct_dataset_count,
            "indirect_dataset_count": indirect_dataset_count,
            "layer_dataset_count": layer_dataset_count,
            "total_direct_rows": total_direct_rows,
        },
        "graph": graph,
    }


def filter_structural_impact_rows(
    structural_impact_model: dict[str, object],
    dataset_filter: str = "Tum Veri Setleri",
) -> dict[str, list[dict]]:
    if not dataset_filter or dataset_filter == "Tum Veri Setleri":
        return {
            "direct_rows": list(structural_impact_model.get("direct_rows", [])),
            "indirect_rows": list(structural_impact_model.get("indirect_rows", [])),
            "layer_rows": list(structural_impact_model.get("layer_rows", [])),
            "layer_impact_rows": list(structural_impact_model.get("layer_impact_rows", [])),
            "surface_impact_rows": list(structural_impact_model.get("surface_impact_rows", [])),
        }

    return {
        "direct_rows": [
            row
            for row in structural_impact_model.get("direct_rows", [])
            if str(row.get("dataset", "")) == dataset_filter
        ],
        "indirect_rows": [
            row
            for row in structural_impact_model.get("indirect_rows", [])
            if str(row.get("dataset", "")) == dataset_filter
        ],
        "layer_rows": [
            row
            for row in structural_impact_model.get("layer_rows", [])
            if str(row.get("target_dataset", "")) == dataset_filter
        ],
        "layer_impact_rows": list(structural_impact_model.get("layer_impact_rows", [])),
        "surface_impact_rows": [
            row
            for row in structural_impact_model.get("surface_impact_rows", [])
            if not dataset_filter
            or dataset_filter == "Tum Veri Setleri"
            or str(row.get("dataset", "")) == dataset_filter
        ],
    }


def summarize_structural_impact_cards(
    structural_impact_model: dict[str, object],
    filtered_structural_rows: dict[str, list[dict]],
) -> dict[str, dict[str, int | str]]:
    total_direct_dataset_count = len(
        {str(row.get("dataset", "")) for row in structural_impact_model.get("direct_rows", []) if row.get("dataset")}
    )
    total_indirect_dataset_count = len(
        {str(row.get("dataset", "")) for row in structural_impact_model.get("indirect_rows", []) if row.get("dataset")}
    )
    total_layer_dataset_count = len(
        {
            str(row.get("target_dataset", ""))
            for row in structural_impact_model.get("layer_rows", [])
            if row.get("target_dataset")
        }
    )
    total_direct_rows = sum(
        int(row.get("affected_row_count", 0))
        for row in structural_impact_model.get("direct_rows", [])
    )

    filtered_direct_dataset_count = len(
        {str(row.get("dataset", "")) for row in filtered_structural_rows.get("direct_rows", []) if row.get("dataset")}
    )
    filtered_indirect_dataset_count = len(
        {str(row.get("dataset", "")) for row in filtered_structural_rows.get("indirect_rows", []) if row.get("dataset")}
    )
    filtered_layer_dataset_count = len(
        {
            str(row.get("target_dataset", ""))
            for row in filtered_structural_rows.get("layer_rows", [])
            if row.get("target_dataset")
        }
    )
    filtered_direct_rows = sum(
        int(row.get("affected_row_count", 0))
        for row in filtered_structural_rows.get("direct_rows", [])
    )

    def card(current: int, total: int) -> dict[str, int | str]:
        return {
            "current": current,
            "total": total,
            "caption": f"Filtre: {current} / Toplam: {total}",
        }

    return {
        "direct_dataset_count": card(filtered_direct_dataset_count, total_direct_dataset_count),
        "indirect_dataset_count": card(filtered_indirect_dataset_count, total_indirect_dataset_count),
        "layer_dataset_count": card(filtered_layer_dataset_count, total_layer_dataset_count),
        "total_direct_rows": card(filtered_direct_rows, total_direct_rows),
    }


def group_layer_impact_rows_by_construction(
    layer_impact_rows: list[dict],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict]] = {}

    for row in layer_impact_rows:
        construction_label = str(row.get("construction_names", "")).strip() or "Construction Baglantisi Yok"
        grouped.setdefault(construction_label, []).append(row)

    groups = []
    for construction_label, rows in grouped.items():
        changed_count = sum(1 for row in rows if str(row.get("badge", "")) == "Degisen Layer")
        impacted_count = len(rows) - changed_count
        groups.append(
            {
                "construction_label": construction_label,
                "rows": rows,
                "row_count": len(rows),
                "changed_count": changed_count,
                "impacted_count": impacted_count,
            }
        )

    return sorted(
        groups,
        key=lambda item: (
            0 if int(item["changed_count"]) > 0 else 1,
            -int(item["changed_count"]),
            -int(item["row_count"]),
            str(item["construction_label"]).lower(),
        ),
    )


def build_layer_impact_chart_model(layer_impact_rows: list[dict]) -> dict[str, object]:
    groups = group_layer_impact_rows_by_construction(layer_impact_rows)
    labels: list[str] = []
    changed_values: list[int] = []
    unchanged_values: list[int] = []
    impact_levels: list[str] = []

    for group in groups:
        row_count = int(group.get("row_count", 0))
        changed_count = int(group.get("changed_count", 0))
        impacted_count = int(group.get("impacted_count", 0))
        ratio = (changed_count / row_count) if row_count > 0 else 0.0
        if ratio >= 0.5:
            impact_level = "Yuksek"
        elif ratio >= 0.2:
            impact_level = "Orta"
        else:
            impact_level = "Dusuk"

        labels.append(shorten_text(str(group.get("construction_label", "-")), 28))
        changed_values.append(changed_count)
        unchanged_values.append(impacted_count)
        impact_levels.append(impact_level)

    return {
        "labels": labels,
        "changed_values": changed_values,
        "unchanged_values": unchanged_values,
        "impact_levels": impact_levels,
        "has_data": bool(labels),
    }


def build_combined_impact_summary(structural_impact_model: dict[str, object]) -> dict[str, object]:
    layer_rows = list(structural_impact_model.get("layer_impact_rows", []))
    surface_rows = list(structural_impact_model.get("surface_impact_rows", []))

    changed_fields = sorted(
        {
            str(row.get("changed_field", "")).strip()
            for row in [*layer_rows, *surface_rows]
            if str(row.get("changed_field", "")).strip()
        }
    )

    construction_field_map: dict[str, set[str]] = {}
    for row in layer_rows:
        construction_names = str(row.get("construction_names", "")).strip()
        changed_field = str(row.get("changed_field", "")).strip()
        if not construction_names or not changed_field:
            continue
        for construction_name in [item.strip() for item in construction_names.split(",") if item.strip()]:
            construction_field_map.setdefault(construction_name, set()).add(changed_field)

    overlapping_constructions = [
        {
            "construction_name": construction_name,
            "changed_fields": sorted(fields),
            "changed_field_count": len(fields),
        }
        for construction_name, fields in construction_field_map.items()
        if len(fields) > 1
    ]
    overlapping_constructions.sort(
        key=lambda item: (-int(item["changed_field_count"]), str(item["construction_name"]).lower())
    )

    surface_field_map: dict[tuple[str, str], set[str]] = {}
    surface_meta: dict[tuple[str, str], dict[str, str]] = {}
    for row in surface_rows:
        surface_kind = str(row.get("surface_kind", "")).strip() or "-"
        surface_name = str(row.get("surface_name", "")).strip() or "-"
        changed_field = str(row.get("changed_field", "")).strip()
        if not changed_field:
            continue
        key = (surface_kind, surface_name)
        surface_field_map.setdefault(key, set()).add(changed_field)
        surface_meta[key] = {
            "surface_kind": surface_kind,
            "surface_name": surface_name,
            "construction_name": str(row.get("construction_name", "")).strip() or "-",
        }

    overlapping_surfaces = []
    for key, fields in surface_field_map.items():
        if len(fields) <= 1:
            continue
        meta = surface_meta[key]
        overlapping_surfaces.append(
            {
                "surface_kind": meta["surface_kind"],
                "surface_name": meta["surface_name"],
                "construction_name": meta["construction_name"],
                "changed_fields": sorted(fields),
                "changed_field_count": len(fields),
            }
        )
    overlapping_surfaces.sort(
        key=lambda item: (
            -int(item["changed_field_count"]),
            str(item["surface_kind"]).lower(),
            str(item["surface_name"]).lower(),
        )
    )

    overlapping_group_count = len(overlapping_constructions) + len(overlapping_surfaces)
    if overlapping_group_count >= 3:
        tone = "critical"
        message = "Birlesik etki yuksek: birden fazla degisim ayni construction veya yuzeylerde cakisiyor."
    elif overlapping_group_count > 0:
        tone = "warning"
        message = "Birlesik etki bulundu: bazı degisimler ayni construction veya yuzeyler uzerinde birikiyor."
    elif len(changed_fields) > 1:
        tone = "neutral"
        message = "Birden fazla degisim var, ancak belirgin bir construction/yuzey cakismasi tespit edilmedi."
    else:
        tone = "neutral"
        message = "Su anda tekil bir etki gorunuyor."

    return {
        "changed_fields": changed_fields,
        "changed_field_count": len(changed_fields),
        "overlapping_constructions": overlapping_constructions[:5],
        "overlapping_surfaces": overlapping_surfaces[:5],
        "overlapping_group_count": overlapping_group_count,
        "tone": tone,
        "message": message,
    }


def build_runner_status_view_model(
    status_history: list[RunnerStatusEvent] | list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    normalized_history: list[dict[str, str]] = []
    for item in status_history or []:
        if isinstance(item, RunnerStatusEvent):
            normalized_history.append(
                {
                    "status": item.status,
                    "label": item.label,
                    "detail": item.detail,
                }
            )
        elif isinstance(item, dict):
            normalized_history.append(
                {
                    "status": str(item.get("status", "")).strip(),
                    "label": str(item.get("label", "")).strip(),
                    "detail": str(item.get("detail", "")).strip(),
                }
            )

    status_index = {status: index for index, status in enumerate(RUNNER_STATUS_ORDER)}
    latest_status = normalized_history[-1]["status"] if normalized_history else "hazir"
    latest_index = status_index.get(latest_status, 0)
    is_error = latest_status == "hata"
    latest_details: dict[str, str] = {}
    for item in normalized_history:
        status = item["status"]
        detail = item["detail"]
        if status and detail:
            latest_details[status] = detail

    view_rows = []
    for index, status in enumerate(RUNNER_STATUS_ORDER):
        label = RUNNER_STATUS_LABELS.get(status, status.replace("_", " ").title())
        detail = latest_details.get(status, "")
        if is_error and status == "hata":
            tone = "negative"
            badge = "Hata"
        elif status == latest_status and status not in {"tamamlandi", "hata"}:
            tone = "warning"
            badge = "Aktif"
        elif index < latest_index or (status == latest_status and status == "tamamlandi"):
            tone = "positive"
            badge = "Tamam"
        else:
            tone = "neutral"
            badge = "Bekliyor"

        view_rows.append(
            {
                "status": status,
                "label": label,
                "detail": detail,
                "tone": tone,
                "badge": badge,
            }
        )

    return view_rows


def build_recent_scenarios_markdown(manifests: list[dict]) -> str:
    if not manifests:
        return "Henuz senaryo cikti paketi uretilmedi."

    recent_entries = manifests[-5:]
    lines = []
    for manifest in reversed(recent_entries):
        lines.append(
            f"- **{manifest.get('scenario_name', '-')}** | "
            f"degisen alan: {manifest.get('changed_field_count', 0)} | "
            f"islem: {manifest.get('operation_count', 0)}"
        )
    return "\n".join(lines)


def scenario_output_targets(scenario_path: Path) -> tuple[Path, Path, Path]:
    scenario = load_scenario_definition(scenario_path)
    scenario_copy = deepcopy(scenario)
    input_path = Path(scenario_copy["input"])
    return build_output_paths(scenario_copy["scenario_name"], input_path, SIMULATION_OUTPUT_DIR)


def parse_parameter_page_query(query_params: dict | object | None) -> dict[str, object]:
    if query_params is None:
        return {
            "impact_dataset": "Tum Veri Setleri",
            "category": "",
            "search": "",
            "scenario_name": "",
            "scenario_description": "",
            "selected_parameter_ids": [],
            "selected_parameter_state": {},
        }

    impact_dataset = str(getattr(query_params, "get", lambda *_: "")("impact_dataset", "")).strip()
    category = str(getattr(query_params, "get", lambda *_: "")("category", "")).strip()
    search = str(getattr(query_params, "get", lambda *_: "")("search", "")).strip()
    scenario_name = str(getattr(query_params, "get", lambda *_: "")("scenario_name", "")).strip()
    scenario_description = str(
        getattr(query_params, "get", lambda *_: "")("scenario_description", "")
    ).strip()
    selected_raw = str(getattr(query_params, "get", lambda *_: "")("selected", "")).strip()
    selected_state_raw = str(
        getattr(query_params, "get", lambda *_: "")("selection_state", "")
    ).strip()
    selected_parameter_ids = [item.strip() for item in selected_raw.split(",") if item.strip()]
    selected_parameter_state = parse_selected_parameter_state(selected_state_raw)

    return {
        "impact_dataset": impact_dataset or "Tum Veri Setleri",
        "category": category,
        "search": search,
        "scenario_name": scenario_name,
        "scenario_description": scenario_description,
        "selected_parameter_ids": selected_parameter_ids,
        "selected_parameter_state": selected_parameter_state,
    }


def parse_selected_parameter_state(raw_state: str) -> dict[str, dict[str, str]]:
    normalized = str(raw_state or "").strip()
    if not normalized:
        return {}

    try:
        decoded = json.loads(normalized)
    except json.JSONDecodeError:
        return {}

    if not isinstance(decoded, dict):
        return {}

    parsed = {}
    for parameter_id, payload in decoded.items():
        if not isinstance(parameter_id, str) or not isinstance(payload, dict):
            continue
        record_label = str(payload.get("record_label", "")).strip()
        new_value = str(payload.get("new_value", "")).strip()
        if not record_label and not new_value:
            continue
        parsed[parameter_id] = {
            "record_label": record_label,
            "new_value": new_value,
        }
    return parsed


def serialize_selected_parameter_state(
    selected_parameter_state: dict[str, dict[str, object]] | None,
) -> str:
    if not selected_parameter_state:
        return ""

    serialized = {}
    for parameter_id, payload in selected_parameter_state.items():
        record_label = str(payload.get("record_label", "")).strip()
        new_value = str(payload.get("new_value", "")).strip()
        if not record_label and not new_value:
            continue
        serialized[str(parameter_id)] = {
            "record_label": record_label,
            "new_value": new_value,
        }

    if not serialized:
        return ""
    return json.dumps(serialized, ensure_ascii=False, separators=(",", ":"))


def build_parameter_page_url(
    dataset_filter: str = "Tum Veri Setleri",
    category: str = "",
    search_query: str = "",
    scenario_name: str = "",
    scenario_description: str = "",
    selected_parameter_ids: list[str] | None = None,
    selected_parameter_state: dict[str, dict[str, object]] | None = None,
) -> str:
    params = {}
    normalized_filter = str(dataset_filter or "").strip()
    normalized_category = str(category or "").strip()
    normalized_search = str(search_query or "").strip()
    normalized_scenario_name = str(scenario_name or "").strip()
    normalized_scenario_description = str(scenario_description or "").strip()
    normalized_selected = [
        str(item).strip()
        for item in (selected_parameter_ids or [])
        if str(item).strip()
    ]
    serialized_selected_state = serialize_selected_parameter_state(selected_parameter_state)

    if normalized_filter and normalized_filter != "Tum Veri Setleri":
        params["impact_dataset"] = normalized_filter
    if normalized_category and normalized_category != "Tum Kategoriler":
        params["category"] = normalized_category
    if normalized_search:
        params["search"] = normalized_search
    if normalized_scenario_name:
        params["scenario_name"] = normalized_scenario_name
    if normalized_scenario_description:
        params["scenario_description"] = normalized_scenario_description
    if normalized_selected:
        params["selected"] = ",".join(normalized_selected)
    if serialized_selected_state:
        params["selection_state"] = serialized_selected_state

    if not params:
        return "/parameters"
    return f"/parameters?{urlencode(params)}"


def build_absolute_parameter_page_url(base_origin: str, path: str) -> str:
    normalized_origin = str(base_origin or "").rstrip("/")
    normalized_path = str(path or "").strip() or "/parameters"
    if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
        return normalized_path
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    if not normalized_origin:
        return normalized_path
    return f"{normalized_origin}{normalized_path}"


def build_share_qr_service_url(absolute_url: str, size: int = 160) -> str:
    normalized_url = str(absolute_url or "").strip()
    if not normalized_url:
        return ""
    encoded_url = quote(normalized_url, safe="")
    return (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size={int(size)}x{int(size)}&data={encoded_url}"
    )

@ui.page("/parameters")
def parameter_selection_page() -> None:
    ui.page_title("Parametre Secimi")
    dark_mode = ui.dark_mode()
    ui.add_head_html(
        """
        <style>
        :root {
            --ui-primary: #2563eb;
            --ui-primary-soft: #dbeafe;
            --ui-success: #059669;
            --ui-success-soft: #d1fae5;
            --ui-warning: #d97706;
            --ui-warning-soft: #fef3c7;
            --ui-surface: #ffffff;
            --ui-surface-muted: #f8fafc;
            --ui-text-muted: #64748b;
            --ui-border: #e2e8f0;
        }
        body {
            background: linear-gradient(180deg, #f8fafc 0%, #eef4ff 100%);
        }
        @keyframes parameterFadeSlide {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .parameter-panel {
            animation: parameterFadeSlide 0.28s ease-out;
        }
        .parameter-shell {
            background: color-mix(in srgb, var(--ui-surface) 78%, transparent);
            border: 1px solid rgba(148, 163, 184, 0.22);
            box-shadow: 0 24px 80px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(10px);
        }
        .parameter-category-radio .q-radio {
            width: 100%;
            margin: 0;
            padding: 0;
        }
        .parameter-category-radio .q-radio__label {
            width: 100%;
            padding: 0.85rem 1rem;
            border-radius: 14px;
            border: 1px solid transparent;
            background: var(--ui-surface);
            color: #334155;
            transition: all 0.18s ease;
            font-weight: 500;
        }
        .parameter-category-radio .q-radio:hover .q-radio__label {
            background: #f8fafc;
            border-color: #dbeafe;
            color: #0f172a;
        }
        .parameter-category-radio .q-radio[aria-checked="true"] .q-radio__label {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-color: #93c5fd;
            color: #0f172a;
            box-shadow: inset 3px 0 0 #2563eb;
        }
        .parameter-category-radio .q-radio__inner {
            color: #2563eb;
        }
        .parameter-category-list {
            gap: 0.5rem;
        }
        .parameter-category-item {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            padding: 0.9rem 1rem;
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            background: #ffffff;
            color: #334155;
            transition: all 0.18s ease;
            cursor: pointer;
        }
        .parameter-category-item:hover {
            border-color: #bfdbfe;
            background: #f8fbff;
            transform: translateX(2px);
        }
        .parameter-category-item-active {
            border-color: #93c5fd;
            background: linear-gradient(135deg, #eff6ff 0%, var(--ui-primary-soft) 100%);
            box-shadow: inset 3px 0 0 var(--ui-primary);
            color: #0f172a;
            transform: translateX(3px);
        }
        .parameter-category-count {
            min-width: 2rem;
            text-align: center;
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
            background: #f1f5f9;
            color: #475569;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .parameter-category-item-active .parameter-category-count {
            background: var(--ui-surface);
            color: #1d4ed8;
        }
        .parameter-category-icon {
            width: 2rem;
            height: 2rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 9999px;
            background: #eff6ff;
            color: var(--ui-primary);
            flex-shrink: 0;
        }
        .parameter-category-item-active .parameter-category-icon {
            background: #ffffff;
            color: #1d4ed8;
        }
        .parameter-search .q-field__control {
            border-radius: 16px;
            background: var(--ui-surface-muted);
        }
        .parameter-search .q-field--outlined .q-field__control:before {
            border-color: #cbd5e1;
        }
        .parameter-search .q-field--focused .q-field__control:before {
            border-color: #60a5fa !important;
        }
        .parameter-section-tabs {
            gap: 0.75rem;
            background: transparent !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        .parameter-section-tabs .q-tabs__content {
            gap: 0.75rem;
        }
        .parameter-section-tabs .q-tab {
            min-height: auto;
            border-radius: 9999px;
            border: 1px solid #dbe4f0;
            background: rgba(255, 255, 255, 0.92);
            color: #475569;
            padding: 0.2rem 0.4rem;
            transition: all 0.18s ease;
        }
        .parameter-section-tabs .q-tab:hover {
            border-color: #bfdbfe;
            background: #f8fbff;
            color: #0f172a;
        }
        .parameter-section-tabs .q-tab--active {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-color: #93c5fd;
            color: #1d4ed8;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.12);
        }
        .parameter-section-tabs .q-tab__label {
            font-size: 0.85rem;
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .parameter-section-tabs .q-tabs__arrow {
            color: #64748b;
        }
        .parameter-action-button {
            border-radius: 12px;
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .empty-state-icon {
            width: 4rem;
            height: 4rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 1.25rem;
            background: var(--ui-primary-soft);
            color: var(--ui-primary);
        }
        .empty-state-icon.warning {
            background: var(--ui-warning-soft);
            color: var(--ui-warning);
        }
        .empty-state-icon.success {
            background: var(--ui-success-soft);
            color: var(--ui-success);
        }
        .sticky-table .q-table thead tr th {
            position: sticky;
            top: 0;
            z-index: 1;
            background: var(--ui-surface-muted);
        }
        @media (max-width: 768px) {
            .parameter-shell {
                border-radius: 22px !important;
            }
            .parameter-panel {
                animation: none;
            }
            .parameter-section-tabs .q-tabs__content {
                gap: 0.5rem;
                flex-wrap: wrap;
            }
            .parameter-section-tabs .q-tab {
                padding: 0.15rem 0.35rem;
            }
            .parameter-category-item {
                padding: 0.8rem 0.9rem;
            }
        }
        </style>
        """
    )
    request = getattr(ui.context.client, "request", None)
    restored_query_state = parse_parameter_page_query(
        getattr(request, "query_params", None) if request is not None else None
    )
    base_origin = str(getattr(request, "base_url", "")).rstrip("/") if request is not None else ""

    all_parameters = list_parameter_definitions()
    parameter_groups = build_parameter_groups_for_ui()
    category_options = ["Tum Kategoriler", *[group["category"] for group in parameter_groups]]
    category_icons = {
        "Tum Kategoriler": "apps",
        "Materials": "inventory_2",
        "Constructions": "foundation",
        "Walls": "view_agenda",
        "Roofs": "roofing",
        "Floors": "dashboard",
        "Windows": "window",
        "Openings": "door_front",
        "Thermal Properties": "device_thermostat",
        "Cost Related": "payments",
        "Comfort Related": "weekend",
    }
    category_counts = {
        "Tum Kategoriler": len(all_parameters),
        **{group["category"]: int(group["parameter_count"]) for group in parameter_groups},
    }
    parameter_by_id = {parameter.id: parameter for parameter in all_parameters}
    selected_parameters: dict[str, dict[str, object]] = {}
    restored_category = str(restored_query_state["category"] or "").strip()
    initial_parameter_section = (
        resolve_parameter_section_for_category(restored_category) if restored_category else None
    )
    category_filter_state = {
        "value": restored_category if restored_category in category_options else "",
    }
    category_search_state = {"query": ""}
    highlighted_parameter_state = {"id": ""}
    structural_filter_state = {
        "dataset": restored_query_state["impact_dataset"]
    }
    share_link_state = {"last_url": ""}
    run_status_state = {
        "history": [{"status": "hazir", "label": RUNNER_STATUS_LABELS["hazir"], "detail": "Calistirma bekleniyor."}],
    }

    def sync_parameter_page_query() -> None:
        current_path = build_parameter_page_url(
            dataset_filter=str(structural_filter_state["dataset"]),
            category=str(category_filter_state["value"] or ""),
            search_query=str(parameter_search.value or ""),
            scenario_name=str(scenario_name_input.value or ""),
            scenario_description=str(scenario_description_input.value or ""),
            selected_parameter_ids=list(selected_parameters.keys()),
            selected_parameter_state=selected_parameters,
        )
        ui.run_javascript(
            "window.history.replaceState({}, '', '{}')".format(
                "{}",
                current_path,
            )
        )
        if "share_link_preview" in locals():
            share_link_state["last_url"] = current_path
            share_link_preview.set_text(shorten_text(current_path, 72))
            share_link_preview.tooltip(current_path)

    def get_current_parameter_page_path() -> str:
        return build_parameter_page_url(
            dataset_filter=str(structural_filter_state["dataset"]),
            category=str(category_filter_state["value"] or ""),
            search_query=str(parameter_search.value or ""),
            scenario_name=str(scenario_name_input.value or ""),
            scenario_description=str(scenario_description_input.value or ""),
            selected_parameter_ids=list(selected_parameters.keys()),
            selected_parameter_state=selected_parameters,
        )

    def get_current_parameter_page_absolute_url() -> str:
        return build_absolute_parameter_page_url(base_origin, get_current_parameter_page_path())

    def refresh_share_link_preview() -> None:
        current_path = get_current_parameter_page_path()
        current_absolute_url = get_current_parameter_page_absolute_url()
        share_link_state["last_url"] = current_absolute_url
        share_link_preview.set_text(shorten_text(current_path, 72))
        share_link_preview.tooltip(current_absolute_url)
        qr_service_url = build_share_qr_service_url(current_absolute_url, size=96)
        qr_dialog_url = build_share_qr_service_url(current_absolute_url, size=240)
        if qr_service_url:
            share_qr_preview.set_source(qr_service_url)
            share_qr_dialog_image.set_source(qr_dialog_url)
            share_qr_dialog_caption.set_text(current_absolute_url)

    def render_run_status_panel() -> None:
        scenario_run_status_container.clear()
        status_rows = build_runner_status_view_model(run_status_state["history"])
        latest_row = status_rows[-1] if status_rows else {"label": "Hazir", "detail": ""}
        scenario_run_status_info.set_text(
            f"Calistirma Durumu: {latest_row['label']}"
            + (f" | {latest_row['detail']}" if latest_row["detail"] else "")
        )
        tone_classes = {
            "positive": "bg-emerald-50 border border-emerald-200 text-emerald-800",
            "warning": "bg-amber-50 border border-amber-200 text-amber-800",
            "negative": "bg-rose-50 border border-rose-200 text-rose-800",
            "neutral": "bg-slate-50 border border-slate-200 text-slate-700",
        }
        badge_classes = {
            "positive": "bg-emerald-100 text-emerald-800",
            "warning": "bg-amber-100 text-amber-800",
            "negative": "bg-rose-100 text-rose-800",
            "neutral": "bg-slate-100 text-slate-700",
        }
        with scenario_run_status_container:
            ui.label("Calistirma Asamalari").classes("text-sm font-medium")
            for row in status_rows:
                tone = str(row["tone"])
                with ui.row().classes(
                    "w-full items-start justify-between gap-3 rounded-lg px-3 py-2 "
                    + tone_classes.get(tone, tone_classes["neutral"])
                ):
                    with ui.column().classes("gap-1"):
                        ui.label(str(row["label"])).classes("text-sm font-medium")
                        if str(row["detail"]).strip():
                            ui.label(str(row["detail"])).classes("text-xs opacity-80")
                    ui.label(str(row["badge"])).classes(
                        "rounded-full px-2 py-1 text-xs font-medium "
                        + badge_classes.get(tone, badge_classes["neutral"])
                    )

    def reset_run_status(detail: str = "Calistirma bekleniyor.") -> None:
        run_status_state["history"] = [
            {
                "status": "hazir",
                "label": RUNNER_STATUS_LABELS["hazir"],
                "detail": detail,
            }
        ]
        render_run_status_panel()

    def push_run_status(event: RunnerStatusEvent) -> None:
        run_status_state["history"].append(
            {
                "status": event.status,
                "label": event.label,
                "detail": event.detail,
            }
        )
        render_run_status_panel()

    async def copy_parameter_page_link() -> None:
        path = get_current_parameter_page_path()
        sync_parameter_page_query()
        try:
            copied_url = await ui.run_javascript(
                "(async () => {"
                f"const url = `${{window.location.origin}}{path}`;"
                "await navigator.clipboard.writeText(url);"
                "return url;"
                "})()"
            )
        except Exception:
            ui.notify("Link kopyalanamadi.", color="negative")
            return

        share_link_state["last_url"] = str(copied_url)
        share_link_preview.set_text(shorten_text(copied_url, 72))
        share_link_preview.tooltip(str(copied_url))
        ui.notify(f"Link kopyalandi: {copied_url}", color="positive")

    with ui.header().classes("items-center justify-between bg-slate-800 text-white"):
        ui.label("Parametre Secimi").classes("text-lg font-medium")
        with ui.row().classes("items-center gap-3"):
            ui.button("Ana Panel", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.button("Linki Kopyala", on_click=copy_parameter_page_link).props("flat color=white")
            with ui.dialog() as share_qr_dialog, ui.card().classes("items-center gap-3 p-4"):
                ui.label("QR Onizleme").classes("text-base font-medium")
                share_qr_dialog_image = ui.image("").classes("w-60 h-60 bg-white rounded p-2")
                share_qr_dialog_caption = ui.label("").classes("max-w-lg text-xs text-slate-600 break-all")
                ui.button("Kapat", on_click=share_qr_dialog.close).props("outline")
            share_qr_preview = ui.image("").classes("w-12 h-12 bg-white rounded p-1 cursor-pointer")
            share_qr_preview.on("click", lambda _: share_qr_dialog.open())
            share_link_preview = ui.label("Paylasilabilir oturum linki henuz olusturulmadi.").classes(
                "max-w-md text-xs text-slate-200"
            )
            ui.label("Koyu Tema").classes("text-sm")
            ui.switch(value=False, on_change=lambda e: dark_mode.set_value(bool(e.value)))

    with ui.column().classes("w-full max-w-[1480px] mx-auto px-6 py-8 gap-6"):
        with ui.card().classes("w-full parameter-shell parameter-panel rounded-[28px] border-0 px-6 py-5"):
            ui.label("Parametre Secimi").classes("text-[28px] font-semibold tracking-tight text-slate-900")
            ui.label(
                "Soldan bir kategori secin, sagda ilgili parametreleri goruntuleyin ve secimlerinizi yonetin."
            ).classes("text-sm text-slate-600")
        section_counts = build_parameter_section_counts(all_parameters)
        ui.label("Hizli Bolum Secimi").classes("text-sm font-medium uppercase tracking-[0.12em] text-slate-500")
        parameter_section_tabs = ui.tabs(value=initial_parameter_section).classes(
            "w-full parameter-section-tabs"
        )
        with parameter_section_tabs:
            for section_label in PARAMETER_SECTION_LABELS:
                ui.tab(
                    section_label,
                    label=f"{section_label} ({section_counts.get(section_label, 0)})",
                )

        with ui.grid().classes("w-full gap-6 items-start grid-cols-1 lg:grid-cols-12"):
            with ui.column().classes("w-full lg:col-span-5 gap-4"):
                with ui.row().classes("w-full gap-4 items-start"):
                    with ui.card().classes("w-full lg:w-[300px] parameter-panel rounded-[24px] border border-slate-200 bg-white/95 shadow-sm"):
                        ui.label("Kategori Listesi").classes("text-lg font-semibold text-slate-900")
                        ui.label("Degistirmek istediginiz alana gore kategori secin.").classes(
                            "text-sm text-slate-600"
                        )
                        category_search_input = ui.input(
                            label="Kategori Ara",
                            placeholder="Kategori adinda ara",
                        ).props("outlined clearable").classes("w-full parameter-search")
                        category_list_container = ui.column().classes("w-full pt-2 parameter-category-list")

                    with ui.column().classes("w-full gap-4"):
                        with ui.card().classes("w-full parameter-panel rounded-[24px] border border-slate-200 bg-white/95 shadow-sm"):
                            with ui.row().classes("w-full items-start justify-between gap-3"):
                                with ui.column().classes("gap-1"):
                                    parameter_panel_title = ui.label("Parametre Listesi").classes(
                                        "text-lg font-semibold text-slate-900"
                                    )
                                    parameter_panel_description = ui.label(
                                        "Secilen kategoriye ait parametreler burada listelenir."
                                    ).classes("text-sm text-slate-600")
                                parameter_context_badge = ui.label("Kategori Secilmedi").classes(
                                    "rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600"
                                )
                            ui.separator().classes("my-2")
                            parameter_search = ui.input(
                                label="Arama Kutusu",
                                placeholder="Ad, aciklama, alan adi veya veri seti icinde ara",
                                value=str(restored_query_state["search"]),
                            ).props("outlined clearable").classes("w-full parameter-search")
                            parameter_result_info = ui.label("").classes("text-sm text-slate-600")
                            parameter_list_container = ui.grid().classes(
                                "w-full gap-4 grid-cols-1 xl:grid-cols-2"
                            )

            with ui.column().classes("w-full lg:col-span-3 gap-4"):
                with ui.card().classes("w-full parameter-panel rounded-[24px] border border-slate-200 bg-white/95 shadow-sm"):
                    ui.label("Secilen Parametreler").classes("text-lg font-semibold text-slate-900")
                    selected_count_label = ui.label("0 parametre secildi").classes("text-sm font-medium text-slate-700")
                    ui.label(
                        "Mevcut degeri inceleyin, yeni deger girin ve gerekirse secimi kaldirin."
                    ).classes("text-sm text-slate-600")
                    selected_panel_actions = ui.row().classes("w-full justify-between items-center")
                    selected_inline_chart_container = ui.column().classes("w-full gap-3")
                    selected_parameters_container = ui.column().classes("w-full gap-3")

            with ui.column().classes("w-full lg:col-span-4 gap-4"):
                with ui.card().classes("w-full sticky top-4 parameter-panel rounded-[24px] border border-slate-200 bg-white/95 shadow-sm"):
                    ui.label("Canli Overlay Grafik").classes("text-base font-medium")
                    selected_overlay_chart_info = ui.label(
                        "Degisecek parametrelerin ilk ve yeni halleri burada ayni grafik uzerinde gosterilir."
                    ).classes("text-sm text-slate-600")
                    selected_overlay_chart_container = ui.column().classes("w-full gap-3")

        with ui.card().classes("w-full parameter-panel rounded-[24px] border border-slate-200 bg-white/95 shadow-sm"):
            scenario_builder_header = ui.label("Senaryo Hazirlik").classes("text-lg font-semibold text-slate-900")
            scenario_builder_info = ui.label(
                "Secili parametreler, kayit secimi ve yeni degerler ile senaryo JSON taslagi burada olusur."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full gap-4"):
                scenario_name_input = ui.input(
                    label="Senaryo Adi",
                    placeholder="Ornek: facade_upgrade_option_a",
                    value=str(restored_query_state["scenario_name"]),
                ).classes("w-full")
                scenario_description_input = ui.input(
                    label="Aciklama",
                    placeholder="Kisa senaryo notu",
                    value=str(restored_query_state["scenario_description"]),
                ).classes("w-full")
            base_model_path_input = ui.input(
                label="Baz Model Yolu (.osm)",
                placeholder=r"Ornek: C:\star\deneme.osm",
            ).classes("w-full")
            scenario_builder_actions = ui.row().classes("w-full gap-2")
            with ui.row().classes("w-full gap-4 items-stretch"):
                with ui.card().classes("w-full bg-slate-50"):
                    ui.label("Senaryo Adi").classes("text-sm text-slate-500")
                    scenario_summary_name = ui.label("-").classes("text-lg font-medium")
                with ui.card().classes("w-full bg-slate-50"):
                    ui.label("Degisiklik Sayisi").classes("text-sm text-slate-500")
                    scenario_summary_change_count = ui.label("0").classes("text-3xl font-bold")
                with ui.card().classes("w-full bg-slate-50"):
                    ui.label("Veri Seti").classes("text-sm text-slate-500")
                    scenario_summary_dataset = ui.label("-").classes("text-lg font-medium")
            scenario_draft_summary = ui.label("Taslak henuz hazir degil.").classes("text-sm text-slate-600")
            scenario_change_summary = ui.label("").classes("hidden")
            scenario_preview_info = ui.markdown("").classes("hidden w-full text-sm")
            scenario_draft_container = ui.column().classes("w-full gap-3")
            scenario_live_analysis_info = ui.label(
                "Parametre secimine gore anlik senaryo analizi burada gosterilir."
            ).classes("text-sm text-slate-600")
            scenario_live_analysis_container = ui.column().classes("w-full gap-3")
            scenario_run_prep_info = ui.label(
                "Gercek run icin baz model kopyasi ve varyant model ayri bir klasorde hazirlanir."
            ).classes("text-sm text-slate-600")
            scenario_run_status_info = ui.label(
                "Calistirma durumu asamalari burada izlenir."
            ).classes("text-sm text-slate-600")
            scenario_run_status_container = ui.column().classes("w-full gap-2")
            scenario_run_prep_container = ui.column().classes("w-full gap-3")
            structural_impact_info = ui.label(
                "Secilen kayitlara gore yapisal etki analizi burada gosterilir."
            ).classes("text-sm text-slate-600")
            structural_impact_container = ui.column().classes("w-full gap-3")

        def remove_parameter(parameter_id: str) -> None:
            selected_parameters.pop(parameter_id, None)
            sync_parameter_page_query()
            render_parameter_list()
            render_selected_parameters()
            render_scenario_builder()

        def clear_selected_parameters() -> None:
            selected_parameters.clear()
            sync_parameter_page_query()
            render_parameter_list()
            render_selected_parameters()
            render_scenario_builder()

        def add_parameter(parameter: ParameterDefinition) -> None:
            if parameter.id in selected_parameters:
                ui.notify(f"{parameter.label} zaten secili.", color="warning")
                render_selected_parameters()
                return

            selected_parameters[parameter.id] = {
                "definition": parameter,
                "current_value": get_parameter_current_value_preview(
                    parameter.dataset,
                    parameter.field_name,
                ),
                "new_value": "",
                "record_label": "",
                "record_choice": None,
            }
            highlighted_parameter_state["id"] = parameter.id
            ui.timer(
                1.2,
                lambda pid=parameter.id: clear_highlighted_parameter(pid),
                once=True,
            )
            ui.notify(
                f"{parameter.label} secildi. Siradaki adim: kayit secip yeni deger girin.",
                color="positive",
            )
            sync_parameter_page_query()
            render_parameter_list()
            render_selected_parameters()
            render_scenario_builder()

        def set_parameter_record(parameter_id: str, record_label: str) -> None:
            item = selected_parameters.get(parameter_id)
            if item is None:
                return

            parameter = item["definition"]
            record_choices = build_parameter_record_choices(parameter.dataset)
            choice = record_choices.get(record_label)

            item["record_label"] = record_label
            item["record_choice"] = choice
            if choice is None:
                item["current_value"] = get_parameter_current_value_preview(
                    parameter.dataset,
                    parameter.field_name,
                )
            else:
                row = choice.get("row", {})
                item["current_value"] = str(row.get(parameter.field_name, "")).strip() or "-"

            sync_parameter_page_query()
            render_selected_parameters()
            render_scenario_builder()

        def move_selected_parameter(parameter_id: str, direction: int) -> None:
            keys = list(selected_parameters.keys())
            if parameter_id not in selected_parameters or parameter_id not in keys:
                return
            current_index = keys.index(parameter_id)
            target_index = current_index + direction
            if target_index < 0 or target_index >= len(keys):
                return
            keys[current_index], keys[target_index] = keys[target_index], keys[current_index]
            reordered = {key: selected_parameters[key] for key in keys}
            selected_parameters.clear()
            selected_parameters.update(reordered)
            sync_parameter_page_query()
            render_selected_parameters()
            render_scenario_builder()

        def clear_highlighted_parameter(parameter_id: str) -> None:
            if highlighted_parameter_state["id"] != parameter_id:
                return
            highlighted_parameter_state["id"] = ""
            render_parameter_list()

        def is_selected_parameter_ready(item: dict[str, object]) -> bool:
            record_label = str(item.get("record_label", "")).strip()
            new_value = str(item.get("new_value", "")).strip()
            return bool(record_label and new_value)

        def build_selected_progress_steps() -> list[tuple[str, bool]]:
            selected_total = len(selected_parameters)
            any_record_selected = any(
                str(item.get("record_label", "")).strip() for item in selected_parameters.values()
            )
            any_new_value = any(
                str(item.get("new_value", "")).strip() for item in selected_parameters.values()
            )
            all_ready = bool(selected_parameters) and all(
                is_selected_parameter_ready(item) for item in selected_parameters.values()
            )
            return [
                ("1. Parametre Sec", selected_total > 0),
                ("2. Kayit Sec", any_record_selected),
                ("3. Yeni Deger Gir", any_new_value),
                ("4. Senaryo Olustur", all_ready),
            ]

        def build_parameter_draft_row(parameter_id: str, item: dict[str, object]) -> dict[str, object]:
            parameter = item["definition"]
            return {
                "parameter_id": parameter_id,
                "label": parameter.label,
                "dataset": parameter.dataset,
                "field_name": parameter.field_name,
                "current_value": str(item["current_value"]),
                "new_value": str(item["new_value"]).strip(),
                "unit": parameter.unit or "-",
                "value_type": parameter.value_type,
                "category": parameter.category,
                "record_label": str(item.get("record_label", "")).strip(),
                "record_choice": item.get("record_choice"),
            }

        def collect_selected_changes() -> list[SelectedParameterChange]:
            collected = []
            for item in selected_parameters.values():
                parameter = item["definition"]
                collected.append(
                    SelectedParameterChange(
                        parameter=parameter,
                        current_value=str(item["current_value"]),
                        new_value=str(item["new_value"]).strip(),
                        record_label=str(item.get("record_label", "")).strip(),
                        record_choice=item.get("record_choice"),
                    )
                )
            return collected

        def build_scenario_draft() -> tuple[list[dict[str, object]], list[str], dict[str, object] | None]:
            selected_changes = collect_selected_changes()
            scenario_name = sanitize_scenario_name(
                (scenario_name_input.value or "").strip() or "parameter_selection_draft"
            )
            scenario_description = (scenario_description_input.value or "").strip()
            input_validation_errors: list[str] = []
            for change in selected_changes:
                warnings = validate_parameter_new_value(
                    parameter=change.parameter,
                    current_value=change.current_value,
                    new_value=change.new_value,
                )
                for warning in warnings:
                    input_validation_errors.append(f"{change.parameter.label}: {warning}")

            draft, change_list, errors = build_scenario_from_selected_changes(
                selected_changes,
                scenario_name=scenario_name,
                description=scenario_description,
            )
            errors = [*input_validation_errors, *errors]

            draft_rows = [
                build_parameter_draft_row(parameter.id, item)
                for parameter, item in (
                    (change.parameter, selected_parameters[change.parameter.id])
                    for change in selected_changes
                )
            ]
            if draft is not None:
                draft["changes"] = change_list
            return draft_rows, errors, draft

        def build_structural_impact_preview(
            draft_rows: list[dict[str, object]],
        ) -> tuple[dict[str, object], list[str]]:
            csv_root = Path("csv_output")
            if not csv_root.exists():
                return {
                    "direct_rows": [],
                    "indirect_rows": [],
                    "layer_rows": [],
                    "summary": "csv_output klasoru bulunamadi.",
                }, ["Etki analizi icin csv_output klasoru bulunamadi."]

            repo = CsvRepository(csv_root)
            direct_rows: list[dict[str, object]] = []
            indirect_rows: list[dict[str, object]] = []
            layer_rows: list[dict[str, object]] = []
            layer_impact_rows: list[dict[str, object]] = []
            surface_impact_rows: list[dict[str, object]] = []
            errors: list[str] = []

            for row in draft_rows:
                record_choice = row.get("record_choice")
                if not isinstance(record_choice, dict):
                    continue

                selected_row = record_choice.get("row")
                if not isinstance(selected_row, dict):
                    continue

                dataset_name = str(row.get("dataset", "")).strip()
                field_name = str(row.get("field_name", "")).strip()
                trigger_label = str(row.get("label", "")).strip() or dataset_name
                record_label = str(row.get("record_label", "")).strip()

                try:
                    model = build_dependency_service_model_for_row(
                        repo=repo,
                        dataset_name=dataset_name,
                        row=selected_row,
                        changed_column=field_name,
                    )
                except DependencyAnalysisError as error:
                    errors.append(f"{trigger_label}: {error}")
                    continue

                for item in model["direct_affected_tables"]:
                    direct_rows.append(
                        {
                            "id": f"{trigger_label}-direct-{item['dataset']}",
                            "trigger": trigger_label,
                            "record_label": record_label,
                            "dataset": item["dataset"],
                            "affected_row_count": item["affected_row_count"],
                            "reasons": " | ".join(item["reasons"]) or "-",
                        }
                    )

                for index, item in enumerate(model["indirect_affected_items"], start=1):
                    indirect_rows.append(
                        {
                            "id": f"{trigger_label}-indirect-{index}",
                            "trigger": trigger_label,
                            "record_label": record_label,
                            "dataset": item["dataset"],
                            "row_key": item["row_key"] or "-",
                            "via": item["via"] or "-",
                            "reason": item["reason"] or "-",
                        }
                    )

                for index, item in enumerate(model["layer_relationships"], start=1):
                    layer_rows.append(
                        {
                            "id": f"{trigger_label}-layer-{index}",
                            "trigger": trigger_label,
                            "source_row_key": item["source_row_key"] or "-",
                            "target_dataset": item["target_dataset"] or "-",
                            "target_row_key": item["target_row_key"] or "-",
                            "relationship_type": item["relationship_type"] or "-",
                            "reason": item["reason"] or "-",
                        }
                    )

                for index, item in enumerate(model.get("affected_layers", []), start=1):
                    layer_impact_rows.append(
                        {
                            "id": f"{trigger_label}-layer-impact-{index}",
                            "badge": item.get("badge", "Etkilenen Layer"),
                            "layer_name": item.get("layer_name", "-"),
                            "material_name": item.get("material_name", "-"),
                            "changed_field": field_name or "-",
                            "old_value": str(row.get("current_value", "-") or "-"),
                            "new_value": str(row.get("new_value", "-") or "-"),
                            "construction_names": ", ".join(item.get("construction_names", [])) or "-",
                            "trigger": trigger_label,
                        }
                    )

                for index, item in enumerate(model.get("affected_surfaces", []), start=1):
                    surface_impact_rows.append(
                        {
                            "id": f"{trigger_label}-surface-impact-{index}",
                            "surface_kind": item.get("surface_kind", "-"),
                            "surface_name": item.get("surface_name", "-"),
                            "construction_name": item.get("construction_name", "-"),
                            "reason": item.get("reason", "-"),
                            "changed_field": item.get("changed_field", field_name or "-"),
                            "dataset": item.get("dataset", "-"),
                            "trigger": trigger_label,
                        }
                    )

            summary = (
                f"Dogrudan tablo: {len(direct_rows)} | "
                f"Dolayli oge: {len(indirect_rows)} | "
                f"Katman iliskisi: {len(layer_rows)} | "
                f"Katman etkisi: {len(layer_impact_rows)} | "
                f"Yuzey etkisi: {len(surface_impact_rows)}"
            )
            return {
                "direct_rows": direct_rows,
                "indirect_rows": indirect_rows,
                "layer_rows": layer_rows,
                "layer_impact_rows": layer_impact_rows,
                "surface_impact_rows": surface_impact_rows,
                "summary": summary,
            }, errors

        def build_generated_scenario_path(scenario_name: str) -> Path:
            normalized_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", scenario_name.strip())
            normalized_name = normalized_name.strip("_") or "parameter_selection_draft"
            return SCENARIO_DIR / "generated" / f"{normalized_name}.json"

        def save_scenario_draft_file(draft: dict[str, object]) -> Path:
            scenario_path = build_generated_scenario_path(str(draft["scenario_name"]))
            scenario_path.parent.mkdir(parents=True, exist_ok=True)
            return write_scenario_definition_file(scenario_path, draft)

        def save_current_scenario_draft() -> None:
            _, errors, draft = build_scenario_draft()
            if errors or draft is None:
                ui.notify("Taslak kaydedilemedi. Once tum alanlari tamamlayin.", color="negative")
                render_scenario_builder()
                return

            scenario_path = save_scenario_draft_file(draft)
            ui.notify(f"Senaryo taslagi kaydedildi: {scenario_path.as_posix()}", color="positive")
            ui.navigate.to(f"/?scenario={quote(scenario_path.as_posix(), safe='')}&focus=scenario")
            render_scenario_builder()

        def run_current_scenario_draft() -> None:
            _, errors, draft = build_scenario_draft()
            if errors or draft is None:
                ui.notify("Senaryo calistirilamadi. Once tum alanlari tamamlayin.", color="negative")
                render_scenario_builder()
                return

            scenario_path = save_scenario_draft_file(draft)
            try:
                compatible_payload = build_apply_scenario_definition_payload(draft)
                output_path, log_output_path, change_count = run_scenario_definition(compatible_payload)
            except CsvUpdateError as error:
                ui.notify(str(error), color="negative")
                render_scenario_builder()
                return

            ui.notify(
                f"Senaryo calisti: {change_count} alan degisti. Cikti: {output_path.as_posix()}",
                color="positive",
            )
            scenario_draft_summary.set_text(
                f"Senaryo calisti. {change_count} alan guncellendi ve cikti dosyalari olustu."
            )
            scenario_preview_info.set_content(
                build_run_artifacts_markdown(
                    title="Olusan Dosyalar",
                    lead="Tek senaryo CSV guncellemesi tamamlandi.",
                    artifacts=[
                        ("Taslak", scenario_path.as_posix()),
                        ("Cikti CSV", output_path.as_posix()),
                        ("Degisim Logu", log_output_path.as_posix()),
                    ],
                )
            )
            scenario_preview_info.classes(remove="hidden")
            ui.navigate.to(f"/?scenario={quote(scenario_path.as_posix(), safe='')}&focus=impact")
            render_scenario_builder()

        def prepare_current_scenario_run() -> None:
            scenario_run_prep_container.clear()
            reset_run_status("Scenario run hazirligi bekleniyor.")
            _, errors, draft = build_scenario_draft()
            base_model_path = str(base_model_path_input.value or "").strip()

            if errors or draft is None:
                push_run_status(
                    RunnerStatusEvent(
                        status="hata",
                        label=RUNNER_STATUS_LABELS["hata"],
                        detail="Run klasoru icin gerekli alanlar eksik.",
                    )
                )
                ui.notify("Run klasoru hazirlanamadi. Once tum alanlari tamamlayin.", color="negative")
                render_scenario_builder()
                return
            if not base_model_path:
                push_run_status(
                    RunnerStatusEvent(
                        status="dogrulaniyor",
                        label=RUNNER_STATUS_LABELS["dogrulaniyor"],
                        detail="Baz model yolu bekleniyor.",
                    )
                )
                ui.notify("Baz model yolu girilmeli.", color="warning")
                with scenario_run_prep_container:
                    ui.label("Run hazirligi icin once baz .osm model yolunu girin.").classes(
                        "text-sm text-amber-700"
                    )
                return

            try:
                push_run_status(
                    RunnerStatusEvent(
                        status="dogrulaniyor",
                        label=RUNNER_STATUS_LABELS["dogrulaniyor"],
                        detail="Baz model ve senaryo girdisi kontrol ediliyor.",
                    )
                )
                push_run_status(
                    RunnerStatusEvent(
                        status="senaryo_hazirlaniyor",
                        label=RUNNER_STATUS_LABELS["senaryo_hazirlaniyor"],
                        detail="Scenario run klasoru olusturuluyor.",
                    )
                )
                preparation = prepare_scenario_model_variant(
                    scenario=draft,
                    base_model_path=base_model_path,
                )
                push_run_status(
                    RunnerStatusEvent(
                        status="model_guncelleniyor",
                        label=RUNNER_STATUS_LABELS["model_guncelleniyor"],
                        detail=(
                            "OpenStudio ile varyant model kaydedildi."
                            if preparation.openstudio_available
                            else "Model workspace kopya modunda hazirlandi."
                        ),
                    )
                )
                push_run_status(
                    RunnerStatusEvent(
                        status="tamamlandi",
                        label=RUNNER_STATUS_LABELS["tamamlandi"],
                        detail="Scenario run hazirligi tamamlandi.",
                    )
                )
            except (ScenarioModelPreparationError, ScenarioRunWorkspaceError, OSError) as error:
                push_run_status(
                    RunnerStatusEvent(
                        status="hata",
                        label=RUNNER_STATUS_LABELS["hata"],
                        detail=str(error),
                    )
                )
                ui.notify(str(error), color="negative")
                with scenario_run_prep_container:
                    ui.label(str(error)).classes("text-sm text-red-600")
                return

            ui.notify(
                f"Scenario run klasoru hazirlandi: {preparation.workspace.run_dir.as_posix()}",
                color="positive",
            )
            with scenario_run_prep_container:
                ui.markdown(
                    build_run_artifacts_markdown(
                        title="Scenario Run Hazirligi",
                        lead="Run klasoru, baz model kopyasi ve varyant model uretildi.",
                        artifacts=[
                            ("Run klasoru", preparation.workspace.run_dir.as_posix()),
                            ("Baz model kopyasi", preparation.workspace.base_model_copy.as_posix()),
                            ("Varyant model", preparation.workspace.scenario_model_path.as_posix()),
                            ("Senaryo snapshot", preparation.scenario_snapshot_path.as_posix()),
                            (
                                "CSV kopyasi",
                                preparation.input_csv_copy_path.as_posix()
                                if preparation.input_csv_copy_path is not None
                                else None,
                            ),
                        ],
                    )
                ).classes("w-full text-sm")
                ui.label(
                    "OpenStudio varyant hazirligi: "
                    + ("hazir" if preparation.openstudio_available else "kopya modunda")
                ).classes(
                    "text-sm " + ("text-emerald-700" if preparation.openstudio_available else "text-amber-700")
                )

        def run_current_comparative_simulation() -> None:
            scenario_run_prep_container.clear()
            reset_run_status("Comparative simulation baslatilmadi.")
            _, errors, draft = build_scenario_draft()
            base_model_path = str(base_model_path_input.value or "").strip()

            if errors or draft is None:
                push_run_status(
                    RunnerStatusEvent(
                        status="hata",
                        label=RUNNER_STATUS_LABELS["hata"],
                        detail="Calistirma icin gerekli parametreler eksik.",
                    )
                )
                ui.notify(
                    "Karsilastirmali simulasyon baslatilamadi. Once tum alanlari tamamlayin.",
                    color="negative",
                )
                render_scenario_builder()
                return
            if not base_model_path:
                push_run_status(
                    RunnerStatusEvent(
                        status="dogrulaniyor",
                        label=RUNNER_STATUS_LABELS["dogrulaniyor"],
                        detail="Baz model yolu bekleniyor.",
                    )
                )
                ui.notify("Baz model yolu girilmeli.", color="warning")
                with scenario_run_prep_container:
                    ui.label("Baseline ve senaryo run icin once baz .osm model yolunu girin.").classes(
                        "text-sm text-amber-700"
                    )
                return

            try:
                result = run_comparative_simulation(
                    scenario=draft,
                    base_model_path=base_model_path,
                    status_callback=push_run_status,
                    source="ui",
                )
            except (
                SimulationRunnerError,
                ScenarioModelPreparationError,
                ScenarioRunWorkspaceError,
                CsvUpdateError,
                OSError,
            ) as error:
                if not run_status_state["history"] or run_status_state["history"][-1]["status"] != "hata":
                    push_run_status(
                        RunnerStatusEvent(
                            status="hata",
                            label=RUNNER_STATUS_LABELS["hata"],
                            detail=str(error),
                        )
                    )
                ui.notify(str(error), color="negative")
                with scenario_run_prep_container:
                    ui.label(str(error)).classes("text-sm text-red-600")
                return

            ui.notify(
                f"Karsilastirmali simulasyon tamamlandi: {result.run_dir.as_posix()}",
                color="positive",
            )
            with scenario_run_prep_container:
                ui.markdown(
                    build_run_artifacts_markdown(
                        title="Comparative Simulation Runner",
                        lead="Baseline ve senaryo ciktilari ayri klasorlerde uretildi; karsilastirma raporu hazir.",
                        artifacts=[
                            ("Run klasoru", result.run_dir.as_posix()),
                            ("Baseline cikti", result.baseline_output.as_posix()),
                            ("Baseline log", result.baseline_log.as_posix()),
                            ("Senaryo cikti", result.scenario_output.as_posix()),
                            ("Senaryo log", result.scenario_log.as_posix()),
                            ("Karsilastirma raporu", result.comparison_report.as_posix()),
                        ],
                    )
                ).classes("w-full text-sm")
                if result.preparation is not None:
                    ui.label(
                        "Model hazirligi: "
                        + (
                            "OpenStudio ile varyant kaydedildi"
                            if result.preparation.openstudio_available
                            else "kopya modunda varyant workspace hazirlandi"
                        )
                    ).classes(
                        "text-sm "
                        + (
                            "text-emerald-700"
                            if result.preparation.openstudio_available
                            else "text-amber-700"
                        )
                    )

        def render_scenario_builder() -> None:
            scenario_draft_container.clear()
            scenario_live_analysis_container.clear()
            scenario_run_prep_container.clear()
            structural_impact_container.clear()
            scenario_builder_actions.clear()
            draft_rows, errors, draft = build_scenario_draft()

            if not selected_parameters:
                scenario_builder_header.set_text("Bolum 2-3-4: Yeni Deger Girisi, Senaryo Ozeti ve Yapisal Etki")
                scenario_builder_info.set_text(
                    "Secili parametreler, kayit secimi ve yeni degerler ile senaryo ozeti burada olusur."
                )
                scenario_summary_name.set_text("-")
                scenario_summary_change_count.set_text("0")
                scenario_summary_dataset.set_text("-")
                scenario_draft_summary.set_text("Taslak henuz hazir degil.")
                scenario_change_summary.set_text("")
                scenario_preview_info.set_content("")
                scenario_live_analysis_info.set_text(
                    "Parametre secimine gore anlik senaryo analizi burada gosterilir."
                )
                scenario_run_prep_info.set_text(
                    "Gercek run icin baz model korunur; baseline ve senaryo ciktilari ayri klasorlerde uretilir."
                )
                reset_run_status("Calistirma icin parametre secimi bekleniyor.")
                structural_impact_info.set_text(
                    "Secilen kayitlara gore yapisal etki analizi burada gosterilir."
                )
                with scenario_draft_container:
                    with ui.card().classes(
                        "rounded-[20px] border border-dashed border-slate-300 bg-slate-50/70 shadow-none"
                    ):
                        with ui.column().classes("items-center gap-2 py-8 text-center"):
                            with ui.element("span").classes("empty-state-icon"):
                                ui.icon("edit_note").classes("text-3xl")
                            ui.label("Hazirlik adimi icin once parametre secin").classes(
                                "text-base font-semibold text-slate-900"
                            )
                            ui.label(
                                "Secilen parametreler ve yeni degerler bu alanda senaryo taslagina donusecek."
                            ).classes("max-w-md text-sm text-slate-600")
                with scenario_run_prep_container:
                    with ui.card().classes(
                        "rounded-[18px] border border-slate-200 bg-slate-50/80 shadow-none"
                    ):
                        ui.label("Run hazirligi icin once parametre secin.").classes("text-sm text-slate-500")
                with scenario_live_analysis_container:
                    with ui.card().classes(
                        "rounded-[18px] border border-slate-200 bg-slate-50/80 shadow-none"
                    ):
                        ui.label("Anlik analiz icin once parametre secin.").classes("text-sm text-slate-500")
                with structural_impact_container:
                    with ui.card().classes(
                        "rounded-[18px] border border-slate-200 bg-slate-50/80 shadow-none"
                    ):
                        ui.label("Etki analizi icin once parametre secin.").classes("text-sm text-slate-500")
                return

            scenario_builder_header.set_text("Bolum 2-3-4: Yeni Deger Girisi, Senaryo Ozeti ve Yapisal Etki")
            scenario_builder_info.set_text(
                "Bu adim yeni degerleri kontrol eder ve secilen kayda gore calistirilabilir bir senaryo uretir."
            )
            scenario_preview_info.set_content("")
            scenario_run_prep_info.set_text(
                "Baz model degismeden kalir; scenario_runs altinda baseline ve senaryo ciktilari ayri klasorlerde uretilir."
            )
            render_run_status_panel()
            structural_impact_model, structural_errors = build_structural_impact_preview(draft_rows)
            structural_impact_view = build_structural_impact_view_model(structural_impact_model)
            dataset_filter_options = sorted(
                {
                    str(row.get("dataset", "")).strip()
                    for row in structural_impact_model["direct_rows"] + structural_impact_model["indirect_rows"]
                    if str(row.get("dataset", "")).strip()
                }
                | {
                    str(row.get("target_dataset", "")).strip()
                    for row in structural_impact_model["layer_rows"]
                    if str(row.get("target_dataset", "")).strip()
                }
            )
            allowed_dataset_filters = {"Tum Veri Setleri", *dataset_filter_options}
            if structural_filter_state["dataset"] not in allowed_dataset_filters:
                structural_filter_state["dataset"] = "Tum Veri Setleri"
            filtered_structural_rows = filter_structural_impact_rows(
                structural_impact_model,
                structural_filter_state["dataset"],
            )
            structural_card_summary = summarize_structural_impact_cards(
                structural_impact_model,
                filtered_structural_rows,
            )
            combined_impact_summary = build_combined_impact_summary(structural_impact_model)
            live_change_chart = build_parameter_change_chart_model(selected_parameters)
            live_waterfall_model = build_parameter_waterfall_chart_model(live_change_chart)
            can_run_scenario = bool(selected_parameters) and all(
                is_selected_parameter_ready(item) for item in selected_parameters.values()
            )
            structural_impact_info.set_text(
                "Secilen kayitlarin dogrudan etkiledigi tablolar, dolayli ogeler ve katman iliskileri asagida listelenir."
            )
            scenario_live_analysis_info.set_text(
                "Bu alan secili parametrelerin mevcut ve yeni degerlerine gore anlik senaryo yorumunu gosterir."
            )

            with scenario_builder_actions:
                ui.button(
                    "Taslagi Kaydet",
                    on_click=save_current_scenario_draft,
                ).props("outline size=sm").classes("parameter-action-button")
                ui.button(
                    "Senaryoyu Calistir",
                    on_click=run_current_scenario_draft,
                ).props(
                    (
                        "color=primary unelevated size=sm"
                        if can_run_scenario
                        else "disable color=primary unelevated size=sm"
                    )
                ).classes("parameter-action-button")
                ui.button(
                    "Sadece Hazirlik Yap",
                    on_click=prepare_current_scenario_run,
                ).props("outline color=secondary size=sm").classes("parameter-action-button")
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Gercek Karsilastirmali Calistirma",
                        on_click=run_current_comparative_simulation,
                    ).props("color=accent icon=play_circle unelevated size=sm").classes("parameter-action-button")
                    ui.label("ONERILEN").classes(
                        "text-[10px] font-bold tracking-wide px-2 py-1 rounded bg-emerald-100 text-emerald-800"
                    )
                ui.label(
                    "Sadece Hazirlik Yap: run klasoru, model kopyasi ve snapshot olusturur; comparison grafikleri doldurmaz."
                ).classes("text-xs text-slate-500")
                ui.label(
                    "Gercek Karsilastirmali Calistirma: baseline ve senaryo ciktilarini uretir, comparison raporu olusturur ve grafikleri doldurur."
                ).classes("text-xs text-emerald-700")
                if not can_run_scenario:
                    ui.label(
                        "Senaryoyu Calistir butonu icin her parametrede kayit secimi ve yeni deger girisi tamamlanmali."
                    ).classes("text-xs text-amber-700")

            scenario_summary_name.set_text(str(draft["scenario_name"]) if draft else "-")
            scenario_summary_change_count.set_text(str(len(draft_rows)))
            scenario_summary_dataset.set_text(str(draft["input"]).replace("csv_output/", "") if draft else "-")

            with scenario_draft_container:
                with ui.card().classes(
                    "w-full rounded-[18px] border border-sky-200 bg-sky-50/80 shadow-none"
                ):
                    with ui.column().classes("gap-2"):
                        ui.label("Hazirlik Akisi").classes("text-sm font-semibold text-sky-900")
                        ui.label(
                            "Taslak ozetini kontrol edin, eksik alan varsa duzeltin, sonra hazirlik ya da calistirma aksiyonlarindan birini secin."
                        ).classes("text-sm text-sky-800")

                ui.label("Bolum 3 - Senaryo Ozeti").classes("text-sm font-medium")

                ui.label(
                    "Hazir Durumu: HAZIR" if not errors else "Hazir Durumu: EKSIK / DUZELTME GEREKLI"
                ).classes("text-sm font-medium " + ("text-emerald-700" if not errors else "text-rose-700"))

                ui.label("Secilen Parametreler Ozeti").classes("text-sm font-medium")
                ui.table(
                    columns=[
                        {"name": "label", "label": "Parametre", "field": "label"},
                        {"name": "dataset", "label": "Veri Seti", "field": "dataset"},
                        {"name": "record_label", "label": "Kayit", "field": "record_label"},
                        {"name": "field_name", "label": "Alan", "field": "field_name"},
                        {"name": "current_value", "label": "Mevcut", "field": "current_value"},
                        {"name": "new_value", "label": "Yeni", "field": "new_value"},
                        {"name": "unit", "label": "Birim", "field": "unit"},
                    ],
                    rows=draft_rows,
                    row_key="parameter_id",
                    pagination={"rowsPerPage": 10},
                ).classes("w-full sticky-table")

                if errors:
                    scenario_draft_summary.set_text(f"Taslak hazir degil. {len(errors)} sorun bulundu.")
                    scenario_change_summary.set_text("")
                    with ui.card().classes(
                        "w-full rounded-[18px] border border-rose-200 bg-rose-50 shadow-none"
                    ):
                        with ui.column().classes("gap-1"):
                            ui.label("Duzeltilmesi Gerekenler").classes("text-sm font-semibold text-rose-800")
                            ui.label(
                                "Calistirma oncesi asagidaki sorunlari giderin. En sik eksikler: kayit secilmemesi veya yeni deger girilmemesi."
                            ).classes("text-sm text-rose-700")
                    for error in errors:
                        ui.label(error).classes("text-sm text-red-600")
                else:
                    scenario_draft_summary.set_text(
                        f"Taslak hazir. {len(draft_rows)} parametre icin {len(draft['operations'])} islem uretildi."
                    )
                    scenario_change_summary.set_text("")
                    changed_fields = sorted(
                        {
                            str(change.get("field_name", "")).strip()
                            for change in draft.get("changes", [])
                            if str(change.get("field_name", "")).strip()
                        }
                    )
                    affected_records = sorted(
                        {
                            str(change.get("record_label", "")).strip()
                            for change in draft.get("changes", [])
                            if str(change.get("record_label", "")).strip()
                        }
                    )
                    with ui.card().classes("w-full bg-emerald-50 border border-emerald-100"):
                        ui.label("Taslak Ozeti").classes("text-sm font-medium text-emerald-800")
                        ui.label(
                            f"Islem sayisi: {len(draft.get('operations', []))} | Etkilenen kayit: {len(affected_records)}"
                        ).classes("text-sm text-emerald-700")
                        ui.label(
                            "Degisen alanlar: " + (", ".join(changed_fields) if changed_fields else "-")
                        ).classes("text-xs text-emerald-700")

            impact_map_model = build_parameter_impact_map_model(selected_parameters)
            with scenario_draft_container:
                ui.label("Beklenen Etki").classes("text-sm font-medium")
                ui.label(
                    "Bu tablo secili parametrelerin beklenen goreli etkisini renkli olarak ozetler; gercek simulasyon sonucu degildir."
                ).classes("text-sm text-slate-600")
                if impact_map_model["has_data"]:
                    impact_summary_cards = build_parameter_impact_summary_cards(impact_map_model)
                    with ui.row().classes("w-full gap-3 items-stretch"):
                        for card in impact_summary_cards:
                            with ui.card().classes("w-full gap-1 " + str(card["classes"])):
                                ui.label(str(card["title"])).classes("text-xs uppercase tracking-wide opacity-80")
                                ui.label(
                                    f"{card['emoji']} {card['parameter_label']}"
                                ).classes("text-sm font-medium")
                                ui.label(
                                    f"Etki seviyesi: {str(card['level_text']).capitalize()}"
                                ).classes("text-xs")
                    with ui.column().classes("w-full gap-2"):
                        with ui.row().classes("w-full gap-2 items-stretch"):
                            ui.label("Parametre").classes(
                                "min-w-48 text-xs font-medium uppercase tracking-wide text-slate-500"
                            )
                            for column_name in impact_map_model["columns"]:
                                ui.label(format_impact_dimension_label(str(column_name))).classes(
                                    "w-36 text-center text-xs font-medium uppercase tracking-wide text-slate-500"
                                )
                        for row in impact_map_model["rows"]:
                            with ui.row().classes("w-full gap-2 items-stretch"):
                                with ui.card().classes("min-w-48 grow bg-slate-50"):
                                    ui.label(str(row["parameter_label"])).classes("text-sm font-medium")
                                    matched_impacts = list(row.get("matched_impacts", []))
                                    if matched_impacts:
                                        ui.label(
                                            "Beklenen etkiler: " + ", ".join(matched_impacts[:4])
                                        ).classes("text-xs text-slate-500")
                                for column_name in impact_map_model["columns"]:
                                    cell = dict(row[str(column_name)])
                                    with ui.card().classes(
                                        "w-36 items-center justify-center gap-1 px-2 py-3 text-center "
                                        + str(cell["classes"])
                                    ):
                                        ui.label(str(cell["emoji"])).classes("text-lg")
                                        ui.label(str(cell["text"]).capitalize()).classes(
                                            "text-xs font-medium"
                                        )
                    ui.label("Toplu Etki Cizgisi").classes("text-sm font-medium")
                    ui.label(
                        "Mevcut durum referans cizgisi sifirdir. Yeni cizgiler secilen parametrelerin beklenen etkisini, birden fazla secimde ise birlesik senaryo toplam etkisini gosterir."
                    ).classes("text-xs text-slate-600")
                    ui.echart(
                        build_multi_parameter_impact_chart_options(impact_map_model)
                    ).classes("w-full h-80")
                else:
                    ui.label("Etki haritasi icin once parametre secin.").classes("text-sm text-slate-500")

            with scenario_live_analysis_container:
                ui.label("Anlik Senaryo Analizi").classes("text-sm font-medium")
                ui.label(
                    "Bu analiz secili 1, 2 veya daha fazla parametredeki base ve updated degerleri ayni grafikte birlikte gosterir."
                ).classes("text-sm text-slate-600")

                if live_change_chart["has_data"]:
                    live_overlay_model = build_overlay_chart_model(
                        chart_name="Anlik Parametre Overlay",
                        x_labels=live_change_chart["labels"],
                        series=[
                            {
                                "name": "Base",
                                "data": live_change_chart["before_values"],
                                "origin": "base",
                                "line_type": "line",
                                "line_style": "solid",
                                "color": "#1f2937",
                            },
                            {
                                "name": "Updated",
                                "data": live_change_chart["after_values"],
                                "origin": "scenario",
                                "line_type": "line",
                                "line_style": "dashed",
                                "color": "#0f766e",
                            },
                        ],
                    )
                    live_overlay_series = overlay_chart_model_to_echart_series(live_overlay_model)
                    comparable_indexes = [
                        index
                        for index, value in enumerate(live_change_chart["delta_values"])
                        if value is not None
                    ]
                    y_axis_name = (
                        "Normalize Edilmis Deger"
                        if live_change_chart["is_normalized"]
                        else "Deger"
                    )

                    ui.echart(
                        {
                            "tooltip": {
                                "trigger": "axis",
                                "formatter": build_parameter_overlay_tooltip_formatter(
                                    live_change_chart
                                ),
                            },
                            "legend": {
                                "data": [series.get("name", "Series") for series in live_overlay_series],
                                "top": 8,
                            },
                            "grid": {
                                "left": "3%",
                                "right": "4%",
                                "bottom": "12%",
                                "containLabel": True,
                            },
                            "xAxis": {
                                "type": "category",
                                "data": live_overlay_model.x_labels,
                                "axisLabel": {"interval": 0, "rotate": 25},
                            },
                            "yAxis": {"type": "value", "name": y_axis_name},
                            "series": live_overlay_series,
                        }
                    ).classes("w-full h-72")

                    if live_waterfall_model["has_data"]:
                        unit_label = str(live_waterfall_model.get("unit", "") or "")
                        unit_suffix = f" {unit_label}" if unit_label else ""
                        waterfall_tooltip = (
                            "function (params) {"
                            "if (!params || params.length === 0) return '';"
                            "const idx = params[0].dataIndex;"
                            f"const running = {json.dumps(live_waterfall_model['running_values'])};"
                            "let lines = [];"
                            "params.forEach(function (entry) {"
                            "if (!entry || entry.seriesName === 'Offset') return;"
                            "const value = Number(entry.value || 0);"
                            "if (value === 0 && entry.seriesName !== 'Net Total') return;"
                            "lines.push(entry.marker + ' ' + entry.seriesName + ': ' + value.toFixed(2)"
                            f" + '{unit_suffix}');"
                            "});"
                            "if (idx < running.length) {"
                            "lines.push('Kumulatif: ' + Number(running[idx] || 0).toFixed(2)"
                            f" + '{unit_suffix}');"
                            "}"
                            "return params[0].axisValue + '<br/>' + lines.join('<br/>');"
                            "}"
                        )

                        ui.label("Parametre Etki Waterfall").classes("text-sm font-medium")
                        ui.label(str(live_waterfall_model["summary"])).classes("text-xs text-slate-600")
                        ui.echart(
                            {
                                "tooltip": {
                                    "trigger": "axis",
                                    "axisPointer": {"type": "shadow"},
                                    "formatter": waterfall_tooltip,
                                },
                                "legend": {"data": ["Artis", "Azalis", "Net Total"], "top": 8},
                                "grid": {
                                    "left": "3%",
                                    "right": "4%",
                                    "bottom": "14%",
                                    "containLabel": True,
                                },
                                "xAxis": {
                                    "type": "category",
                                    "data": live_waterfall_model["labels"],
                                    "axisLabel": {"interval": 0, "rotate": 25},
                                },
                                "yAxis": {
                                    "type": "value",
                                    "name": f"Degisim{unit_suffix}",
                                },
                                "series": [
                                    {
                                        "name": "Offset",
                                        "type": "bar",
                                        "stack": "total",
                                        "silent": True,
                                        "itemStyle": {
                                            "borderColor": "transparent",
                                            "color": "transparent",
                                        },
                                        "emphasis": {
                                            "itemStyle": {
                                                "borderColor": "transparent",
                                                "color": "transparent",
                                            }
                                        },
                                        "data": live_waterfall_model["helper_values"],
                                    },
                                    {
                                        "name": "Artis",
                                        "type": "bar",
                                        "stack": "total",
                                        "itemStyle": {"color": "#16a34a"},
                                        "data": live_waterfall_model["increase_values"],
                                    },
                                    {
                                        "name": "Azalis",
                                        "type": "bar",
                                        "stack": "total",
                                        "itemStyle": {"color": "#dc2626"},
                                        "data": live_waterfall_model["decrease_values"],
                                    },
                                    {
                                        "name": "Net Total",
                                        "type": "bar",
                                        "itemStyle": {"color": "#2563eb"},
                                        "data": [
                                            value if value is not None else "-"
                                            for value in live_waterfall_model["total_values"]
                                        ],
                                    },
                                ],
                            }
                        ).classes("w-full h-72")

                    max_delta_index = (
                        max(
                            comparable_indexes,
                            key=lambda index: abs(float(live_change_chart["delta_values"][index])),
                        )
                        if comparable_indexes
                        else None
                    )
                    max_delta_label = (
                        live_change_chart["labels"][max_delta_index]
                        if max_delta_index is not None
                        else "-"
                    )
                    max_delta_value = (
                        float(live_change_chart["delta_values"][max_delta_index])
                        if max_delta_index is not None
                        else 0.0
                    )
                    positive_count = sum(
                        1
                        for value in live_change_chart["delta_values"]
                        if value is not None and float(value) > 0
                    )
                    negative_count = sum(
                        1
                        for value in live_change_chart["delta_values"]
                        if value is not None and float(value) < 0
                    )

                    with ui.card().classes(
                        "w-full "
                        + (
                            "border border-red-200 bg-red-50"
                            if combined_impact_summary["tone"] == "critical"
                            else "border border-amber-200 bg-amber-50"
                            if combined_impact_summary["tone"] == "warning"
                            else "bg-slate-50"
                        )
                    ):
                        ui.label("Kisa Yorum").classes("text-sm font-medium")
                        if live_change_chart["is_normalized"]:
                            ui.label(
                                "Grafik farkli birimler nedeniyle normalize edildi; gercek sayisal farklar tooltipte verilir."
                            ).classes("text-xs text-slate-600")
                        if max_delta_index is not None:
                            ui.label(
                                "En buyuk fark ozeti: "
                                + build_parameter_delta_summary(live_change_chart, max_delta_index)
                            ).classes("text-sm")
                        else:
                            ui.label(
                                "Henuz yeni deger girilmedigi icin sadece base cizgisi gorunuyor."
                            ).classes("text-sm text-amber-700")
                        ui.label(
                            f"Artis sayisi: {positive_count} | Azalis sayisi: {negative_count} | "
                            f"Toplam degisim: {len(live_change_chart['labels'])}"
                        ).classes("text-xs text-slate-600")
                        if live_change_chart["missing_updated_labels"]:
                            missing_preview = ", ".join(
                                live_change_chart["missing_updated_labels"][:4]
                            )
                            suffix = (
                                ""
                                if len(live_change_chart["missing_updated_labels"]) <= 4
                                else " ..."
                            )
                            ui.label(
                                f"Updated cizgisi su parametrelerde henuz olusmadi: {missing_preview}{suffix}"
                            ).classes("text-xs text-amber-700")
                        ui.label(
                            f"Yapisal etki yorumu: {combined_impact_summary['message']}"
                        ).classes("text-xs text-slate-700")
                else:
                    ui.label(
                        "Anlik grafik icin numerik mevcut ve yeni degerlere sahip en az bir parametre gerekli."
                    ).classes("text-sm text-slate-500")

            with structural_impact_container:
                ui.label("Yapisal Etki Analizi").classes("text-sm font-medium")
                ui.label(str(structural_impact_model["summary"])).classes("text-sm text-slate-600")
                with ui.card().classes(
                    "w-full "
                    + (
                        "border border-red-200 bg-red-50"
                        if combined_impact_summary["tone"] == "critical"
                        else "border border-amber-200 bg-amber-50"
                        if combined_impact_summary["tone"] == "warning"
                        else "bg-slate-50"
                    )
                ):
                    ui.label("Combined Impact Ozeti").classes("text-sm font-medium")
                    ui.label(str(combined_impact_summary["message"])).classes("text-sm")
                    with ui.row().classes("w-full gap-4"):
                        with ui.column().classes("gap-1"):
                            ui.label("Degisen Alan").classes("text-xs text-slate-500")
                            ui.label(str(combined_impact_summary["changed_field_count"])).classes("text-2xl font-bold")
                        with ui.column().classes("gap-1"):
                            ui.label("Cakisan Grup").classes("text-xs text-slate-500")
                            ui.label(str(combined_impact_summary["overlapping_group_count"])).classes("text-2xl font-bold")
                    if combined_impact_summary["changed_fields"]:
                        ui.label(
                            "Alanlar: " + ", ".join(combined_impact_summary["changed_fields"])
                        ).classes("text-xs text-slate-600")
                    if combined_impact_summary["overlapping_constructions"]:
                        ui.label("Construction Cakismalari").classes("text-xs font-medium text-slate-700")
                        for item in combined_impact_summary["overlapping_constructions"]:
                            ui.label(
                                f"{item['construction_name']}: {', '.join(item['changed_fields'])}"
                            ).classes("text-xs text-slate-600")
                    if combined_impact_summary["overlapping_surfaces"]:
                        ui.label("Yuzey Cakismalari").classes("text-xs font-medium text-slate-700")
                        for item in combined_impact_summary["overlapping_surfaces"]:
                            ui.label(
                                f"{item['surface_kind']} {item['surface_name']} ({item['construction_name']}): "
                                f"{', '.join(item['changed_fields'])}"
                            ).classes("text-xs text-slate-600")
                with ui.row().classes("w-full gap-4 items-stretch"):
                    with ui.card().classes("w-full bg-emerald-50"):
                        ui.label("Dogrudan Tablo").classes("text-sm text-emerald-700")
                        ui.label(
                            str(structural_card_summary["direct_dataset_count"]["current"])
                        ).classes("text-3xl font-bold text-emerald-800")
                        ui.label(
                            str(structural_card_summary["direct_dataset_count"]["caption"])
                        ).classes("text-xs text-emerald-700")
                    with ui.card().classes("w-full bg-amber-50"):
                        ui.label("Dolayli Veri").classes("text-sm text-amber-700")
                        ui.label(
                            str(structural_card_summary["indirect_dataset_count"]["current"])
                        ).classes("text-3xl font-bold text-amber-800")
                        ui.label(
                            str(structural_card_summary["indirect_dataset_count"]["caption"])
                        ).classes("text-xs text-amber-700")
                    with ui.card().classes("w-full bg-sky-50"):
                        ui.label("Katman Hedefi").classes("text-sm text-sky-700")
                        ui.label(
                            str(structural_card_summary["layer_dataset_count"]["current"])
                        ).classes("text-3xl font-bold text-sky-800")
                        ui.label(
                            str(structural_card_summary["layer_dataset_count"]["caption"])
                        ).classes("text-xs text-sky-700")
                    with ui.card().classes(
                        build_parameter_card_classes(compact=True, selected=True)
                    ):
                        ui.label("Toplam Satir").classes("text-sm text-slate-500")
                        ui.label(
                            str(structural_card_summary["total_direct_rows"]["current"])
                        ).classes("text-3xl font-bold")
                        ui.label(
                            str(structural_card_summary["total_direct_rows"]["caption"])
                        ).classes("text-xs text-slate-500")

                if structural_errors:
                    for error in structural_errors:
                        ui.label(error).classes("text-sm text-red-600")

                if structural_impact_model["direct_rows"] or structural_impact_model["indirect_rows"]:
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        structural_filter_label = (
                            "Tum Veri Setleri"
                            if structural_filter_state["dataset"] == "Tum Veri Setleri"
                            else f"Grafik filtresi: {structural_filter_state['dataset']}"
                        )
                        ui.label(structural_filter_label).classes("text-sm text-slate-600")
                        with ui.row().classes("gap-2"):
                            dataset_filter_select = ui.select(
                                options=["Tum Veri Setleri", *dataset_filter_options],
                                value=structural_filter_state["dataset"],
                                label="Veri Seti Filtresi",
                            ).classes("w-64")
                            dataset_filter_select.on_value_change(
                                lambda e: (
                                    structural_filter_state.__setitem__(
                                        "dataset",
                                        str(e.value or "Tum Veri Setleri"),
                                    ),
                                    sync_parameter_page_query(),
                                    render_scenario_builder(),
                                )
                            )
                            ui.button(
                                "Filtreyi Temizle",
                                on_click=lambda: (
                                    structural_filter_state.__setitem__("dataset", "Tum Veri Setleri"),
                                    sync_parameter_page_query(),
                                    render_scenario_builder(),
                                ),
                            ).props("outline size=sm")
                    ui.label("Etki Iliski Grafigi").classes("text-sm font-medium")
                    structural_graph = ui.echart(structural_impact_view["graph"]).classes("w-full h-96")

                    def on_structural_graph_click(event) -> None:
                        args = getattr(event, "args", {}) or {}
                        data = args.get("data", {}) if isinstance(args, dict) else {}
                        dataset_filter = ""
                        if isinstance(data, dict):
                            dataset_filter = str(data.get("dataset_filter", "")).strip()
                        if not dataset_filter:
                            structural_filter_state["dataset"] = "Tum Veri Setleri"
                        else:
                            structural_filter_state["dataset"] = dataset_filter
                        sync_parameter_page_query()
                        render_scenario_builder()

                    structural_graph.on("click", on_structural_graph_click)

                if not filtered_structural_rows["direct_rows"]:
                    ui.label(
                        "Dogrudan etki tablosu icin once kayit secimi yapin."
                    ).classes("text-sm text-slate-500")
                else:
                    ui.table(
                        columns=[
                            {"name": "trigger", "label": "Degisen Parametre", "field": "trigger"},
                            {"name": "record_label", "label": "Kaynak Kayit", "field": "record_label"},
                            {"name": "dataset", "label": "Dogrudan Etkilenen Tablo", "field": "dataset"},
                            {"name": "affected_row_count", "label": "Satir", "field": "affected_row_count"},
                            {"name": "reasons", "label": "Neden", "field": "reasons"},
                        ],
                        rows=filtered_structural_rows["direct_rows"],
                        row_key="id",
                        pagination={"rowsPerPage": 10},
                    ).classes("w-full")

                ui.label("Dolayli Etkilenen Ogeler").classes("text-sm font-medium")
                if not filtered_structural_rows["indirect_rows"]:
                    ui.label("Dolayli etki bulunamadi veya analiz icin kayit secilmedi.").classes(
                        "text-sm text-slate-500"
                    )
                else:
                    ui.table(
                        columns=[
                            {"name": "trigger", "label": "Degisen Parametre", "field": "trigger"},
                            {"name": "dataset", "label": "Etkilenen Veri Seti", "field": "dataset"},
                            {"name": "row_key", "label": "Etkilenen Oge", "field": "row_key"},
                            {"name": "via", "label": "Baglanti", "field": "via"},
                            {"name": "reason", "label": "Neden", "field": "reason"},
                        ],
                        rows=filtered_structural_rows["indirect_rows"],
                        row_key="id",
                        pagination={"rowsPerPage": 10},
                    ).classes("w-full")

                ui.label("Katman Iliskileri").classes("text-sm font-medium")
                if not filtered_structural_rows["layer_rows"]:
                    ui.label("Katman iliskisi bulunamadi.").classes("text-sm text-slate-500")
                else:
                    ui.table(
                        columns=[
                            {"name": "trigger", "label": "Degisen Parametre", "field": "trigger"},
                            {"name": "source_row_key", "label": "Kaynak", "field": "source_row_key"},
                            {"name": "target_dataset", "label": "Hedef Veri Seti", "field": "target_dataset"},
                            {"name": "target_row_key", "label": "Hedef Kayit", "field": "target_row_key"},
                            {"name": "relationship_type", "label": "Iliski", "field": "relationship_type"},
                        ],
                        rows=filtered_structural_rows["layer_rows"],
                        row_key="id",
                        pagination={"rowsPerPage": 10},
                    ).classes("w-full")

                ui.label("Katman Etkisi").classes("text-sm font-medium")
                ui.label(
                    "Kalınlık veya benzeri degisimlerin hangi layer satirlarini etkiledigi burada ayri rozetle gosterilir."
                ).classes("text-sm text-slate-600")
                if not filtered_structural_rows["layer_impact_rows"]:
                    ui.label("Katman etkisi bulunamadi.").classes("text-sm text-slate-500")
                else:
                    layer_impact_chart = build_layer_impact_chart_model(
                        filtered_structural_rows["layer_impact_rows"]
                    )
                    if layer_impact_chart["has_data"]:
                        ui.label(
                            "Katman Etkisi Grafigi (Stacked: Changed / Unchanged)"
                        ).classes("text-sm font-medium")
                        ui.echart(
                            {
                                "tooltip": {
                                    "trigger": "axis",
                                    "axisPointer": {"type": "shadow"},
                                },
                                "legend": {"data": ["Changed", "Unchanged"]},
                                "xAxis": {
                                    "type": "category",
                                    "data": layer_impact_chart["labels"],
                                    "axisLabel": {"interval": 0, "rotate": 20},
                                },
                                "yAxis": {"type": "value", "name": "Layer Sayisi"},
                                "series": [
                                    {
                                        "name": "Changed",
                                        "type": "bar",
                                        "stack": "layer-impact",
                                        "data": layer_impact_chart["changed_values"],
                                        "itemStyle": {"color": "#dc2626"},
                                    },
                                    {
                                        "name": "Unchanged",
                                        "type": "bar",
                                        "stack": "layer-impact",
                                        "data": layer_impact_chart["unchanged_values"],
                                        "itemStyle": {"color": "#94a3b8"},
                                    },
                                ],
                            }
                        ).classes("w-full h-72")
                        ui.label(
                            "Etki seviyesi: "
                            + ", ".join(
                                f"{label}={level}"
                                for label, level in zip(
                                    layer_impact_chart["labels"],
                                    layer_impact_chart["impact_levels"],
                                )
                            )
                        ).classes("text-xs text-slate-600")

                    grouped_layer_impacts = group_layer_impact_rows_by_construction(
                        filtered_structural_rows["layer_impact_rows"]
                    )
                    with ui.column().classes("w-full gap-3"):
                        for group in grouped_layer_impacts:
                            header = (
                                f"{group['construction_label']} | "
                                f"katman={group['row_count']} | "
                                f"degisen={group['changed_count']} | "
                                f"etkilenen={group['impacted_count']}"
                            )
                            with ui.expansion(header, value=True).classes("w-full"):
                                with ui.column().classes("w-full gap-3 pt-2"):
                                    for item in group["rows"]:
                                        is_changed_layer = str(item["badge"]) == "Degisen Layer"
                                        card_classes = (
                                            "w-full border border-red-200 bg-red-50"
                                            if is_changed_layer
                                            else "w-full bg-slate-50"
                                        )
                                        with ui.card().classes(card_classes):
                                            with ui.row().classes("w-full items-stretch gap-3"):
                                                with ui.column().classes(
                                                    "w-1 rounded-full bg-red-500" if is_changed_layer else "w-1 rounded-full bg-slate-200"
                                                ):
                                                    pass
                                                with ui.column().classes("grow gap-3"):
                                                    with ui.row().classes("w-full items-start justify-between gap-3"):
                                                        with ui.row().classes("items-start gap-2"):
                                                            if is_changed_layer:
                                                                ui.icon("priority_high").classes("text-red-600 text-lg mt-0.5")
                                                            with ui.column().classes("gap-1"):
                                                                ui.label(str(item["layer_name"])).classes("text-sm font-medium")
                                                                ui.label(
                                                                    f"Material: {item['material_name']} | Alan: {item['changed_field']}"
                                                                ).classes("text-xs text-slate-600")
                                                        ui.badge(
                                                            str(item["badge"]),
                                                            color="negative" if is_changed_layer else "primary",
                                                        )
                                                    with ui.row().classes("w-full gap-4"):
                                                        with ui.column().classes("gap-1"):
                                                            ui.label("Eski Deger").classes("text-xs text-slate-500")
                                                            ui.label(str(item["old_value"])).classes("text-sm")
                                                        with ui.column().classes("gap-1"):
                                                            ui.label("Yeni Deger").classes("text-xs text-slate-500")
                                                            ui.label(str(item["new_value"])).classes("text-sm")
                                                with ui.column().classes("gap-1 grow"):
                                                    ui.label("Bagli Construction'lar").classes("text-xs text-slate-500")
                                                    ui.label(str(item["construction_names"])).classes("text-sm")

                ui.label("Yuzey Etkisi").classes("text-sm font-medium")
                ui.label(
                    "Degisimin modelde hangi duvar, cati ve doseme ogelerine yayildigi burada listelenir."
                ).classes("text-sm text-slate-600")
                if not filtered_structural_rows["surface_impact_rows"]:
                    ui.label("Yuzey etkisi bulunamadi.").classes("text-sm text-slate-500")
                else:
                    ui.table(
                        columns=[
                            {"name": "surface_kind", "label": "Yuzey Turu", "field": "surface_kind"},
                            {"name": "surface_name", "label": "Yuzey Adi", "field": "surface_name"},
                            {"name": "construction_name", "label": "Kullanilan Construction", "field": "construction_name"},
                            {"name": "reason", "label": "Etkilenme Nedeni", "field": "reason"},
                        ],
                        rows=filtered_structural_rows["surface_impact_rows"],
                        row_key="id",
                        pagination={"rowsPerPage": 10},
                    ).classes("w-full")

        def render_selected_parameters() -> None:
            selected_parameters_container.clear()
            selected_inline_chart_container.clear()
            selected_overlay_chart_container.clear()
            selected_panel_actions.clear()

            selected_total = len(selected_parameters)
            if selected_total:
                selected_count_label.set_text(
                    f"{selected_total} parametre secildi · sonraki adim: kayit secimi ve yeni deger girisi"
                )
            else:
                selected_count_label.set_text("Henuz parametre secilmedi")

            with selected_panel_actions:
                if selected_parameters:
                    with ui.row().classes("gap-2"):
                        ui.button(
                            "Tumunu Temizle",
                            on_click=clear_selected_parameters,
                        ).props("outline size=sm color=negative")
                        ui.button(
                            "Deger Girisine Gec",
                            on_click=render_scenario_builder,
                        ).props("color=primary size=sm unelevated icon=arrow_forward")
            with selected_parameters_container:
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    for label, completed in build_selected_progress_steps():
                        ui.label(label).classes(
                            "rounded-full px-3 py-1 text-xs font-medium "
                            + (
                                "bg-emerald-100 text-emerald-800"
                                if completed
                                else "bg-slate-100 text-slate-600"
                            )
                        )

                if not selected_parameters:
                    with ui.card().classes(
                        "rounded-[20px] border border-dashed border-slate-300 bg-slate-50/70 shadow-none"
                    ):
                        with ui.column().classes("items-center gap-2 py-8 text-center"):
                            with ui.element("span").classes("empty-state-icon success"):
                                ui.icon("playlist_add_check_circle").classes("text-3xl")
                            ui.label("Henuz parametre secilmedi").classes("text-base font-semibold text-slate-900")
                            ui.label(
                                "Sagdaki kartlardan `Sec` butonuna basarak parametreleri bu alana ekleyebilirsiniz."
                            ).classes("max-w-sm text-sm text-slate-600")
                    selected_overlay_chart_info.set_text(
                        "Overlay grafik icin once en az bir parametre secin."
                    )
                    with selected_inline_chart_container:
                        with ui.card().classes(
                            "rounded-[18px] border border-slate-200 bg-slate-50/80 shadow-none"
                        ):
                            ui.label("Grafik onizlemesi icin parametre secimi bekleniyor.").classes(
                                "text-sm text-slate-500"
                            )
                    with selected_overlay_chart_container:
                        with ui.card().classes(
                            "rounded-[18px] border border-slate-200 bg-slate-50/80 shadow-none"
                        ):
                            ui.label("Grafik onizlemesi icin parametre secimi bekleniyor.").classes(
                                "text-sm text-slate-500"
                            )
                    return

                with ui.card().classes(
                    "rounded-[18px] border border-sky-200 bg-sky-50/80 shadow-none"
                ):
                    with ui.column().classes("gap-2"):
                        ui.label("Sonraki Adimlar").classes("text-sm font-semibold text-sky-900")
                        ui.label(
                            "1. Her parametre icin uygun kaydi secin. 2. Yeni degeri girin. 3. Ardindan senaryo hazirlik alanina gecin."
                        ).classes("text-sm text-sky-800")

                change_chart_model = build_parameter_change_chart_model(selected_parameters)
                parameter_transition_rows = build_parameter_transition_rows(change_chart_model)
                if change_chart_model["has_data"]:
                    comparable_indexes = [
                        index
                        for index, value in enumerate(change_chart_model["delta_values"])
                        if value is not None
                    ]
                    max_delta_index = (
                        max(
                            comparable_indexes,
                            key=lambda index: abs(float(change_chart_model["delta_values"][index])),
                        )
                        if comparable_indexes
                        else None
                    )
                    max_delta_label = (
                        change_chart_model["labels"][max_delta_index]
                        if max_delta_index is not None
                        else "-"
                    )
                    max_delta_value = (
                        float(change_chart_model["delta_values"][max_delta_index])
                        if max_delta_index is not None
                        else 0.0
                    )
                    overlay_model = build_overlay_chart_model(
                        chart_name="Parametre Overlay",
                        x_labels=change_chart_model["labels"],
                        series=[
                            {
                                "name": "Base",
                                "data": change_chart_model["before_values"],
                                "origin": "base",
                                "line_type": "line",
                                "line_style": "solid",
                                "color": "#1f2937",
                            },
                            {
                                "name": "Updated",
                                "data": change_chart_model["after_values"],
                                "origin": "scenario",
                                "line_type": "line",
                                "line_style": "dashed",
                                "color": "#0f766e",
                            },
                        ],
                    )
                    overlay_series = overlay_chart_model_to_echart_series(overlay_model)
                    y_axis_name = (
                        "Normalize Edilmis Deger"
                        if change_chart_model["is_normalized"]
                        else "Deger"
                    )
                    selected_overlay_chart_info.set_text(
                        "Bu grafik secilen parametrelerin degisiklik oncesi base degerlerini ve girdiginiz updated degerlerini ayni eksen uzerinde gosterir."
                    )
                    def render_overlay_chart(target_container: ui.column) -> None:
                        with target_container:
                            ui.label("Ilk Hali / Yeni Hali Overlay Grafigi").classes("text-sm font-medium")
                            ui.label(
                                "Base duz cizgi, Updated kesikli cizgi ile gosterilir. Farkli birimler varsa cizgi normalize edilir; tooltip gercek degerleri verir."
                            ).classes("text-xs text-slate-600")
                            ui.echart(
                                {
                                    "tooltip": {
                                        "trigger": "axis",
                                        "formatter": build_parameter_overlay_tooltip_formatter(
                                            change_chart_model
                                        ),
                                    },
                                    "legend": {
                                        "data": [series.get("name", "Series") for series in overlay_series],
                                        "top": 8,
                                    },
                                    "grid": {
                                        "left": "3%",
                                        "right": "4%",
                                        "bottom": "12%",
                                        "containLabel": True,
                                    },
                                    "xAxis": {
                                        "type": "category",
                                        "data": overlay_model.x_labels,
                                        "axisLabel": {"interval": 0, "rotate": 25},
                                    },
                                    "yAxis": {"type": "value", "name": y_axis_name},
                                    "series": overlay_series,
                                }
                            ).classes("w-full h-96")
                            if change_chart_model["is_normalized"]:
                                ui.label(
                                    "Not: Farkli birimler nedeniyle cizgi yukseklikleri normalize edildi; sayisal karsilastirma icin tooltip kullanin."
                                ).classes("text-xs text-slate-500")
                            if max_delta_index is not None:
                                ui.label(
                                    "En buyuk fark ozeti: "
                                    + build_parameter_delta_summary(change_chart_model, max_delta_index)
                                ).classes("text-xs text-slate-600")
                            else:
                                ui.label(
                                    "Yeni deger girilmedigi icin su anda yalnizca base cizgisi gosteriliyor."
                                ).classes("text-xs text-amber-700")
                            if change_chart_model["missing_updated_labels"]:
                                missing_preview = ", ".join(
                                    change_chart_model["missing_updated_labels"][:4]
                                )
                                suffix = (
                                    ""
                                    if len(change_chart_model["missing_updated_labels"]) <= 4
                                    else " ..."
                                )
                                ui.label(
                                    f"Updated cizgisi su parametrelerde henuz olusmadi: {missing_preview}{suffix}"
                                ).classes("text-xs text-amber-700")

                    render_overlay_chart(selected_inline_chart_container)
                    with selected_overlay_chart_container:
                        ui.label("Ilk Hali / Yeni Hali Overlay Grafigi").classes("text-sm font-medium")
                        ui.label(
                            "Base duz cizgi, Updated kesikli cizgi ile gosterilir. Farkli birimler varsa cizgi normalize edilir; tooltip gercek degerleri verir."
                        ).classes("text-xs text-slate-600")
                        ui.echart(
                            {
                                "tooltip": {
                                    "trigger": "axis",
                                    "formatter": build_parameter_overlay_tooltip_formatter(
                                        change_chart_model
                                    ),
                                },
                                "legend": {
                                    "data": [series.get("name", "Series") for series in overlay_series],
                                    "top": 8,
                                },
                                "grid": {
                                    "left": "3%",
                                    "right": "4%",
                                    "bottom": "12%",
                                    "containLabel": True,
                                },
                                "xAxis": {
                                    "type": "category",
                                    "data": overlay_model.x_labels,
                                    "axisLabel": {"interval": 0, "rotate": 25},
                                },
                                "yAxis": {"type": "value", "name": y_axis_name},
                                "series": overlay_series,
                            }
                        ).classes("w-full h-96")
                        if change_chart_model["is_normalized"]:
                            ui.label(
                                "Not: Farkli birimler nedeniyle cizgi yukseklikleri normalize edildi; sayisal karsilastirma icin tooltip kullanin."
                            ).classes("text-xs text-slate-500")
                        if max_delta_index is not None:
                            ui.label(
                                "En buyuk fark ozeti: "
                                + build_parameter_delta_summary(change_chart_model, max_delta_index)
                            ).classes("text-xs text-slate-600")
                        else:
                            ui.label(
                                "Yeni deger girilmedigi icin su anda yalnizca base cizgisi gosteriliyor."
                            ).classes("text-xs text-amber-700")
                        if change_chart_model["missing_updated_labels"]:
                            missing_preview = ", ".join(
                                change_chart_model["missing_updated_labels"][:4]
                            )
                            suffix = (
                                ""
                                if len(change_chart_model["missing_updated_labels"]) <= 4
                                else " ..."
                            )
                            ui.label(
                                f"Updated cizgisi su parametrelerde henuz olusmadi: {missing_preview}{suffix}"
                            ).classes("text-xs text-amber-700")

                        ui.separator()
                        ui.label("Parametre Bazli Degisim Grafikleri").classes("text-sm font-medium")
                        if parameter_transition_rows:
                            ui.label(
                                "Her degistirdigin parametre icin ayri bir Ilk Deger / Yeni Deger grafigi olusturuldu."
                            ).classes("text-xs text-slate-600")
                            with ui.row().classes("w-full gap-4 items-stretch flex-wrap"):
                                for item in parameter_transition_rows:
                                    with ui.card().classes("w-full min-w-[20rem] grow"):
                                        ui.label(str(item["label"])).classes("text-sm font-medium")
                                        ui.label(
                                            build_parameter_delta_summary(
                                                {
                                                    "labels": [item["label"]],
                                                    "base_values": [item["base_value"]],
                                                    "updated_values": [item["updated_value"]],
                                                    "units": [item["unit"]],
                                                },
                                                0,
                                            )
                                        ).classes("text-xs text-slate-600")
                                        ui.echart(
                                            build_value_transition_chart_options(
                                                label=str(item["label"]),
                                                base_value=item["base_value"],
                                                updated_value=item["updated_value"],
                                                unit=str(item["unit"]),
                                            )
                                        ).classes("w-full h-64")
                        else:
                            ui.label(
                                "Ayrik grafik olusmasi icin sayisal ve degismis en az bir parametre gerekli."
                            ).classes("text-xs text-slate-500")
                else:
                    selected_overlay_chart_info.set_text(
                        "Overlay grafik icin numerik mevcut ve yeni degerlere sahip parametreler gerekli."
                    )
                    with selected_inline_chart_container:
                        ui.label(
                            "Secili parametreler numerik olmadigi icin grafik olusturulamadi."
                        ).classes("text-sm text-amber-700")
                    with selected_overlay_chart_container:
                        ui.label(
                            "Secili parametreler numerik olmadigi icin grafik olusturulamadi."
                        ).classes("text-sm text-amber-700")

                if change_chart_model["skipped_count"]:
                    skipped_text = ", ".join(change_chart_model["skipped_labels"][:4])
                    suffix = "" if change_chart_model["skipped_count"] <= 4 else " ..."
                    ui.label(
                        f"Not: {change_chart_model['skipped_count']} parametre numerik olmayan deger nedeniyle grafikte gosterilmedi: {skipped_text}{suffix}"
                    ).classes("text-xs text-amber-700")

                for parameter_id, item in selected_parameters.items():
                    parameter = item["definition"]
                    current_value = str(item["current_value"])
                    new_value = str(item["new_value"])
                    record_label = str(item.get("record_label", ""))
                    is_ready = is_selected_parameter_ready(item)
                    record_missing = not bool(record_label.strip())
                    new_value_missing = not bool(new_value.strip())
                    record_choices = build_parameter_record_choices(parameter.dataset)
                    explanation = build_parameter_explanation(
                        field_name=parameter.field_name,
                        label=parameter.label,
                        description=parameter.description,
                        expected_impacts=parameter.expected_impacts,
                    )
                    parameter_impact_model = build_parameter_impact_map_model(
                        {
                            parameter_id: item,
                        }
                    )
                    parameter_impact_row = (
                        parameter_impact_model["rows"][0]
                        if parameter_impact_model.get("rows")
                        else {}
                    )
                    parameter_change_state = analyze_parameter_change_state(
                        parameter=parameter,
                        current_value=item.get("current_value"),
                        new_value=item.get("new_value"),
                    )
                    parameter_impact_scores = {
                        dimension: int(dict(parameter_impact_row.get(dimension, {})).get("score", 0))
                        for dimension in PARAMETER_IMPACT_DIMENSIONS
                    }
                    change_summary_text = build_parameter_change_summary_text(
                        parameter=parameter,
                        current_value=item.get("current_value"),
                        new_value=item.get("new_value"),
                        change_state=parameter_change_state,
                    )
                    expected_effect_text = build_parameter_expected_effect_text(parameter_impact_row)
                    direction_badge_label, direction_badge_color = build_change_direction_badge(
                        parameter_change_state
                    )
                    strength_badge_label, strength_badge_color = build_change_strength_badge(
                        parameter_change_state
                    )
                    summary_card_classes = build_change_summary_card_classes(parameter_change_state)
                    summary_icon_name, summary_icon_classes = build_change_summary_icon(
                        parameter_change_state
                    )

                    with ui.card().classes(
                        "w-full border rounded-[20px] "
                        + (
                            "border-emerald-200 bg-emerald-50/60"
                            if is_ready
                            else "border-amber-200 bg-amber-50/50"
                        )
                    ):
                        with ui.row().classes("w-full justify-between items-start gap-3"):
                            with ui.column().classes("gap-1"):
                                ui.label(parameter.label).classes("text-sm font-medium")
                                ui.label(f"{parameter.dataset}.{parameter.field_name}").classes(
                                    "text-xs text-slate-500"
                                )
                                ui.label(explanation["summary"]).classes("text-xs text-slate-700")
                                ui.label(explanation["impact"]).classes("text-xs text-slate-600")
                                with ui.row().classes("gap-2 items-center"):
                                    ui.badge(parameter.category).props("outline color=primary")
                                    ui.badge(
                                        "Tamamlandi" if is_ready else "Eksik",
                                        color="positive" if is_ready else "warning",
                                    )
                            with ui.column().classes("items-end gap-2"):
                                with ui.row().classes("gap-1"):
                                    ui.button(
                                        icon="keyboard_arrow_up",
                                        on_click=lambda pid=parameter_id: move_selected_parameter(pid, -1),
                                    ).props("flat dense size=sm")
                                    ui.button(
                                        icon="keyboard_arrow_down",
                                        on_click=lambda pid=parameter_id: move_selected_parameter(pid, 1),
                                    ).props("flat dense size=sm")
                                ui.button(
                                    "Kaldir",
                                    on_click=lambda pid=parameter_id: remove_parameter(pid),
                                ).props("flat color=negative size=sm")

                        record_select = ui.select(
                            options=list(record_choices.keys()),
                            value=record_label or None,
                            label="Kayit Secimi",
                        ).classes("w-full dashboard-input")
                        record_select.on_value_change(
                            lambda e, pid=parameter_id: set_parameter_record(pid, str(e.value or ""))
                        )
                        if record_missing:
                            ui.label("Bu parametre icin once bir kayit secin.").classes(
                                "text-xs text-amber-700"
                            )

                        with ui.row().classes("w-full gap-4 items-end"):
                            with ui.column().classes("gap-1 min-w-24"):
                                ui.label("Mevcut Deger").classes("text-xs text-slate-500")
                                ui.label(current_value or "-").classes("text-sm")

                            with ui.column().classes("gap-1 grow"):
                                new_value_input = ui.input(
                                    label="Yeni Deger",
                                    value=new_value,
                                    placeholder=f"Ornek: {parameter.example}",
                                ).classes("w-full dashboard-input")
                                if parameter.value_type in {"float", "integer"}:
                                    new_value_input.props("inputmode=decimal")
                                ui.label(build_parameter_recommended_range_text(parameter)).classes(
                                    build_parameter_recommended_range_style(parameter, new_value)
                                )
                                new_value_input.on_value_change(
                                    lambda e, pid=parameter_id: (
                                        selected_parameters[pid].__setitem__("new_value", e.value),
                                        sync_parameter_page_query(),
                                        render_scenario_builder(),
                                    )
                                )
                                for warning in validate_parameter_new_value(
                                    parameter=parameter,
                                    current_value=current_value,
                                    new_value=new_value,
                                ):
                                    ui.label(warning).classes("text-xs text-amber-700")
                                if new_value_missing:
                                    ui.label("Yeni deger girilmeden senaryo olusturulamaz.").classes(
                                        "text-xs text-amber-700"
                                    )

                            with ui.column().classes("gap-1 min-w-20"):
                                ui.label("Birim").classes("text-xs text-slate-500")
                                ui.label(parameter.unit or "-").classes("text-sm")

                        ui.separator()
                        ui.label("Degisim Ozeti").classes("text-xs font-medium text-slate-700")
                        if bool(parameter_change_state.get("has_effective_change")):
                            with ui.card().classes(summary_card_classes):
                                with ui.row().classes("w-full gap-2 items-center"):
                                    ui.icon(summary_icon_name).classes("text-lg " + summary_icon_classes)
                                    ui.badge(direction_badge_label, color=direction_badge_color)
                                    ui.badge(strength_badge_label, color=strength_badge_color).props("outline")
                                ui.label(change_summary_text).classes("text-sm text-slate-800")
                                ui.label(expected_effect_text).classes("text-xs text-slate-600")
                                top_effects = [
                                    format_impact_dimension_label(dimension)
                                    for dimension in PARAMETER_IMPACT_DIMENSIONS
                                    if parameter_impact_scores.get(dimension, 0) > 0
                                ]
                                if top_effects:
                                    ui.label(
                                        "Etki alanlari: " + ", ".join(top_effects[:4])
                                    ).classes("text-xs text-slate-500")
                        else:
                            with ui.card().classes(summary_card_classes):
                                with ui.row().classes("w-full gap-2 items-center"):
                                    ui.icon(summary_icon_name).classes("text-lg " + summary_icon_classes)
                                    ui.badge(direction_badge_label, color=direction_badge_color)
                                    ui.badge(strength_badge_label, color=strength_badge_color).props("outline")
                                ui.label(change_summary_text).classes("text-xs text-slate-700")


        def render_parameter_list() -> None:
            parameter_list_container.clear()
            active_section = str(parameter_section_tabs.value or "").strip()
            active_category = str(category_filter_state["value"] or "").strip()
            if not active_category and not active_section:
                parameter_panel_title.set_text("Parametre Listesi")
                parameter_panel_description.set_text("Secilen kategoriye ait parametreler burada listelenir.")
                parameter_context_badge.set_text("Kategori Secilmedi")
                parameter_result_info.set_text("Parametreleri gormek icin soldan bir kategori veya ustten bir bolum secin.")
                with parameter_list_container:
                    with ui.card().classes(
                        "col-span-full min-h-[320px] rounded-[24px] border border-dashed border-slate-300 bg-slate-50/70 shadow-none"
                    ):
                        with ui.column().classes("h-full min-h-[280px] items-center justify-center gap-3 text-center"):
                            with ui.element("span").classes("empty-state-icon"):
                                ui.icon("dashboard_customize").classes("text-4xl")
                            ui.label("Henuz kategori secilmedi").classes("text-xl font-semibold text-slate-900")
                            ui.label(
                                "Soldaki listeden bir kategori secerek parametre listesini acabilirsiniz."
                            ).classes("max-w-md text-sm text-slate-600")
                            ui.label(
                                "Tum Kategoriler secilirse butun parametreler birlikte listelenir."
                            ).classes("text-xs text-slate-500")
                return
            section_filtered_parameters = filter_parameters_for_section(
                all_parameters,
                active_section or "Tum",
            )
            filtered_parameters = filter_parameter_definitions(
                section_filtered_parameters,
                category=active_category or "Tum Kategoriler",
                query=str(parameter_search.value or ""),
            )

            parameter_result_info.set_text(
                f"Toplam parametre: {len(all_parameters)} | Bolum: {len(section_filtered_parameters)} | Filtrelenen: {len(filtered_parameters)}"
            )
            visible_context = active_category or (
                "Tum Kategoriler" if (active_section or "Tum") == "Tum" else active_section
            )
            parameter_panel_title.set_text(f"{visible_context} Parametreleri")
            parameter_panel_description.set_text(
                f"Secilen kategoriye ait parametreler burada listelenir: {visible_context}."
            )
            parameter_context_badge.set_text(f"Secili: {visible_context}")

            with parameter_list_container:
                if not filtered_parameters:
                    with ui.card().classes(
                        "col-span-full rounded-[20px] border border-slate-200 bg-slate-50/80 shadow-none"
                    ):
                        with ui.column().classes("items-center gap-2 py-10 text-center"):
                            with ui.element("span").classes("empty-state-icon warning"):
                                ui.icon("search_off").classes("text-3xl")
                            ui.label("Eslesen parametre bulunamadi").classes("text-base font-medium text-slate-800")
                            ui.label(
                                "Arama terimini veya secili kategoriyi degistirerek tekrar deneyin."
                            ).classes("text-sm text-slate-500")
                    return

                for parameter in filtered_parameters:
                    is_selected = parameter.id in selected_parameters
                    is_emphasized = highlighted_parameter_state["id"] == parameter.id
                    explanation = build_parameter_explanation(
                        field_name=parameter.field_name,
                        label=parameter.label,
                        description=parameter.description,
                        expected_impacts=parameter.expected_impacts,
                    )
                    with ui.card().classes(
                        build_parameter_card_classes(
                            compact=True,
                            selected=is_selected,
                            emphasized=is_emphasized,
                        )
                    ):
                        with ui.row().classes("w-full justify-between items-start gap-4"):
                            with ui.column().classes("gap-1 grow"):
                                ui.label(parameter.label).classes("text-base font-semibold text-slate-900")
                                with ui.row().classes("gap-2 items-center"):
                                    ui.badge(parameter.category).props("outline color=primary")
                                    ui.label(parameter.id).classes("text-xs text-slate-500")
                                ui.label(
                                    f"{parameter.dataset}.{parameter.field_name}"
                                ).classes("text-sm text-slate-600")
                                ui.label(explanation["summary"]).classes("text-sm text-slate-600")
                                ui.label(explanation["impact"]).classes("text-xs text-slate-600")
                                ui.label(
                                    f"Birim: {parameter.unit or '-'} | Tip: {parameter.value_type} | "
                                    f"Mevcut onizleme: {get_parameter_current_value_preview(parameter.dataset, parameter.field_name)}"
                                ).classes("text-xs text-slate-500")

                            ui.button(
                                "Kaldir" if is_selected else "Sec",
                                on_click=(
                                    (lambda pid=parameter.id: remove_parameter(pid))
                                    if is_selected
                                    else (lambda p=parameter: add_parameter(p))
                                ),
                            ).props(
                                "outline color=positive size=sm"
                                if is_selected
                                else "color=primary unelevated size=sm"
                            ).classes("parameter-action-button")

        def render_category_navigation() -> None:
            category_list_container.clear()
            active_category = str(category_filter_state["value"] or "").strip()
            normalized_query = str(category_search_state["query"] or "").strip().lower()
            with category_list_container:
                for option in category_options:
                    if normalized_query and normalized_query not in option.lower():
                        continue
                    is_active = option == active_category
                    item_classes = "parameter-category-item"
                    if is_active:
                        item_classes += " parameter-category-item-active"
                    with ui.element("button").classes(item_classes).on(
                        "click",
                        lambda _=None, value=option: set_category_filter_value(value),
                    ):
                        with ui.row().classes("w-full items-center justify-between gap-3"):
                            with ui.row().classes("items-center gap-3"):
                                with ui.element("span").classes("parameter-category-icon"):
                                    ui.icon(category_icons.get(option, "category")).classes("text-base")
                                with ui.column().classes("gap-0"):
                                    ui.label(option).classes(
                                        "text-sm font-semibold text-slate-900"
                                        if is_active
                                        else "text-sm font-medium text-slate-700"
                                    )
                                    if option == "Tum Kategoriler":
                                        ui.label("Butun parametreleri birlikte gosterir.").classes(
                                            "text-xs text-slate-500"
                                        )
                            ui.html(
                                f"<span class='parameter-category-count'>{category_counts.get(option, 0)}</span>"
                            )
                if normalized_query and not any(
                    normalized_query in option.lower() for option in category_options
                ):
                    ui.label("Eslesen kategori bulunamadi.").classes("text-sm text-slate-500")

        def set_category_filter_value(value: str | None) -> None:
            normalized_value = str(value or "").strip()
            if normalized_value == str(category_filter_state["value"] or "").strip():
                return
            category_filter_state["value"] = normalized_value
            render_category_navigation()
            handle_category_filter_change()

        def refresh_parameter_list_with_query_sync() -> None:
            sync_parameter_page_query()
            render_parameter_list()

        def handle_parameter_section_change() -> None:
            current_section = str(parameter_section_tabs.value or "").strip()
            if not current_section:
                refresh_parameter_list_with_query_sync()
                return

            current_category = str(category_filter_state["value"] or "").strip()
            allowed_categories = resolve_parameter_section_categories(current_section)
            if not current_category:
                category_filter_state["value"] = resolve_default_category_for_section(current_section)
                render_category_navigation()
                refresh_parameter_list_with_query_sync()
                return
            if allowed_categories and current_category not in allowed_categories:
                category_filter_state["value"] = resolve_default_category_for_section(current_section)
                render_category_navigation()
                refresh_parameter_list_with_query_sync()
                return
            refresh_parameter_list_with_query_sync()

        def handle_category_filter_change() -> None:
            selected_category = str(category_filter_state["value"] or "").strip()
            if not selected_category:
                if parameter_section_tabs.value is not None:
                    parameter_section_tabs.set_value(None)
                    return
                refresh_parameter_list_with_query_sync()
                return

            next_section = resolve_parameter_section_for_category(selected_category)
            if str(parameter_section_tabs.value or "") != next_section:
                parameter_section_tabs.set_value(next_section)
                return
            refresh_parameter_list_with_query_sync()

        def refresh_scenario_builder_with_query_sync() -> None:
            sync_parameter_page_query()
            render_scenario_builder()

        parameter_section_tabs.on_value_change(lambda _: handle_parameter_section_change())
        category_search_input.on_value_change(
            lambda e: (
                category_search_state.__setitem__("query", str(e.value or "")),
                render_category_navigation(),
            )
        )
        parameter_search.on_value_change(lambda _: refresh_parameter_list_with_query_sync())
        scenario_name_input.on_value_change(lambda _: refresh_scenario_builder_with_query_sync())
        scenario_description_input.on_value_change(lambda _: refresh_scenario_builder_with_query_sync())
        render_category_navigation()

        for parameter_id in restored_query_state["selected_parameter_ids"]:
            parameter = parameter_by_id.get(parameter_id)
            if parameter is None:
                continue
            restored_selection_state = restored_query_state["selected_parameter_state"].get(
                parameter_id,
                {},
            )
            record_label = str(restored_selection_state.get("record_label", "")).strip()
            record_choice = None
            current_value = get_parameter_current_value_preview(
                parameter.dataset,
                parameter.field_name,
            )
            if record_label:
                record_choice = build_parameter_record_choices(parameter.dataset).get(record_label)
                if isinstance(record_choice, dict):
                    row = record_choice.get("row", {})
                    current_value = str(row.get(parameter.field_name, "")).strip() or "-"
            selected_parameters[parameter.id] = {
                "definition": parameter,
                "current_value": current_value,
                "new_value": str(restored_selection_state.get("new_value", "")).strip(),
                "record_label": record_label,
                "record_choice": record_choice,
            }

        sync_parameter_page_query()
        refresh_share_link_preview()
        render_parameter_list()
        render_selected_parameters()
        render_scenario_builder()


@ui.page("/")
def main_page() -> None:
    ui.page_title("CSV Izleme Paneli")
    dark_mode = ui.dark_mode()
    ui.add_head_html(
        """
        <style>
        :root {
            --ui-primary: #2563eb;
            --ui-success: #059669;
            --ui-warning: #d97706;
            --ui-surface: #ffffff;
            --ui-surface-muted: #f8fafc;
            --ui-text-muted: #64748b;
            --ui-border: #e2e8f0;
        }
        .dashboard-hero {
            background: color-mix(in srgb, var(--ui-surface) 82%, transparent);
            border: 1px solid rgba(148, 163, 184, 0.22);
            box-shadow: 0 24px 80px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(10px);
        }
        .dashboard-summary-card {
            border-radius: 22px;
            min-height: 138px;
            border: 1px solid var(--ui-border);
            background: color-mix(in srgb, var(--ui-surface) 95%, transparent);
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        .dashboard-panel {
            border-radius: 24px;
            border: 1px solid var(--ui-border);
            background: color-mix(in srgb, var(--ui-surface) 96%, transparent);
            box-shadow: 0 14px 36px rgba(15, 23, 42, 0.06);
        }
        .dashboard-tabs {
            gap: 0.75rem;
            background: transparent !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        .dashboard-tabs .q-tabs__content {
            gap: 0.75rem;
        }
        .dashboard-tabs .q-tab {
            min-height: auto;
            border-radius: 9999px;
            border: 1px solid #dbe4f0;
            background: rgba(255, 255, 255, 0.92);
            color: #475569;
            padding: 0.2rem 0.5rem;
        }
        .dashboard-tabs .q-tab--active {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-color: #93c5fd;
            color: #1d4ed8;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.12);
        }
        .dashboard-tabs .q-tab__label {
            font-size: 0.85rem;
            font-weight: 600;
        }
        .dashboard-input .q-field__control {
            border-radius: 16px;
            background: #f8fafc;
        }
        @media (max-width: 768px) {
            .dashboard-hero {
                border-radius: 22px !important;
            }
            .dashboard-summary-card,
            .dashboard-panel {
                border-radius: 20px !important;
            }
            .dashboard-tabs .q-tabs__content {
                gap: 0.5rem;
                flex-wrap: wrap;
            }
            .dashboard-tabs .q-tab {
                padding: 0.15rem 0.4rem;
            }
        }
        </style>
        """
    )
    request = getattr(ui.context.client, "request", None)
    requested_scenario = ""
    requested_focus = ""
    if request is not None:
        requested_scenario = str(request.query_params.get("scenario", "")).strip()
        requested_focus = str(request.query_params.get("focus", "")).strip().lower()

    state = {
        "csv_files": [path.as_posix() for path in collect_csv_files()],
        "log_files": [path.as_posix() for path in collect_log_files()],
        "scenario_files": [path.as_posix() for path in collect_scenario_files()],
        "audit_files": [path.as_posix() for path in collect_audit_files()],
    }
    selected_csv = get_initial_csv(state["csv_files"])
    selected_log = get_initial_log(state["log_files"])
    selected_scenario = (
        requested_scenario
        if requested_scenario in state["scenario_files"]
        else get_initial_scenario(state["scenario_files"])
    )
    selected_audit = get_initial_audit(state["audit_files"])

    with ui.header().classes("items-center justify-between bg-slate-800 text-white"):
        ui.label("CSV ve Senaryo Izleme Paneli").classes("text-lg font-medium")
        with ui.row().classes("items-center gap-3"):
            ui.button("Parametre Secimi", on_click=lambda: ui.navigate.to("/parameters")).props(
                "flat color=white"
            )
            ui.label("Koyu Tema").classes("text-sm")
            ui.switch(value=False, on_change=lambda e: dark_mode.set_value(bool(e.value)))

    with ui.column().classes("w-full max-w-[1480px] mx-auto px-6 py-8 gap-6"):
        with ui.card().classes("w-full dashboard-hero rounded-[28px] border-0 px-6 py-5"):
            ui.label("CSV ve Senaryo Izleme Paneli").classes("text-[28px] font-semibold tracking-tight text-slate-900")
            ui.label(
                "CSV verileri, degisiklik loglari, analiz ciktilari ve senaryo akislarini tek ekranda izleyin."
            ).classes("text-sm text-slate-600")

        with ui.row().classes("w-full gap-4 items-stretch"):
            with ui.card().classes("w-full dashboard-summary-card"):
                ui.label("Toplam Senaryo Ciktisi").classes("text-sm text-slate-500")
                total_scenarios_value = ui.label("0").classes("text-3xl font-bold")

            with ui.card().classes("w-full dashboard-summary-card"):
                ui.label("Toplam Degisen Alan").classes("text-sm text-slate-500")
                total_changes_value = ui.label("0").classes("text-3xl font-bold")

            with ui.card().classes("w-full dashboard-summary-card"):
                ui.label("Son Calistirilan Senaryo").classes("text-sm text-slate-500")
                last_scenario_value = ui.label("-").classes("text-lg font-medium")

        ui.label("Calisma Alanlari").classes("text-sm font-medium uppercase tracking-[0.12em] text-slate-500")
        with ui.tabs().classes("w-full dashboard-tabs") as tabs:
            data_tab = ui.tab("Veri")
            logs_tab = ui.tab("Loglar")
            audit_tab = ui.tab("Denetim")
            scenarios_tab = ui.tab("Senaryolar")
            analytics_tab = ui.tab("Analiz")
            cost_tab = ui.tab("Maliyet")

        with ui.tab_panels(tabs, value=data_tab).classes("w-full"):
            with ui.tab_panel(data_tab):
                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Hizli Erisim").classes("text-base font-medium")
                    quick_access_row = ui.row().classes("w-full gap-2")

                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("CSV Veri Tablosu").classes("text-lg font-semibold text-slate-900")
                    csv_select = ui.select(
                        options=state["csv_files"],
                        value=selected_csv,
                        label="CSV dosyasi",
                    ).classes("w-full dashboard-input")
                    with ui.row().classes("w-full gap-4"):
                        global_search = ui.input(
                            label="Genel arama",
                            placeholder="Tum kolonlarda ara",
                        ).props("outlined clearable").classes("w-full dashboard-input")
                        column_filter_select = ui.select(
                            options=[],
                            label="Kolon filtresi",
                        ).classes("w-full dashboard-input")
                        column_filter_input = ui.input(
                            label="Kolon degeri",
                            placeholder="Secilen kolon icinde filtrele",
                        ).props("outlined clearable").classes("w-full dashboard-input")
                    rows_per_page = ui.select(
                        options=[10, 20, 50, 100],
                        value=DEFAULT_ROWS_PER_PAGE,
                        label="Sayfa basina satir",
                    ).classes("w-40 dashboard-input")
                    csv_info = ui.label("").classes("text-sm text-slate-600")
                    csv_table_container = ui.column().classes("w-full")

                def refresh_quick_access() -> None:
                    quick_access_row.clear()
                    with quick_access_row:
                        for quick_file in COMMON_CSV_ORDER:
                            if quick_file not in state["csv_files"]:
                                continue
                            ui.button(
                                Path(quick_file).name,
                                on_click=lambda path=quick_file: csv_select.set_value(path),
                            ).props("outline size=sm")

                def refresh_csv_table() -> None:
                    csv_table_container.clear()
                    selected_value = csv_select.value
                    if not selected_value:
                        csv_info.set_text("Lutfen bir CSV dosyasi secin.")
                        return

                    csv_path = Path(selected_value)
                    if not csv_path.exists():
                        csv_info.set_text(f"Dosya bulunamadi: {selected_value}")
                        return

                    rows, fieldnames = read_csv_rows(csv_path)
                    column_filter_select.options = fieldnames
                    column_filter_select.update()
                    if fieldnames and column_filter_select.value not in fieldnames:
                        column_filter_select.set_value(fieldnames[0])

                    filtered_rows = filter_rows(
                        rows,
                        global_query=global_search.value or "",
                        column_name=column_filter_select.value or "",
                        column_query=column_filter_input.value or "",
                    )
                    preview_rows = filtered_rows[:MAX_PREVIEW_ROWS]

                    csv_info.set_text(
                        f"Dosya: {csv_path.as_posix()} | Toplam satir: {len(rows)} | "
                        f"Filtrelenen: {len(filtered_rows)} | Onizleme: {len(preview_rows)}"
                    )

                    with csv_table_container:
                        if not fieldnames:
                            ui.label("CSV baslik satiri bulunamadi.").classes("text-red-600")
                            return

                        table = ui.table(
                            columns=[
                                {"name": field, "label": field, "field": field, "sortable": True}
                                for field in fieldnames
                            ],
                            rows=preview_rows,
                            row_key="__row_id",
                            pagination={"rowsPerPage": int(rows_per_page.value)},
                        ).classes("w-full")
                        table.on(
                            "rowClick",
                            lambda event, columns=fieldnames: open_row_detail(
                                "Satir Detayi",
                                event.args["row"],
                                columns,
                            ),
                        )

                        if len(filtered_rows) > MAX_PREVIEW_ROWS:
                            ui.label(
                                f"Performans icin ilk {MAX_PREVIEW_ROWS} satir gosteriliyor."
                            ).classes("text-sm text-amber-700")

                csv_select.on_value_change(lambda _: refresh_csv_table())
                global_search.on_value_change(lambda _: refresh_csv_table())
                column_filter_select.on_value_change(lambda _: refresh_csv_table())
                column_filter_input.on_value_change(lambda _: refresh_csv_table())
                rows_per_page.on_value_change(lambda _: refresh_csv_table())
                ui.button("Veri Tablosunu Yenile", on_click=refresh_csv_table).props("outline")

                refresh_quick_access()
                refresh_csv_table()

            with ui.tab_panel(logs_tab):
                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Degisiklik Gecmisi").classes("text-lg font-semibold text-slate-900")
                    log_select = ui.select(
                        options=state["log_files"],
                        value=selected_log,
                        label="Log dosyasi",
                    ).classes("w-full dashboard-input")
                    with ui.row().classes("w-full gap-4"):
                        log_file_filter = ui.input(label="Dosya filtresi").props("outlined clearable").classes("w-full dashboard-input")
                        log_column_filter = ui.input(label="Kolon filtresi").props("outlined clearable").classes("w-full dashboard-input")
                        log_operation_filter = ui.input(label="Senaryo / islem filtresi").props("outlined clearable").classes("w-full dashboard-input")
                    log_info = ui.label("").classes("text-sm text-slate-600")
                    log_table_container = ui.column().classes("w-full")

                def refresh_log_table() -> None:
                    log_table_container.clear()
                    selected_value = log_select.value
                    if not selected_value:
                        log_info.set_text("Lutfen bir log dosyasi secin.")
                        return

                    log_path = Path(selected_value)
                    if not log_path.exists():
                        log_info.set_text(f"Log dosyasi bulunamadi: {selected_value}")
                        return

                    rows, fieldnames = read_log_rows(log_path)
                    filtered_rows = rows

                    if log_file_filter.value:
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if log_file_filter.value.lower() in str(row.get("dosya", "")).lower()
                        ]

                    if log_column_filter.value:
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if log_column_filter.value.lower() in str(row.get("kolon", "")).lower()
                        ]

                    if log_operation_filter.value:
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if any(
                                log_operation_filter.value.lower() in str(row.get(key, "")).lower()
                                for key in ["islem", "dosya", "kolon"]
                            )
                        ]

                    log_info.set_text(
                        f"Log dosyasi: {log_path.as_posix()} | Toplam kayit: {len(rows)} | "
                        f"Filtrelenen: {len(filtered_rows)}"
                    )

                    with log_table_container:
                        if not fieldnames:
                            ui.label("Log kaydi bulunamadi.").classes("text-red-600")
                            return

                        table = ui.table(
                            columns=[
                                {"name": field, "label": field, "field": field, "sortable": True}
                                for field in fieldnames
                            ],
                            rows=filtered_rows[:MAX_PREVIEW_ROWS],
                            row_key="__row_id",
                            pagination={"rowsPerPage": 10},
                        ).classes("w-full")
                        table.on(
                            "rowClick",
                            lambda event, columns=fieldnames: open_row_detail(
                                "Log Kaydi Detayi",
                                event.args["row"],
                                columns,
                            ),
                        )

                log_select.on_value_change(lambda _: refresh_log_table())
                log_file_filter.on_value_change(lambda _: refresh_log_table())
                log_column_filter.on_value_change(lambda _: refresh_log_table())
                log_operation_filter.on_value_change(lambda _: refresh_log_table())
                ui.button("Log Tablosunu Yenile", on_click=refresh_log_table).props("outline")
                refresh_log_table()

            with ui.tab_panel(audit_tab):
                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Denetim Gecmisi").classes("text-lg font-semibold text-slate-900")
                    audit_select = ui.select(
                        options=state["audit_files"],
                        value=selected_audit,
                        label="Audit dosyasi",
                    ).classes("w-full dashboard-input")
                    with ui.row().classes("w-full gap-4"):
                        audit_scenario_filter = ui.input(label="Senaryo filtresi").props("outlined clearable").classes("w-full dashboard-input")
                        audit_status_filter = ui.input(label="Status filtresi").props("outlined clearable").classes("w-full dashboard-input")
                        audit_source_filter = ui.input(label="Kaynak filtresi").props("outlined clearable").classes("w-full dashboard-input")
                    audit_search_filter = ui.input(
                        label="Metin arama",
                        placeholder="message, error veya details icinde ara",
                    ).props("outlined clearable").classes("w-full dashboard-input")
                    audit_info = ui.label("").classes("text-sm text-slate-600")
                    audit_table_container = ui.column().classes("w-full")

                def refresh_audit_table() -> None:
                    audit_table_container.clear()
                    selected_value = audit_select.value
                    if not selected_value:
                        audit_info.set_text("Lutfen bir audit dosyasi secin.")
                        return

                    audit_path = Path(selected_value)
                    if not audit_path.exists():
                        audit_info.set_text(f"Audit dosyasi bulunamadi: {selected_value}")
                        return

                    rows, fieldnames = read_audit_rows(audit_path)
                    filtered_rows = rows

                    if audit_scenario_filter.value:
                        query = str(audit_scenario_filter.value).lower()
                        filtered_rows = [
                            row for row in filtered_rows if query in str(row.get("scenario_name", "")).lower()
                        ]

                    if audit_status_filter.value:
                        query = str(audit_status_filter.value).lower()
                        filtered_rows = [
                            row for row in filtered_rows if query in str(row.get("status", "")).lower()
                        ]

                    if audit_source_filter.value:
                        query = str(audit_source_filter.value).lower()
                        filtered_rows = [
                            row for row in filtered_rows if query in str(row.get("source", "")).lower()
                        ]

                    if audit_search_filter.value:
                        query = str(audit_search_filter.value).lower()
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if query in str(row.get("message", "")).lower()
                            or query in str(row.get("error", "")).lower()
                            or query in str(row.get("details_text", "")).lower()
                        ]

                    audit_info.set_text(
                        f"Audit dosyasi: {audit_path.as_posix()} | Toplam event: {len(rows)} | "
                        f"Filtrelenen: {len(filtered_rows)}"
                    )

                    with audit_table_container:
                        if not fieldnames:
                            ui.label("Audit kaydi bulunamadi.").classes("text-red-600")
                            return

                        table = ui.table(
                            columns=[
                                {"name": field, "label": field, "field": field, "sortable": True}
                                for field in fieldnames
                            ],
                            rows=filtered_rows[:MAX_PREVIEW_ROWS],
                            row_key="__row_id",
                            pagination={"rowsPerPage": 12},
                        ).classes("w-full")
                        table.on(
                            "rowClick",
                            lambda event, columns=fieldnames: open_row_detail(
                                "Audit Event Detayi",
                                event.args["row"],
                                columns,
                            ),
                        )

                        if len(filtered_rows) > MAX_PREVIEW_ROWS:
                            ui.label(
                                f"Performans icin ilk {MAX_PREVIEW_ROWS} event gosteriliyor."
                            ).classes("text-sm text-amber-700")

                audit_select.on_value_change(lambda _: refresh_audit_table())
                audit_scenario_filter.on_value_change(lambda _: refresh_audit_table())
                audit_status_filter.on_value_change(lambda _: refresh_audit_table())
                audit_source_filter.on_value_change(lambda _: refresh_audit_table())
                audit_search_filter.on_value_change(lambda _: refresh_audit_table())
                ui.button("Audit Tablosunu Yenile", on_click=refresh_audit_table).props("outline")
                refresh_audit_table()

            with ui.tab_panel(scenarios_tab):
                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Kayitli Senaryolar").classes("text-lg font-semibold text-slate-900")
                    scenarios_grid = ui.row().classes("w-full gap-4")
                    scenario_select = ui.select(
                        options=state["scenario_files"],
                        value=selected_scenario,
                        label="Senaryo sec",
                    ).classes("w-full dashboard-input")
                    scenario_summary = ui.label("").classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4 items-stretch"):
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Senaryo Adi").classes("text-sm text-slate-500")
                            scenario_summary_name = ui.label("-").classes("text-lg font-medium")
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Degisiklik Sayisi").classes("text-sm text-slate-500")
                            scenario_summary_change_count = ui.label("0").classes("text-3xl font-bold")
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Veri Seti").classes("text-sm text-slate-500")
                            scenario_summary_dataset = ui.label("-").classes("text-lg font-medium")
                    scenario_detail = ui.label("").classes("hidden")
                    scenario_change_summary = ui.label("").classes("hidden")
                    recent_scenarios = ui.markdown("").classes("w-full text-sm")
                    with ui.row().classes("gap-2"):
                        open_output_button = ui.button("Cikti Veri Dosyasini Goster").props("outline")
                        open_log_button = ui.button("Cikti Log Dosyasini Goster").props("outline")
                        run_button = ui.button("Sadece Hazirlik Akisini Baslat").props("color=primary")
                    ui.label(
                        "Bu buton sadece hazirlik yapar; comparison raporu ve analiz grafikleri olusturmaz."
                    ).classes("text-xs text-slate-500")

                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Senaryo Yonetimi").classes("text-lg font-semibold text-slate-900")
                    ui.label(
                        "Secili senaryoyu kopyalayin, yeniden adlandirin ve ilgili versiyonlari tek yerde takip edin."
                    ).classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4 items-end"):
                        scenario_copy_name_input = ui.input(
                            label="Kopya Senaryo Adi",
                            placeholder="ornek: materials_option_b",
                        ).classes("w-full dashboard-input")
                        copy_scenario_button = ui.button("Senaryoyu Kopyala").props("color=primary")
                        scenario_rename_name_input = ui.input(
                            label="Yeni Senaryo Adi",
                            placeholder="ornek: materials_final",
                        ).classes("w-full dashboard-input")
                        rename_scenario_button = ui.button("Yeniden Adlandir").props("outline color=primary")
                        backfill_scenarios_button = ui.button("Eski Senaryolari Guncelle").props("outline")
                    management_info = ui.label(
                        "Generated senaryolar dogrudan yeniden adlandirilir; sabit tanimlar korunarak generated klasorune yeni surum olarak yazilir."
                    ).classes("text-xs text-slate-500")
                    with ui.row().classes("w-full gap-4 items-stretch"):
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Versiyon Gecmisi").classes("text-sm text-slate-500")
                            scenario_version_history = ui.markdown(
                                "Bir senaryo sectiginizde versiyon zinciri burada gorunecek."
                            ).classes("w-full text-sm")
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Yonetim Notu").classes("text-sm text-slate-500")
                            scenario_management_note = ui.markdown(
                                "Kopyalama ve yeniden adlandirma olaylari secili senaryonun metadata gecmisine eklenir."
                            ).classes("w-full text-sm")

                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Senaryo Fark Gorunumu").classes("text-lg font-semibold text-slate-900")
                    ui.label(
                        "Secili senaryoyu iki farkli alternatif ile ayni anda karsilastirin."
                    ).classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4 items-end"):
                        scenario_compare_select = ui.select(
                            options=state["scenario_files"],
                            label="2. senaryoyu sec",
                        ).classes("w-full dashboard-input")
                        scenario_compare_third_select = ui.select(
                            options=state["scenario_files"],
                            label="3. senaryoyu sec",
                        ).classes("w-full dashboard-input")
                    with ui.row().classes("w-full gap-4 items-stretch"):
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Sol Senaryo").classes("text-sm text-slate-500")
                            scenario_compare_left = ui.markdown("Sol panel secili senaryoyu bekliyor.").classes(
                                "w-full text-sm"
                            )
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Sag Senaryo").classes("text-sm text-slate-500")
                            scenario_compare_right = ui.markdown("Sag panel icin ikinci senaryoyu secin.").classes(
                                "w-full text-sm"
                            )
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("3. Senaryo").classes("text-sm text-slate-500")
                            scenario_compare_third = ui.markdown("Ucuncu senaryo istege bagli olarak secilebilir.").classes(
                                "w-full text-sm"
                            )
                    ui.label("Karar Puan Kartlari").classes("text-sm font-medium text-slate-700")
                    scenario_score_cards = ui.row().classes("w-full gap-4 items-stretch")
                    scenario_compare_commentary = ui.markdown(
                        "Otomatik yorum kutusu secimlerden sonra burada gosterilecek."
                    ).classes("w-full text-sm")
                    scenario_compare_chart = ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["Degisiklik", "Islem"], "top": 8},
                            "grid": {"left": 56, "right": 24, "top": 64, "bottom": 60, "containLabel": True},
                            "xAxis": {"type": "category", "data": []},
                            "yAxis": {"type": "value"},
                            "series": [
                                {"name": "Degisiklik", "type": "bar", "data": [], "itemStyle": {"color": "#2563eb"}},
                                {"name": "Islem", "type": "bar", "data": [], "itemStyle": {"color": "#f59e0b"}},
                            ],
                        }
                    ).classes("w-full h-72")
                    scenario_diff_markdown = ui.markdown(
                        "Karsilastirma ozeti secimlerden sonra burada gosterilecek."
                    ).classes("w-full text-sm")
                    with ui.row().classes("w-full gap-4 items-stretch"):
                        with ui.card().classes("w-full dashboard-summary-card bg-emerald-50"):
                            ui.label("Ayni Alan").classes("text-sm text-emerald-700")
                            scenario_diff_same_count = ui.label("0").classes(
                                "text-3xl font-bold text-emerald-700"
                            )
                        with ui.card().classes("w-full dashboard-summary-card bg-amber-50"):
                            ui.label("Farkli Alan").classes("text-sm text-amber-700")
                            scenario_diff_changed_count = ui.label("0").classes(
                                "text-3xl font-bold text-amber-700"
                            )
                    scenario_diff_table_hint = ui.label(
                        "Secimlerden sonra detayli fark tablosu burada gosterilecek."
                    ).classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4 items-end"):
                        scenario_compare_mode = ui.select(
                            options=["Detayli Karsilastirma", "Ozet Fark Modu"],
                            value="Detayli Karsilastirma",
                            label="Karsilastirma modu",
                        ).classes("w-64 dashboard-input")
                        scenario_diff_filter = ui.select(
                            options=["Tum Satirlar", "Sadece Farklilar", "Sadece Aynilar"],
                            value="Tum Satirlar",
                            label="Fark filtresi",
                        ).classes("w-64 dashboard-input")
                        export_scenario_diff_button = ui.button("Farklari CSV Olarak Kaydet").props("outline")
                    scenario_diff_table = ui.table(
                        columns=[
                            {"name": "label", "label": "Alan", "field": "label", "align": "left"},
                            {"name": "left", "label": "Sol", "field": "left", "align": "left"},
                            {"name": "right", "label": "Sag", "field": "right", "align": "left"},
                            {"name": "third", "label": "3. Senaryo", "field": "third", "align": "left"},
                            {"name": "status", "label": "Durum", "field": "status", "align": "left"},
                        ],
                        rows=[],
                        row_key="label",
                        pagination={"rowsPerPage": 8},
                    ).classes("w-full")
                    scenario_diff_table.add_slot(
                        "body-cell-status",
                        r'''
                        <q-td :props="props">
                          <q-badge
                            :color="props.value === 'Ayni' ? 'positive' : 'warning'"
                            :label="props.value"
                          />
                        </q-td>
                        ''',
                    )

                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Degisim Ozeti").classes("text-lg font-semibold text-slate-900")
                    summary_hint = ui.label(
                        "Detay listeye girmeden once degisikligin genel etkisi burada gorunecek."
                    ).classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4 items-stretch"):
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Degisen Ana Alan").classes("text-sm text-slate-500")
                            changed_field_value = ui.label("-").classes("text-lg font-medium")
                        with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                            ui.label("Toplam Etkilenen Satir").classes("text-sm text-slate-500")
                            total_impact_value = ui.label("0").classes("text-3xl font-bold")
                        with ui.card().classes("w-full dashboard-summary-card bg-emerald-50"):
                            ui.label("Dogrudan Etki").classes("text-sm text-emerald-700")
                            direct_impact_value = ui.label("0").classes("text-3xl font-bold text-emerald-700")
                        with ui.card().classes("w-full dashboard-summary-card bg-amber-50"):
                            ui.label("Dolayli Etki").classes("text-sm text-amber-700")
                            indirect_impact_value = ui.label("0").classes("text-3xl font-bold text-amber-700")
                    critical_impact_banner = ui.label(
                        "Kritik etki bilgisi burada gosterilecek."
                    ).classes("w-full rounded-md px-3 py-2 text-sm bg-slate-100 text-slate-700")

                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Etkilenen Alanlar").classes("text-lg font-semibold text-slate-900")
                    impact_summary = ui.label(
                        "Bir senaryo sectiginizde etkilenen alanlar burada listelenecek."
                    ).classes("text-sm text-slate-600")
                    impact_error = ui.label("").classes("text-sm text-red-600")
                    with ui.row().classes("w-full gap-4 items-end"):
                        impact_search_input = ui.input(
                            label="Etki icinde ara",
                            placeholder="Alan, veri seti veya kaynak ara",
                        ).props("outlined clearable").classes("w-full dashboard-input")
                        impact_type_filter = ui.select(
                            options=["Tum Etkiler", "Sadece Dogrudan", "Sadece Dolayli"],
                            value="Tum Etkiler",
                            label="Etki tipi",
                        ).classes("w-56 dashboard-input")
                        impact_sort_select = ui.select(
                            options=["Varsayilan", "En Buyuk Degisim", "En Fazla Etki"],
                            value="Varsayilan",
                            label="Siralama",
                        ).classes("w-56 dashboard-input")
                        clear_impact_filters_button = ui.button("Filtreleri Temizle").props("outline")
                    impact_table_container = ui.column().classes("w-full")

                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Grafik Onizleme").classes("text-lg font-semibold text-slate-900")
                    impact_chart_info = ui.label(
                        "Grafik altyapisi secili senaryonun etki verisiyle beslenecek."
                    ).classes("text-sm text-slate-600")
                    change_comparison_chart = ui.echart(
                        {
                            "tooltip": {
                                "trigger": "axis",
                            },
                            "legend": {"data": ["Eski Deger", "Yeni Deger", "Ana Degisim"], "top": 8},
                            "grid": {"left": 56, "right": 24, "top": 64, "bottom": 110, "containLabel": True},
                            "xAxis": {
                                "type": "category",
                                "data": [],
                                "axisLabel": {"interval": 0, "rotate": 12, "fontSize": 11},
                            },
                            "yAxis": {"type": "value"},
                            "series": [
                                {"name": "Eski Deger", "type": "bar", "data": []},
                                {"name": "Yeni Deger", "type": "bar", "data": []},
                                {
                                    "name": "Ana Degisim",
                                    "type": "scatter",
                                    "symbolSize": 18,
                                    "data": [],
                                    "itemStyle": {"color": "#dc2626"},
                                    "z": 5,
                                },
                            ],
                        }
                    ).classes("w-full h-[26rem]")
                    impact_distribution_chart = ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["Dogrudan", "Dolayli"], "top": 8},
                            "grid": {"left": 56, "right": 24, "top": 64, "bottom": 90, "containLabel": True},
                            "xAxis": {
                                "type": "category",
                                "data": [],
                                "axisLabel": {"interval": 0, "rotate": 10, "fontSize": 11},
                            },
                            "yAxis": {"type": "value"},
                            "series": [
                                {
                                    "name": "Dogrudan",
                                    "type": "bar",
                                    "stack": "etki",
                                    "data": [],
                                    "itemStyle": {"color": "#059669"},
                                },
                                {
                                    "name": "Dolayli",
                                    "type": "bar",
                                    "stack": "etki",
                                    "data": [],
                                    "itemStyle": {"color": "#d97706"},
                                },
                            ],
                        }
                    ).classes("w-full h-80")
                    relation_graph = ui.echart(
                        {
                            "tooltip": {
                                "trigger": "item",
                            },
                            "legend": [
                                {
                                    "data": ["Ana Degisim", "Dogrudan Etki", "Dolayli Etki"],
                                    "top": 0,
                                }
                            ],
                            "series": [
                                {
                                    "type": "graph",
                                    "layout": "force",
                                    "roam": True,
                                    "label": {"show": True, "formatter": "{b}", "fontSize": 11},
                                    "force": {"repulsion": 320, "edgeLength": 170, "gravity": 0.06},
                                    "draggable": True,
                                    "categories": [],
                                    "data": [],
                                    "links": [],
                                    "lineStyle": {"opacity": 0.65, "width": 2},
                                    "emphasis": {"focus": "adjacency"},
                                }
                            ],
                        }
                    ).classes("w-full h-96")
                    impact_transition_charts_container = ui.column().classes("w-full gap-4")

                def refresh_state_sources() -> None:
                    state["csv_files"] = [path.as_posix() for path in collect_csv_files()]
                    state["log_files"] = [path.as_posix() for path in collect_log_files()]
                    state["scenario_files"] = [path.as_posix() for path in collect_scenario_files()]
                    state["audit_files"] = [path.as_posix() for path in collect_audit_files()]

                    csv_select.options = state["csv_files"]
                    csv_select.update()
                    log_select.options = state["log_files"]
                    log_select.update()
                    scenario_select.options = state["scenario_files"]
                    scenario_select.update()
                    scenario_compare_select.options = state["scenario_files"]
                    scenario_compare_select.update()
                    audit_select.options = state["audit_files"]
                    audit_select.update()

                    if csv_select.value not in state["csv_files"] and state["csv_files"]:
                        csv_select.set_value(get_initial_csv(state["csv_files"]))
                    if log_select.value not in state["log_files"] and state["log_files"]:
                        log_select.set_value(get_initial_log(state["log_files"]))
                    if scenario_select.value not in state["scenario_files"] and state["scenario_files"]:
                        scenario_select.set_value(get_initial_scenario(state["scenario_files"]))
                    if audit_select.value not in state["audit_files"] and state["audit_files"]:
                        audit_select.set_value(get_initial_audit(state["audit_files"]))

                    refresh_quick_access()
                    refresh_scenario_cards()
                    refresh_recent_scenarios()
                    refresh_scenario_management_views()
                    refresh_audit_table()

                def focus_output_file() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        ui.notify("Lutfen once bir senaryo secin.", color="warning")
                        return

                    output_path, _, _ = scenario_output_targets(Path(selected_value))
                    normalized = output_path.as_posix()
                    if normalized not in state["csv_files"]:
                        ui.notify("Senaryo cikti veri dosyasi henuz uretilmedi.", color="warning")
                        return

                    csv_select.set_value(normalized)
                    refresh_csv_table()
                    ui.notify("Senaryo cikti veri dosyasi acildi.", color="positive")

                def focus_log_file() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        ui.notify("Lutfen once bir senaryo secin.", color="warning")
                        return

                    _, log_path, _ = scenario_output_targets(Path(selected_value))
                    normalized = log_path.as_posix()
                    if normalized not in state["log_files"]:
                        ui.notify("Senaryo cikti log dosyasi henuz uretilmedi.", color="warning")
                        return

                    log_select.set_value(normalized)
                    refresh_log_table()
                    ui.notify("Senaryo log dosyasi acildi.", color="positive")

                def run_scenario_preparation() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        ui.notify("Lutfen once bir senaryo secin.", color="warning")
                        return

                    try:
                        preparation_result = prepare_scenario_from_definition(
                            Path(selected_value),
                            SIMULATION_OUTPUT_DIR,
                        )

                        ui.notify(
                            f"Senaryo hazirlik paketi olusturuldu: {preparation_result.scenario_name}",
                            color="positive",
                        )
                        refresh_state_sources()
                        refresh_metrics()
                        csv_select.set_value(preparation_result.output_path.as_posix())
                        log_select.set_value(preparation_result.log_output_path.as_posix())
                        refresh_csv_table()
                        refresh_log_table()
                        refresh_impact_table()
                    except CsvUpdateError as error:
                        ui.notify(f"Hata: {error}", color="negative")

                def select_scenario(file_path: str) -> None:
                    scenario_select.set_value(file_path)

                def open_scenario_output(file_path: str) -> None:
                    scenario_select.set_value(file_path)
                    focus_output_file()

                def open_scenario_log(file_path: str) -> None:
                    scenario_select.set_value(file_path)
                    focus_log_file()

                def run_scenario_from_card(file_path: str) -> None:
                    scenario_select.set_value(file_path)
                    run_scenario_preparation()

                def is_generated_scenario_path(path: Path) -> bool:
                    return "generated" in {part.lower() for part in path.parts}

                def build_generated_scenario_target_path(scenario_name: str) -> Path:
                    normalized_name = sanitize_scenario_name(scenario_name)
                    return SCENARIO_DIR / "generated" / f"{normalized_name}.json"

                def write_scenario_definition_file(path: Path, scenario: dict[str, object]) -> Path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    scenario_with_metadata = ensure_management_metadata(scenario, path.as_posix())
                    if isinstance(scenario_with_metadata.get("management"), dict):
                        scenario_with_metadata["management"]["scenario_path"] = path.as_posix()
                    with path.open("w", encoding="utf-8") as file:
                        json.dump(scenario_with_metadata, file, ensure_ascii=False, indent=2)
                    return path

                def load_scenario_summary_entries() -> list[dict[str, object]]:
                    entries: list[dict[str, object]] = []
                    for scenario_file in state["scenario_files"]:
                        scenario_path = Path(scenario_file)
                        try:
                            scenario = read_json_file(scenario_path)
                        except Exception:
                            continue
                        if not isinstance(scenario, dict):
                            continue
                        management = scenario.get("management", {})
                        if not isinstance(management, dict):
                            management = {}
                        entries.append(
                            {
                                "path": scenario_path.as_posix(),
                                "scenario_name": str(scenario.get("scenario_name", scenario_path.stem)),
                                "input": str(scenario.get("input", "-")),
                                "change_count": len(scenario.get("changes", [])),
                                "operation_count": len(scenario.get("operations", [])),
                                "management": management,
                                "mtime_label": datetime.fromtimestamp(
                                    scenario_path.stat().st_mtime
                                ).strftime("%Y-%m-%d %H:%M"),
                            }
                        )
                    return entries

                def format_scenario_preview_markdown(
                    scenario_path: Path | None,
                    scenario: dict[str, object] | None,
                ) -> str:
                    if scenario_path is None or not isinstance(scenario, dict):
                        return "Secim yapildiginda senaryo ozeti burada gorunecek."
                    return "\n".join(
                        [
                            f"**{scenario.get('scenario_name', scenario_path.stem)}**",
                            f"- Veri seti: `{str(scenario.get('input', '-')).replace('csv_output/', '')}`",
                            f"- Degisiklik sayisi: {len(scenario.get('changes', []))}",
                            f"- Islem sayisi: {len(scenario.get('operations', []))}",
                            f"- Dosya: `{scenario_path.as_posix()}`",
                        ]
                    )

                scenario_diff_export_rows: list[dict[str, str]] = []

                def build_scenario_diff_export_path(left_name: str, right_name: str) -> Path:
                    export_dir = SCENARIO_DIR / "generated" / "exports"
                    export_dir.mkdir(parents=True, exist_ok=True)
                    timestamp_label = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = (
                        f"scenario_diff__{sanitize_scenario_name(left_name)}__"
                        f"{sanitize_scenario_name(right_name)}__{timestamp_label}.csv"
                    )
                    return export_dir / file_name

                def export_scenario_diff_rows() -> None:
                    rows = list(scenario_diff_export_rows)
                    if not rows:
                        ui.notify("Disa aktarmak icin once karsilastirma olusturun.", color="warning")
                        return

                    left_name = "left"
                    right_name = "right"
                    left_value = str(scenario_select.value or "").strip()
                    right_value = str(scenario_compare_select.value or "").strip()
                    if left_value:
                        left_path = Path(left_value)
                        left_name = left_path.stem
                    if right_value:
                        right_path = Path(right_value)
                        right_name = right_path.stem

                    export_path = build_scenario_diff_export_path(left_name, right_name)
                    with export_path.open("w", encoding="utf-8-sig", newline="") as file:
                        writer = csv.DictWriter(
                            file,
                            fieldnames=["label", "left", "right", "third", "status"],
                        )
                        writer.writeheader()
                        writer.writerows(rows)

                    ui.notify(
                        f"Senaryo farklari CSV olarak kaydedildi: {export_path.as_posix()}",
                        color="positive",
                    )

                def refresh_scenario_management_views() -> None:
                    selected_value = str(scenario_select.value or "").strip()
                    scenario_entries = load_scenario_summary_entries()

                    def render_scenario_score_cards(score_rows: list[dict[str, object]]) -> None:
                        def score_color(score: object) -> str:
                            try:
                                numeric = float(score)
                            except (TypeError, ValueError):
                                return "#94a3b8"
                            if numeric >= 8:
                                return "#059669"
                            if numeric >= 6:
                                return "#0284c7"
                            if numeric >= 4:
                                return "#d97706"
                            return "#dc2626"

                        def progress_value(score: object) -> float:
                            try:
                                numeric = float(score)
                            except (TypeError, ValueError):
                                return 0.0
                            return max(0.0, min(1.0, numeric / 10.0))

                        scenario_score_cards.clear()
                        with scenario_score_cards:
                            if not score_rows:
                                with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                                    ui.label("Skor kartlari icin comparison verisi bekleniyor.").classes(
                                        "text-sm text-slate-500"
                                    )
                                return

                            for score_row in score_rows[:3]:
                                scenario_name = str(score_row.get("scenario_name", "-"))
                                energy_score = score_row.get("energy_score")
                                cost_score = score_row.get("cost_score")
                                risk_score = score_row.get("risk_score")
                                total_score = score_row.get("total_score")
                                risk_label = str(score_row.get("risk_label", "-"))
                                rank_index = score_rows.index(score_row) + 1
                                if rank_index == 1:
                                    rank_label = "1. En Iyi"
                                    rank_color = "#059669"
                                elif rank_index == 2:
                                    rank_label = "2. Sirada"
                                    rank_color = "#0284c7"
                                else:
                                    rank_label = "3. Sirada"
                                    rank_color = "#d97706"
                                with ui.card().classes("w-full dashboard-summary-card bg-slate-50"):
                                    with ui.row().classes("w-full items-center justify-between gap-3"):
                                        ui.label(scenario_name).classes("text-base font-semibold text-slate-900")
                                        ui.badge(rank_label).style(
                                            f"background-color: {rank_color}; color: white;"
                                        )
                                    ui.label(
                                        f"Toplam Puan: {total_score if total_score is not None else '-'} / 10"
                                    ).style(f"color: {score_color(total_score)}").classes("text-lg font-bold")
                                    ui.linear_progress(
                                        value=progress_value(total_score),
                                        color=score_color(total_score),
                                    ).props("rounded stripe").classes("w-full")
                                    with ui.column().classes("w-full gap-2 pt-2"):
                                        with ui.row().classes("w-full items-center justify-between gap-3"):
                                            ui.label(
                                                f"Enerji: {energy_score if energy_score is not None else '-'}"
                                            ).classes("text-sm text-slate-600")
                                            ui.linear_progress(
                                                value=progress_value(energy_score),
                                                color=score_color(energy_score),
                                            ).props("rounded").classes("flex-1")
                                        with ui.row().classes("w-full items-center justify-between gap-3"):
                                            ui.label(
                                                f"Maliyet: {cost_score if cost_score is not None else '-'}"
                                            ).classes("text-sm text-slate-600")
                                            ui.linear_progress(
                                                value=progress_value(cost_score),
                                                color=score_color(cost_score),
                                            ).props("rounded").classes("flex-1")
                                        with ui.row().classes("w-full items-center justify-between gap-3"):
                                            ui.label(
                                                f"Risk: {risk_score if risk_score is not None else '-'} ({risk_label})"
                                            ).classes("text-sm text-slate-600")
                                            ui.linear_progress(
                                                value=progress_value(risk_score),
                                                color=score_color(risk_score),
                                            ).props("rounded").classes("flex-1")

                    compare_options = {
                        str(item.get("path", "")): str(item.get("scenario_name", "-"))
                        for item in scenario_entries
                    }
                    scenario_compare_select.options = compare_options
                    scenario_compare_select.update()
                    scenario_compare_third_select.options = compare_options
                    scenario_compare_third_select.update()
                    if state["scenario_files"] and scenario_compare_select.value not in state["scenario_files"]:
                        fallback_value = next(
                            (item for item in state["scenario_files"] if item != selected_value),
                            state["scenario_files"][0],
                        )
                        scenario_compare_select.set_value(fallback_value)
                    if state["scenario_files"] and scenario_compare_third_select.value not in state["scenario_files"]:
                        remaining_values = [
                            item
                            for item in state["scenario_files"]
                            if item not in {selected_value, str(scenario_compare_select.value or "").strip()}
                        ]
                        scenario_compare_third_select.set_value(remaining_values[0] if remaining_values else "")

                    if not selected_value:
                        scenario_version_history.set_content(
                            "Bir senaryo sectiginizde versiyon zinciri burada gorunecek."
                        )
                        scenario_management_note.set_content(
                            "Kopyalama ve yeniden adlandirma olaylari secili senaryonun metadata gecmisine eklenir."
                        )
                        scenario_compare_left.set_content("Sol panel secili senaryoyu bekliyor.")
                        scenario_compare_right.set_content("Sag panel icin ikinci senaryoyu secin.")
                        scenario_compare_third.set_content("Ucuncu senaryo istege bagli olarak secilebilir.")
                        scenario_compare_commentary.set_content(
                            "Otomatik yorum kutusu secimlerden sonra burada gosterilecek."
                        )
                        render_scenario_score_cards([])
                        scenario_compare_chart.options["xAxis"]["data"] = []
                        scenario_compare_chart.options["series"][0]["data"] = []
                        scenario_compare_chart.options["series"][1]["data"] = []
                        scenario_compare_chart.update()
                        scenario_diff_markdown.set_content(
                            "Karsilastirma ozeti secimlerden sonra burada gosterilecek."
                        )
                        scenario_diff_same_count.set_text("0")
                        scenario_diff_changed_count.set_text("0")
                        scenario_diff_table_hint.set_text(
                            "Secimlerden sonra detayli fark tablosu burada gosterilecek."
                        )
                        scenario_compare_mode.set_value("Detayli Karsilastirma")
                        scenario_diff_filter.set_value("Tum Satirlar")
                        scenario_diff_export_rows.clear()
                        scenario_diff_table.rows = []
                        scenario_diff_table.update()
                        return

                    selected_path = Path(selected_value)
                    try:
                        selected_scenario = read_json_file(selected_path) if selected_path.exists() else None
                    except Exception:
                        selected_scenario = None
                    compare_value = str(scenario_compare_select.value or "").strip()
                    compare_path = Path(compare_value) if compare_value else None
                    try:
                        compare_scenario = (
                            read_json_file(compare_path)
                            if compare_path is not None and compare_path.exists()
                            else None
                        )
                    except Exception:
                        compare_scenario = None
                    third_value = str(scenario_compare_third_select.value or "").strip()
                    if third_value in {selected_value, compare_value}:
                        third_value = ""
                    third_path = Path(third_value) if third_value else None
                    try:
                        third_scenario = (
                            read_json_file(third_path) if third_path is not None and third_path.exists() else None
                        )
                    except Exception:
                        third_scenario = None

                    history_entries = build_version_history_entries(scenario_entries, selected_value)
                    if history_entries:
                        scenario_version_history.set_content(
                            "\n".join(
                                [
                                    f"- v{entry.get('version_index', 1)} | **{entry.get('scenario_name', '-')}** | "
                                    f"{entry.get('updated_at', '-')} {'(secili)' if entry.get('is_selected') else ''}"
                                    for entry in history_entries
                                ]
                            )
                        )
                    else:
                        scenario_version_history.set_content("Bu senaryo icin ayri bir versiyon zinciri bulunamadi.")

                    management = selected_scenario.get("management", {}) if isinstance(selected_scenario, dict) else {}
                    history = management.get("history", []) if isinstance(management, dict) else []
                    if isinstance(history, list) and history:
                        scenario_management_note.set_content(
                            "\n".join(
                                [
                                    f"- {str(item.get('timestamp', '-'))}: `{str(item.get('event', '-'))}`"
                                    + (
                                        f" | onceki: {item.get('previous_scenario_name')}"
                                        if item.get("previous_scenario_name")
                                        else ""
                                    )
                                    + (
                                        f" | kaynak: {item.get('source_scenario_name')}"
                                        if item.get("source_scenario_name")
                                        else ""
                                    )
                                    for item in history[-5:]
                                ]
                            )
                        )
                    else:
                        scenario_management_note.set_content(
                            "Bu senaryoda henuz kayitli yonetim olayi bulunmuyor."
                        )

                    scenario_compare_left.set_content(
                        format_scenario_preview_markdown(selected_path, selected_scenario)
                    )
                    scenario_compare_right.set_content(
                        format_scenario_preview_markdown(compare_path, compare_scenario)
                    )
                    scenario_compare_third.set_content(
                        format_scenario_preview_markdown(third_path, third_scenario)
                        if third_scenario is not None
                        else "Ucuncu senaryo secilmediyse bu alan bos kalir."
                    )

                    active_scenarios = [
                        (
                            str(selected_scenario.get("scenario_name", selected_path.stem))
                            if isinstance(selected_scenario, dict)
                            else selected_path.stem,
                            selected_scenario,
                        ),
                        (
                            str(compare_scenario.get("scenario_name", compare_path.stem))
                            if isinstance(compare_scenario, dict) and compare_path is not None
                            else (compare_path.stem if compare_path is not None else "2. senaryo"),
                            compare_scenario,
                        ),
                    ]
                    if third_scenario is not None and third_path is not None:
                        active_scenarios.append(
                            (
                                str(third_scenario.get("scenario_name", third_path.stem)),
                                third_scenario,
                            )
                        )

                    comparison_reports_by_name = {
                        str(item.get("scenario_name", "")).strip(): item
                        for item in read_comparison_report_entries()
                        if str(item.get("scenario_name", "")).strip()
                    }
                    render_scenario_score_cards(
                        build_multi_scenario_score_rows(
                            active_scenarios,
                            reports_by_name=comparison_reports_by_name,
                        )
                    )
                    scenario_compare_commentary.set_content(
                        build_multi_scenario_decision_commentary(
                            active_scenarios,
                            reports_by_name=comparison_reports_by_name,
                        )
                    )
                    chart_model = build_multi_scenario_chart_model(active_scenarios)
                    scenario_compare_chart.options["xAxis"]["data"] = chart_model["labels"]
                    scenario_compare_chart.options["series"][0]["data"] = chart_model["change_counts"]
                    scenario_compare_chart.options["series"][1]["data"] = chart_model["operation_counts"]
                    scenario_compare_chart.update()

                    diff_rows = build_multi_scenario_comparison_rows(
                        selected_scenario,
                        compare_scenario,
                        third_scenario,
                    )
                    if diff_rows:
                        same_count = sum(1 for row in diff_rows if row.get("status") == "Ayni")
                        changed_count = sum(1 for row in diff_rows if row.get("status") != "Ayni")
                        scenario_diff_same_count.set_text(str(same_count))
                        scenario_diff_changed_count.set_text(str(changed_count))
                        selected_filter = str(scenario_diff_filter.value or "Tum Satirlar")
                        comparison_mode = str(scenario_compare_mode.value or "Detayli Karsilastirma")
                        filtered_diff_rows = filter_multi_scenario_comparison_rows(
                            diff_rows,
                            selected_filter,
                            comparison_mode,
                        )
                        scenario_diff_table_hint.set_text(
                            "Ayni ve farkli alanlar asagidaki tabloda satir bazinda listeleniyor."
                            if comparison_mode == "Detayli Karsilastirma" and selected_filter == "Tum Satirlar"
                            else f"{comparison_mode} / {selected_filter} aktif."
                        )
                        scenario_diff_export_rows[:] = filtered_diff_rows
                        scenario_diff_table.rows = filtered_diff_rows
                        scenario_diff_table.update()
                        scenario_diff_markdown.set_content(
                            "\n".join(
                                [
                                    f"- **{row['label']}** | Sol: {row['left']} | Sag: {row['right']} | "
                                    f"3. Senaryo: {row.get('third', '-')} | Durum: {row['status']}"
                                    for row in filtered_diff_rows
                                ]
                            )
                        )
                    else:
                        scenario_diff_same_count.set_text("0")
                        scenario_diff_changed_count.set_text("0")
                        scenario_diff_table_hint.set_text(
                            "Detayli fark tablosu icin en az iki senaryo secin."
                        )
                        scenario_diff_export_rows.clear()
                        scenario_diff_table.rows = []
                        scenario_diff_table.update()
                        scenario_diff_markdown.set_content(
                            "Karsilastirma icin secili senaryonun yanina en az bir alternatif senaryo secin."
                        )

                def copy_selected_scenario() -> None:
                    selected_value = str(scenario_select.value or "").strip()
                    if not selected_value:
                        ui.notify("Kopyalamadan once bir senaryo secin.", color="warning")
                        return

                    raw_new_name = str(scenario_copy_name_input.value or "").strip()
                    if not raw_new_name:
                        ui.notify("Kopya icin gecerli bir senaryo adi girin.", color="warning")
                        return
                    new_name = sanitize_scenario_name(raw_new_name)

                    target_path = build_generated_scenario_target_path(new_name)
                    if target_path.exists():
                        ui.notify("Bu adla bir senaryo zaten var.", color="negative")
                        return

                    source_path = Path(selected_value)
                    scenario = read_json_file(source_path)
                    if not isinstance(scenario, dict):
                        ui.notify("Secili senaryo okunamadi.", color="negative")
                        return

                    copied = build_copied_scenario_definition(scenario, source_path.as_posix(), new_name)
                    write_scenario_definition_file(target_path, copied)
                    refresh_state_sources()
                    scenario_select.set_value(target_path.as_posix())
                    scenario_copy_name_input.set_value("")
                    refresh_scenario_detail()
                    refresh_scenario_management_views()
                    ui.notify(f"Senaryo kopyalandi: {new_name}", color="positive")

                def rename_selected_scenario() -> None:
                    selected_value = str(scenario_select.value or "").strip()
                    if not selected_value:
                        ui.notify("Yeniden adlandirmadan once bir senaryo secin.", color="warning")
                        return

                    raw_new_name = str(scenario_rename_name_input.value or "").strip()
                    if not raw_new_name:
                        ui.notify("Yeni senaryo adini girin.", color="warning")
                        return
                    new_name = sanitize_scenario_name(raw_new_name)

                    source_path = Path(selected_value)
                    if not source_path.exists():
                        ui.notify("Secili senaryo dosyasi bulunamadi.", color="negative")
                        return

                    scenario = read_json_file(source_path)
                    if not isinstance(scenario, dict):
                        ui.notify("Secili senaryo okunamadi.", color="negative")
                        return

                    target_path = build_generated_scenario_target_path(new_name)
                    if target_path.exists() and target_path.as_posix() != source_path.as_posix():
                        ui.notify("Bu adla bir senaryo zaten var.", color="negative")
                        return

                    renamed = build_renamed_scenario_definition(scenario, source_path.as_posix(), new_name)
                    if is_generated_scenario_path(source_path):
                        write_scenario_definition_file(target_path, renamed)
                        if target_path.as_posix() != source_path.as_posix() and source_path.exists():
                            source_path.unlink()
                        ui.notify(f"Senaryo yeniden adlandirildi: {new_name}", color="positive")
                    else:
                        write_scenario_definition_file(target_path, renamed)
                        ui.notify(
                            "Sabit senaryo korunarak generated klasorune yeni adla surum yazildi.",
                            color="positive",
                        )

                    refresh_state_sources()
                    scenario_select.set_value(target_path.as_posix())
                    scenario_rename_name_input.set_value("")
                    refresh_scenario_detail()
                    refresh_scenario_management_views()

                def backfill_existing_scenario_metadata() -> None:
                    updated_count = 0
                    failed_count = 0
                    for scenario_file in list(state["scenario_files"]):
                        scenario_path = Path(scenario_file)
                        if not scenario_path.exists():
                            continue
                        try:
                            scenario = read_json_file(scenario_path)
                        except Exception:
                            failed_count += 1
                            continue
                        if not isinstance(scenario, dict):
                            failed_count += 1
                            continue

                        existing_management = scenario.get("management", {})
                        if isinstance(existing_management, dict) and existing_management.get("version_group"):
                            continue

                        try:
                            write_scenario_definition_file(scenario_path, scenario)
                            updated_count += 1
                        except Exception:
                            failed_count += 1

                    refresh_state_sources()
                    refresh_scenario_detail()
                    refresh_scenario_management_views()
                    if failed_count:
                        ui.notify(
                            f"{updated_count} senaryo guncellendi, {failed_count} dosya atlandi.",
                            color="warning",
                        )
                    else:
                        ui.notify(
                            f"{updated_count} eski senaryo yonetim metadata'si ile guncellendi.",
                            color="positive",
                        )

                def refresh_scenario_cards() -> None:
                    scenarios_grid.clear()
                    with scenarios_grid:
                        for scenario_file in state["scenario_files"]:
                            scenario_path = Path(scenario_file)
                            try:
                                scenario = read_json_file(scenario_path)
                                status = get_scenario_build_status(scenario_path, state)
                            except Exception:
                                continue

                            if not isinstance(scenario, dict):
                                continue

                            is_generated = "generated" in {part.lower() for part in scenario_path.parts}
                            with ui.card().classes("w-72"):
                                ui.label(scenario.get("scenario_name", scenario_path.stem)).classes(
                                    "text-base font-medium"
                                )
                                with ui.row().classes("gap-2 items-center"):
                                    if is_generated:
                                        ui.badge("Generated").props("color=primary outline")
                                    input_name = str(scenario.get("input", "-")).replace("csv_output/", "")
                                    ui.badge(input_name).props("color=grey-7 outline")
                                    change_count = len(scenario.get("changes", []))
                                    ui.badge(f"{change_count} degisiklik").props("color=grey-7 outline")
                                    if status["ready"]:
                                        ui.badge("Ready").props("color=positive")
                                    else:
                                        ui.badge("Not Built").props("color=warning")
                                with ui.row().classes("gap-2 items-center"):
                                    ui.badge(
                                        "Cikti Hazir" if status["output_ready"] else "Cikti Yok"
                                    ).props(
                                        "color=positive outline" if status["output_ready"] else "color=grey-6 outline"
                                    )
                                    ui.badge(
                                        "Log Hazir" if status["log_ready"] else "Log Yok"
                                    ).props(
                                        "color=positive outline" if status["log_ready"] else "color=grey-6 outline"
                                    )
                                ui.label(scenario.get("description", "-")).classes("text-sm text-slate-600")
                                ui.label(
                                    f"Islem sayisi: {len(scenario.get('operations', []))}"
                                ).classes("text-xs text-slate-500")
                                with ui.row().classes("gap-2"):
                                    ui.button(
                                        "Sec",
                                        on_click=lambda file_path=scenario_file: select_scenario(file_path),
                                    ).props("flat color=primary")
                                    ui.button(
                                        "Cikti",
                                        on_click=lambda file_path=scenario_file: open_scenario_output(file_path),
                                    ).props(
                                        "outline size=sm" if status["output_ready"] else "outline size=sm disable"
                                    )
                                    ui.button(
                                        "Log",
                                        on_click=lambda file_path=scenario_file: open_scenario_log(file_path),
                                    ).props(
                                        "outline size=sm" if status["log_ready"] else "outline size=sm disable"
                                    )
                                ui.button(
                                    "Calistir",
                                    on_click=lambda file_path=scenario_file: run_scenario_from_card(file_path),
                                ).props(
                                    "outline color=grey-7 size=sm"
                                    if status["ready"]
                                    else "color=primary size=sm"
                                )

                def refresh_recent_scenarios() -> None:
                    recent_scenarios.set_content(
                        build_recent_scenarios_markdown(read_manifest_entries())
                    )

                def refresh_scenario_detail() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        scenario_summary.set_text("Lutfen bir senaryo secin.")
                        scenario_summary_name.set_text("-")
                        scenario_summary_change_count.set_text("0")
                        scenario_summary_dataset.set_text("-")
                        scenario_detail.set_text("")
                        scenario_change_summary.set_text("")
                        refresh_scenario_management_views()
                        refresh_impact_table()
                        return

                    scenario_path = Path(selected_value)
                    if not scenario_path.exists():
                        scenario_summary.set_text(f"Senaryo bulunamadi: {selected_value}")
                        scenario_summary_name.set_text("-")
                        scenario_summary_change_count.set_text("0")
                        scenario_summary_dataset.set_text("-")
                        scenario_detail.set_text("")
                        scenario_change_summary.set_text("")
                        refresh_scenario_management_views()
                        refresh_impact_table()
                        return

                    scenario = read_json_file(scenario_path)
                    if not isinstance(scenario, dict):
                        scenario_summary.set_text("Senaryo verisi okunamadi.")
                        scenario_summary_name.set_text("-")
                        scenario_summary_change_count.set_text("0")
                        scenario_summary_dataset.set_text("-")
                        scenario_detail.set_text("")
                        scenario_change_summary.set_text("")
                        refresh_scenario_management_views()
                        return

                    scenario_summary.set_text(
                        f"Senaryo: {scenario.get('scenario_name', '-')} | "
                        f"Islem sayisi: {len(scenario.get('operations', []))}"
                    )
                    scenario_summary_name.set_text(str(scenario.get("scenario_name", "-")))
                    scenario_summary_change_count.set_text(str(len(scenario.get("changes", []))))
                    scenario_summary_dataset.set_text(
                        str(scenario.get("input", "-")).replace("csv_output/", "")
                    )
                    scenario_detail.set_text("")
                    scenario_change_summary.set_text("")
                    scenario_copy_name_input.set_value(
                        f"{sanitize_scenario_name(str(scenario.get('scenario_name', scenario_path.stem)))}_copy"
                    )
                    scenario_rename_name_input.set_value(
                        sanitize_scenario_name(str(scenario.get("scenario_name", scenario_path.stem)))
                    )
                    refresh_scenario_management_views()
                    refresh_impact_table()

                def refresh_impact_table() -> None:
                    impact_table_container.clear()
                    impact_transition_charts_container.clear()
                    impact_error.set_text("")

                    def reset_impact_summary(
                        hint_text: str = "Detay listeye girmeden once degisikligin genel etkisi burada gorunecek."
                    ) -> None:
                        summary_hint.set_text(hint_text)
                        changed_field_value.set_text("-")
                        total_impact_value.set_text("0")
                        direct_impact_value.set_text("0")
                        indirect_impact_value.set_text("0")
                        critical_impact_banner.set_text("Kritik etki bilgisi burada gosterilecek.")
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-slate-100 text-slate-700"
                        )

                    def reset_impact_charts(message: str) -> None:
                        impact_chart_info.set_text(message)
                        with impact_transition_charts_container:
                            ui.label(
                                "Parametre bazli degisim grafikleri burada gosterilecek."
                            ).classes("text-sm text-slate-500")
                        change_comparison_chart.options["xAxis"]["data"] = []
                        change_comparison_chart.options["series"][0]["data"] = []
                        change_comparison_chart.options["series"][1]["data"] = []
                        change_comparison_chart.options["series"][2]["data"] = []
                        change_comparison_chart.update()

                        impact_distribution_chart.options["xAxis"]["data"] = []
                        impact_distribution_chart.options["series"][0]["data"] = []
                        impact_distribution_chart.options["series"][1]["data"] = []
                        impact_distribution_chart.update()

                        relation_graph.options["series"][0]["data"] = []
                        relation_graph.options["series"][0]["links"] = []
                        relation_graph.options["series"][0]["categories"] = []
                        relation_graph.update()

                    selected_value = scenario_select.value
                    if not selected_value:
                        reset_impact_summary()
                        reset_impact_charts(
                            "Grafik altyapisi secili senaryonun etki verisiyle beslenecek."
                        )
                        impact_summary.set_text("Lutfen once bir senaryo secin.")
                        return

                    scenario_path = Path(selected_value)
                    if not scenario_path.exists():
                        reset_impact_summary("Degisim ozeti hazirlanamadi.")
                        reset_impact_charts("Grafik verisi hazirlanamadi.")
                        impact_summary.set_text("Senaryo dosyasi bulunamadi.")
                        return

                    try:
                        scenario = load_scenario_definition(scenario_path)
                        _, log_path, _ = scenario_output_targets(scenario_path)
                        impact_rows, message = build_impact_rows_for_scenario(
                            scenario_path,
                            scenario,
                            log_path,
                        )
                        summary_hint.set_text(
                            f"Senaryo: {scenario.get('scenario_name', scenario_path.stem)}"
                        )
                    except (CsvUpdateError, DependencyAnalysisError) as error:
                        reset_impact_summary("Degisim ozeti hesaplanamadi.")
                        reset_impact_charts("Grafik verisi hesaplanamadi.")
                        impact_summary.set_text("Etkilenen alanlar hesaplanamadi.")
                        impact_error.set_text(str(error))
                        return

                    filtered_impact_rows = filter_impact_rows(
                        impact_rows,
                        query=impact_search_input.value or "",
                        impact_type=impact_type_filter.value or "Tum Etkiler",
                        sort_mode=impact_sort_select.value or "Varsayilan",
                    )

                    impact_totals = build_impact_summary(filtered_impact_rows)
                    changed_field_value.set_text(impact_totals["changed_fields"])
                    total_impact_value.set_text(str(impact_totals["total_rows"]))
                    direct_impact_value.set_text(str(impact_totals["direct_rows"]))
                    indirect_impact_value.set_text(str(impact_totals["indirect_rows"]))

                    critical_impact_banner.set_text(impact_totals["critical_message"])
                    if impact_totals["critical_tone"] == "critical":
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-red-100 text-red-800"
                        )
                    elif impact_totals["critical_tone"] == "warning":
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-amber-100 text-amber-800"
                        )
                    else:
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-slate-100 text-slate-700"
                        )

                    impact_summary.set_text(
                        f"{message} | Filtrelenen kayit: {len(filtered_impact_rows)}"
                    )
                    if not filtered_impact_rows:
                        reset_impact_charts("Secili filtrelere uygun etki kaydi bulunamadi.")
                        with impact_table_container:
                            ui.label("Secili filtrelere uygun etkilenen alan bulunamadi.").classes("text-sm text-slate-500")
                        return

                    chart_model = build_impact_chart_model(filtered_impact_rows)
                    impact_transition_rows = build_impact_transition_rows(filtered_impact_rows)
                    impact_chart_info.set_text(
                        "Bar grafikler once/sonra ve veri seti bazli etkiyi; iliski grafigi ise bagimlilik yayilimini gosterir."
                    )
                    change_comparison_chart.options["xAxis"]["data"] = chart_model["comparison"]["labels"]
                    change_comparison_chart.options["series"][0]["data"] = chart_model["comparison"]["old_values"]
                    change_comparison_chart.options["series"][1]["data"] = chart_model["comparison"]["new_values"]
                    change_comparison_chart.options["series"][2]["data"] = chart_model["comparison"]["highlight_values"]
                    change_comparison_chart.update()

                    impact_distribution_chart.options["xAxis"]["data"] = chart_model["distribution"]["labels"]
                    impact_distribution_chart.options["series"][0]["data"] = chart_model["distribution"]["direct_values"]
                    impact_distribution_chart.options["series"][1]["data"] = chart_model["distribution"]["indirect_values"]
                    impact_distribution_chart.update()

                    relation_graph.options["series"][0]["data"] = chart_model["relations"]["nodes"]
                    relation_graph.options["series"][0]["links"] = chart_model["relations"]["links"]
                    relation_graph.options["series"][0]["categories"] = chart_model["relations"]["categories"]
                    relation_graph.update()

                    with impact_transition_charts_container:
                        ui.label("Senaryo Bazli Ayrik Degisim Grafikleri").classes("text-sm font-medium")
                        if impact_transition_rows:
                            ui.label(
                                "Secili senaryodaki her degisen alan icin ayri Ilk Deger / Yeni Deger grafigi olusturuldu."
                            ).classes("text-xs text-slate-600")
                            with ui.row().classes("w-full gap-4 items-stretch flex-wrap"):
                                for item in impact_transition_rows:
                                    with ui.card().classes("w-full min-w-[20rem] grow"):
                                        ui.label(str(item["label"])).classes("text-sm font-medium")
                                        ui.echart(
                                            build_value_transition_chart_options(
                                                label=str(item["label"]),
                                                base_value=item["base_value"],
                                                updated_value=item["updated_value"],
                                                unit=str(item["unit"]),
                                            )
                                        ).classes("w-full h-64")
                        else:
                            ui.label(
                                "Bu senaryoda ayrik grafik uretilebilecek sayisal degisim bulunamadi."
                            ).classes("text-sm text-slate-500")

                    with impact_table_container:
                        impact_table = ui.table(
                            columns=[
                                {"name": "degisen_alan", "label": "Alan", "field": "degisen_alan", "sortable": True},
                                {"name": "eski_deger", "label": "Eski Deger", "field": "eski_deger", "sortable": True},
                                {"name": "yeni_deger", "label": "Yeni Deger", "field": "yeni_deger", "sortable": True},
                                {"name": "degisim_miktari", "label": "Degisim", "field": "degisim_miktari", "sortable": True},
                                {"name": "yon", "label": "Yon", "field": "yon", "sortable": True},
                                {"name": "etki_tipi", "label": "Etki", "field": "etki_tipi", "sortable": True},
                                {"name": "etkilenen_veri", "label": "Etkilenen Veri", "field": "etkilenen_veri", "sortable": True},
                                {"name": "etkilenen_satir", "label": "Satir", "field": "etkilenen_satir", "sortable": True},
                                {"name": "kaynak", "label": "Kaynak", "field": "kaynak", "sortable": True},
                            ],
                            rows=filtered_impact_rows,
                            row_key="id",
                            pagination={"rowsPerPage": 10},
                        ).classes("w-full")
                        impact_table.add_slot(
                            "body-cell-etki_tipi",
                            r'''
                            <q-td :props="props">
                              <q-badge
                                :color="props.value === 'Dogrudan' ? 'positive' : (props.value === 'Dolayli' ? 'warning' : 'grey-6')"
                                :label="props.value"
                              />
                            </q-td>
                            ''',
                        )
                        impact_table.add_slot(
                            "body-cell-yon",
                            r'''
                            <q-td :props="props">
                              <q-badge
                                :color="props.value === 'Artis' ? 'positive' : (props.value === 'Azalis' ? 'negative' : 'grey-6')"
                                :label="props.value"
                              />
                            </q-td>
                            ''',
                        )
                        impact_table.on(
                            "rowClick",
                            lambda event: open_row_detail(
                                "Etki Kaydi Detayi",
                                event.args["row"],
                                [
                                    "degisen_alan",
                                    "eski_deger",
                                    "yeni_deger",
                                    "degisim_miktari",
                                    "yon",
                                    "etki_tipi",
                                    "etkilenen_veri",
                                    "etkilenen_satir",
                                    "kaynak",
                                    "neden",
                                ],
                            ),
                        )

                def clear_impact_filters() -> None:
                    impact_search_input.set_value("")
                    impact_type_filter.set_value("Tum Etkiler")
                    impact_sort_select.set_value("Varsayilan")
                    refresh_impact_table()

                def handle_scenario_change() -> None:
                    refresh_scenario_detail()

                def apply_requested_focus() -> None:
                    if not requested_scenario or requested_scenario != scenario_select.value:
                        if requested_focus == "audit":
                            tabs.set_value(audit_tab)
                            refresh_audit_table()
                        return
                    if requested_focus == "output":
                        tabs.set_value(data_tab)
                        focus_output_file()
                        return
                    if requested_focus == "log":
                        tabs.set_value(logs_tab)
                        focus_log_file()
                        return
                    if requested_focus == "impact":
                        tabs.set_value(scenarios_tab)
                        refresh_scenario_detail()
                        refresh_impact_table()
                        return
                    if requested_focus == "scenario":
                        tabs.set_value(scenarios_tab)
                        refresh_scenario_detail()
                        return
                    if requested_focus == "audit":
                        tabs.set_value(audit_tab)
                        refresh_audit_table()

                open_output_button.on("click", lambda _: focus_output_file())
                open_log_button.on("click", lambda _: focus_log_file())
                run_button.on("click", lambda _: run_scenario_preparation())
                copy_scenario_button.on("click", lambda _: copy_selected_scenario())
                rename_scenario_button.on("click", lambda _: rename_selected_scenario())
                backfill_scenarios_button.on("click", lambda _: backfill_existing_scenario_metadata())
                scenario_select.on_value_change(lambda _: handle_scenario_change())
                scenario_compare_select.on_value_change(lambda _: refresh_scenario_management_views())
                scenario_compare_third_select.on_value_change(lambda _: refresh_scenario_management_views())
                scenario_compare_mode.on_value_change(lambda _: refresh_scenario_management_views())
                scenario_diff_filter.on_value_change(lambda _: refresh_scenario_management_views())
                export_scenario_diff_button.on("click", lambda _: export_scenario_diff_rows())
                impact_search_input.on_value_change(lambda _: refresh_impact_table())
                impact_type_filter.on_value_change(lambda _: refresh_impact_table())
                impact_sort_select.on_value_change(lambda _: refresh_impact_table())
                clear_impact_filters_button.on("click", lambda _: clear_impact_filters())
                refresh_scenario_cards()
                refresh_scenario_detail()
                refresh_recent_scenarios()
                refresh_scenario_management_views()
                apply_requested_focus()

            with ui.tab_panel(cost_tab):
                with ui.card().classes("w-full dashboard-panel"):
                    ui.label("Maliyet Analizi").classes("text-lg font-semibold text-slate-900")
                    cost_info = ui.label("").classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4"):
                        cost_scenario_select = ui.select(options=[], label="Senaryo").classes("w-full dashboard-input")
                        cost_profile_select = ui.select(
                            options=get_cost_profile_options(),
                            value="tr_electricity_residential",
                            label="Maliyet Profili",
                        ).classes("w-full dashboard-input")
                        cost_unit_price_input = ui.number(
                            label="Enerji Birim Maliyeti",
                            value=2.35,
                            format="%.4f",
                        ).classes("w-full dashboard-input")
                        cost_currency_input = ui.input(label="Para Birimi", value="TRY").props("outlined clearable").classes("w-full dashboard-input")
                    cost_summary_markdown = ui.markdown("").classes("w-full text-sm")
                    cost_chart_info = ui.label(
                        "Old annual cost, new annual cost ve savings karsilastirmasi."
                    ).classes("text-sm text-slate-600")
                    cost_comparison_chart = ui.echart(
                        {
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                            "xAxis": {
                                "type": "category",
                                "data": ["Old Annual Cost", "New Annual Cost", "Savings"],
                            },
                            "yAxis": {"type": "value", "name": "TRY"},
                            "series": [
                                {
                                    "name": "Cost",
                                    "type": "bar",
                                    "data": [],
                                }
                            ],
                        }
                    ).classes("w-full h-72")
                    cost_table_container = ui.column().classes("w-full")

                def apply_cost_profile() -> None:
                    profile = resolve_cost_profile(str(cost_profile_select.value or "custom"))
                    cost_unit_price_input.set_value(float(profile["unit_cost"]))
                    cost_currency_input.set_value(str(profile["currency"]))
                    refresh_cost_tab()

                def refresh_cost_tab() -> None:
                    comparison_entries = read_comparison_report_entries()
                    scenario_names = [str(item.get("scenario_name", "-")) for item in comparison_entries]

                    cost_scenario_select.options = scenario_names
                    cost_scenario_select.update()
                    if scenario_names and cost_scenario_select.value not in scenario_names:
                        cost_scenario_select.set_value(scenario_names[0])

                    if not comparison_entries:
                        cost_info.set_text("Maliyet sekmesi bos kalmaz: karsilastirma raporu bulunamadi.")
                        cost_summary_markdown.set_content(
                            "Maliyet verisi henuz uretilmedi. Once Senaryolar sekmesinden "
                            "karsilastirmali simulasyon calistirin; economics/lifecycle verisi yoksa "
                            "sistem total energy uzerinden basit tahmin gosterir."
                        )
                        cost_comparison_chart.options["yAxis"]["name"] = "TRY"
                        cost_comparison_chart.options["series"][0]["data"] = []
                        cost_comparison_chart.update()
                        cost_table_container.clear()
                        with cost_table_container:
                            ui.label("Rapor bulunamadigi icin tablo olusturulamadi.").classes("text-sm text-slate-500")
                        return

                    selected_name = str(cost_scenario_select.value or "").strip()
                    selected_entry = next(
                        (item for item in comparison_entries if str(item.get("scenario_name", "")) == selected_name),
                        comparison_entries[-1],
                    )

                    currency = str(cost_currency_input.value or "TRY").strip() or "TRY"
                    try:
                        energy_unit_cost = float(cost_unit_price_input.value)
                    except (TypeError, ValueError):
                        energy_unit_cost = 0.12

                    selected_summary = build_cost_summary_from_metrics(
                        list(selected_entry.get("metrics", [])),
                        energy_unit_cost=energy_unit_cost,
                        currency=currency,
                    )
                    cost_chart_model = build_cost_comparison_chart_model(selected_summary)
                    method_labels = {
                        "annual_cost": "Dogrudan annual cost",
                        "estimated_from_total_energy": "Total energy tabanli tahmin",
                        "unavailable": "Veri yok",
                    }

                    cost_info.set_text(
                        f"Secili senaryo: {selected_entry.get('scenario_name', '-')} | "
                        f"Yontem: {method_labels.get(str(selected_summary.get('method', '')), 'Bilinmiyor')}"
                    )
                    cost_summary_markdown.set_content(
                        "\n".join(
                            [
                                f"**Senaryo:** {selected_entry.get('scenario_name', '-')}",
                                f"- Baz maliyet: {format_cost_value(selected_summary.get('base_cost'), currency)}",
                                f"- Senaryo maliyeti: {format_cost_value(selected_summary.get('scenario_cost'), currency)}",
                                f"- Delta: {format_cost_value(selected_summary.get('delta'), currency)}",
                                f"- Yuzde fark: {selected_summary.get('percent_delta') if selected_summary.get('percent_delta') is not None else '-'}",
                                f"- Aciklama: {selected_summary.get('message', '-')}",
                            ]
                        )
                    )

                    cost_comparison_chart.options["yAxis"]["name"] = currency
                    cost_comparison_chart.options["xAxis"]["data"] = cost_chart_model["labels"]
                    cost_comparison_chart.options["series"][0]["data"] = cost_chart_model["values"]
                    cost_comparison_chart.update()

                    savings_value = cost_chart_model["savings"]
                    if not cost_chart_model["has_data"]:
                        cost_chart_info.set_text(
                            "Maliyet grafigi icin old/new annual cost verisi bulunamadi."
                        )
                    elif savings_value is not None and float(savings_value) >= 0:
                        cost_chart_info.set_text(
                            f"Savings pozitif: {float(savings_value):.2f} {currency}"
                        )
                    else:
                        cost_chart_info.set_text(
                            f"Savings negatif (ek maliyet): {float(savings_value or 0):.2f} {currency}"
                        )

                    rows = []
                    for entry in comparison_entries:
                        summary = build_cost_summary_from_metrics(
                            list(entry.get("metrics", [])),
                            energy_unit_cost=energy_unit_cost,
                            currency=currency,
                        )
                        rows.append(
                            {
                                "scenario_name": entry.get("scenario_name", "-"),
                                "method": method_labels.get(str(summary.get("method", "")), "Bilinmiyor"),
                                "base_cost": format_cost_value(summary.get("base_cost"), currency),
                                "scenario_cost": format_cost_value(summary.get("scenario_cost"), currency),
                                "delta": format_cost_value(summary.get("delta"), currency),
                                "percent_delta": (
                                    f"{float(summary.get('percent_delta')):.2f}%"
                                    if summary.get("percent_delta") is not None
                                    else "-"
                                ),
                            }
                        )

                    cost_table_container.clear()
                    with cost_table_container:
                        ui.table(
                            columns=[
                                {"name": "scenario_name", "label": "Senaryo", "field": "scenario_name"},
                                {"name": "method", "label": "Yontem", "field": "method"},
                                {"name": "base_cost", "label": "Baz Maliyet", "field": "base_cost"},
                                {"name": "scenario_cost", "label": "Senaryo Maliyeti", "field": "scenario_cost"},
                                {"name": "delta", "label": "Maliyet Farki", "field": "delta"},
                                {"name": "percent_delta", "label": "Yuzde Fark", "field": "percent_delta"},
                            ],
                            rows=rows,
                            row_key="scenario_name",
                            pagination={"rowsPerPage": 8},
                        ).classes("w-full")

                cost_scenario_select.on_value_change(lambda _: refresh_cost_tab())
                cost_profile_select.on_value_change(lambda _: apply_cost_profile())
                cost_unit_price_input.on_value_change(lambda _: refresh_cost_tab())
                cost_currency_input.on_value_change(lambda _: refresh_cost_tab())
                ui.button("Profili Uygula", on_click=apply_cost_profile).props("outline").classes("parameter-action-button")
                ui.button("Maliyet Tablosunu Yenile", on_click=refresh_cost_tab).props("outline").classes("parameter-action-button")
                refresh_cost_tab()

            with ui.tab_panel(analytics_tab):
                analytics_section = build_analytics_tab_section(
                    monthly_labels_tr=MONTH_LABELS_TR,
                    monthly_tooltip_formatter=build_overlay_tooltip_formatter("Ay", "kWh"),
                    zone_tooltip_formatter=build_overlay_tooltip_formatter("Saat", "C"),
                    comfort_band_min_c=COMFORT_BAND_MIN_C,
                    comfort_band_max_c=COMFORT_BAND_MAX_C,
                )
                analytics_info = analytics_section["analytics_info"]
                analysis_scenario_select = analytics_section["analysis_scenario_select"]
                refresh_all_button = analytics_section["refresh_all_button"]
                last_refresh_label = analytics_section["last_refresh_label"]
                analysis_data_status = analytics_section["analysis_data_status"]
                analysis_status_badge = analytics_section["analysis_status_badge"]
                analysis_workflow_markdown = analytics_section["analysis_workflow_markdown"]
                changes_chart = analytics_section["changes_chart"]
                flow_chart = analytics_section["flow_chart"]
                expected_effect_info = analytics_section["expected_effect_info"]
                energy_performance_info = analytics_section["energy_performance_info"]
                energy_performance_status = analytics_section["energy_performance_status"]
                energy_performance_commentary = analytics_section["energy_performance_commentary"]
                energy_actions = analytics_section["energy_actions"]
                analytics_missing_metrics = analytics_section["analytics_missing_metrics"]
                energy_performance_chart = analytics_section["energy_performance_chart"]
                run_trend_info = analytics_section["run_trend_info"]
                run_trend_status = analytics_section["run_trend_status"]
                run_trend_commentary = analytics_section["run_trend_commentary"]
                run_trend_actions = analytics_section["run_trend_actions"]
                run_trend_metric_select = analytics_section["run_trend_metric_select"]
                run_trend_chart = analytics_section["run_trend_chart"]
                real_output_info = analytics_section["real_output_info"]
                real_output_status = analytics_section["real_output_status"]
                real_output_commentary = analytics_section["real_output_commentary"]
                real_output_actions = analytics_section["real_output_actions"]
                real_output_chart = analytics_section["real_output_chart"]
                real_output_delta_chart = analytics_section["real_output_delta_chart"]
                monthly_energy_info = analytics_section["monthly_energy_info"]
                monthly_energy_status = analytics_section["monthly_energy_status"]
                monthly_energy_commentary = analytics_section["monthly_energy_commentary"]
                monthly_actions = analytics_section["monthly_actions"]
                monthly_heating_chart = analytics_section["monthly_heating_chart"]
                monthly_cooling_chart = analytics_section["monthly_cooling_chart"]
                zone_temperature_info = analytics_section["zone_temperature_info"]
                zone_temperature_status = analytics_section["zone_temperature_status"]
                zone_temperature_commentary = analytics_section["zone_temperature_commentary"]
                zone_temperature_actions = analytics_section["zone_temperature_actions"]
                zone_temperature_select = analytics_section["zone_temperature_select"]
                zone_temperature_chart = analytics_section["zone_temperature_chart"]
                zone_heatmap_metric_select = analytics_section["zone_heatmap_metric_select"]
                zone_heatmap_info = analytics_section["zone_heatmap_info"]
                zone_heatmap_status = analytics_section["zone_heatmap_status"]
                zone_heatmap_commentary = analytics_section["zone_heatmap_commentary"]
                zone_heatmap_actions = analytics_section["zone_heatmap_actions"]
                zone_heatmap_chart = analytics_section["zone_heatmap_chart"]
                advanced_analysis_info = analytics_section["advanced_analysis_info"]
                advanced_analysis_status = analytics_section["advanced_analysis_status"]
                advanced_analysis_commentary = analytics_section["advanced_analysis_commentary"]
                advanced_actions = analytics_section["advanced_actions"]
                advanced_analysis_markdown = analytics_section["advanced_analysis_markdown"]
                overlay_scenarios_select = analytics_section["overlay_scenarios_select"]
                comparison_left = analytics_section["comparison_left"]
                comparison_right = analytics_section["comparison_right"]
                comparison_markdown = analytics_section["comparison_markdown"]
                selected_analysis_state_cache: dict[str, object] = {
                    "signature": None,
                    "value": None,
                }
                analysis_refresh_state: dict[str, object] = {
                    "last_refresh_text": "-",
                }

                def get_selected_scenario_analysis_state() -> dict[str, object]:
                    comparison_entries = read_comparison_report_entries()
                    preparation_only_scenarios = list_preparation_only_scenarios(SCENARIO_RUNS_DIR)
                    reports_by_name = {
                        item.get("scenario_name"): item for item in comparison_entries
                    }
                    scenario_names = [
                        str(item.get("scenario_name", "")).strip()
                        for item in comparison_entries
                    ]
                    selected_name = str(analysis_scenario_select.value or "").strip()
                    if not selected_name:
                        selected_name = str(comparison_left.value or "").strip()
                    if not selected_name and reports_by_name:
                        selected_name = str(next(iter(reports_by_name.keys())) or "")

                    signature = build_selected_analysis_signature(comparison_entries, selected_name)
                    if selected_analysis_state_cache.get("signature") == signature:
                        cached_value = selected_analysis_state_cache.get("value")
                        if isinstance(cached_value, dict):
                            return cached_value

                    selected_report = reports_by_name.get(selected_name, {})
                    metrics_rows: list[dict[str, object]] = []
                    report_path = ""
                    missing_metric_ids: list[str] = []
                    null_metric_ids: list[str] = []
                    available_metric_ids: list[str] = []
                    metric_source_status = "unknown"
                    metric_source_message = ""
                    if isinstance(selected_report, dict):
                        metrics_rows = list(selected_report.get("metrics", []))
                        report_path = str(selected_report.get("report_path", ""))
                        missing_metric_ids = list(selected_report.get("missing_metric_ids", []))
                        null_metric_ids = list(selected_report.get("null_metric_ids", []))
                        available_metric_ids = list(selected_report.get("available_metric_ids", []))
                        metric_source_status = str(selected_report.get("metric_source_status", "unknown") or "unknown")
                        metric_source_message = str(selected_report.get("metric_source_message", "") or "")

                    value = {
                        "comparison_entries": comparison_entries,
                        "reports_by_name": reports_by_name,
                        "scenario_styles": build_scenario_visual_registry(scenario_names),
                        "selected_name": selected_name,
                        "selected_report": selected_report,
                        "metrics_rows": metrics_rows,
                        "report_path": report_path,
                        "missing_metric_ids": missing_metric_ids,
                        "null_metric_ids": null_metric_ids,
                        "available_metric_ids": available_metric_ids,
                        "metric_source_status": metric_source_status,
                        "metric_source_message": metric_source_message,
                        "preparation_only_scenarios": preparation_only_scenarios,
                    }
                    selected_analysis_state_cache["signature"] = signature
                    selected_analysis_state_cache["value"] = value
                    return value

                def set_card_empty_hint(action_row: dict[str, object], message: str) -> None:
                    label = action_row.get("why_empty_label")
                    if hasattr(label, "set_text"):
                        label.set_text(message)

                def set_card_status_badge(action_row: dict[str, object], status: str) -> None:
                    badge = action_row.get("status_badge")
                    if not hasattr(badge, "set_text"):
                        return
                    badge.set_text(status)
                    badge.classes(
                        remove=(
                            "bg-slate-200 text-slate-700 "
                            "bg-emerald-100 text-emerald-800 "
                            "bg-amber-100 text-amber-800 "
                            "bg-rose-100 text-rose-800 "
                            "bg-sky-100 text-sky-800"
                        )
                    )
                    if status == "GUNCEL":
                        badge.classes(add="bg-emerald-100 text-emerald-800")
                    elif status == "HAZIRLIKTA":
                        badge.classes(add="bg-amber-100 text-amber-800")
                    elif status == "VERI EKSIK":
                        badge.classes(add="bg-sky-100 text-sky-800")
                    elif status == "GEREKLI":
                        badge.classes(add="bg-rose-100 text-rose-800")
                    else:
                        badge.classes(add="bg-slate-200 text-slate-700")

                def build_analysis_workflow_markdown(
                    *,
                    selected_name: str,
                    report_path: str,
                    metric_source_status: str,
                    metric_source_message: str,
                    preparation_only_scenarios: list[str],
                    has_chart_data: bool,
                ) -> str:
                    scenario_ready = bool(selected_name)
                    comparison_ready = bool(report_path)
                    charts_ready = bool(has_chart_data) and metric_source_status != "unavailable"

                    def line(done: bool, text: str) -> str:
                        color = "#166534" if done else "#b91c1c"
                        status = "Tamam" if done else "Eksik"
                        return f"- <span style='color:{color}'><strong>{status}</strong></span>: {text}"

                    lines = ["**Analiz Adimlari**"]
                    lines.append(line(scenario_ready, "1. Senaryo hazirlandi"))
                    lines.append(line(comparison_ready, "2. Comparison uretildi"))
                    lines.append(line(charts_ready, "3. Grafikler guncellendi"))
                    if selected_name and selected_name in preparation_only_scenarios and not report_path:
                        lines.append(
                            "- <span style='color:#b45309'><strong>Yonlendirme</strong></span>: Bu senaryo sadece hazirlik asamasinda. Devam etmek icin `Gercek Karsilastirmali Calistirma` butonunu kullan."
                        )
                    elif not report_path:
                        lines.append(
                            "- <span style='color:#b45309'><strong>Yonlendirme</strong></span>: Bu grafikler icin comparison raporu gerekli."
                        )
                    elif metric_source_status == "unavailable":
                        lines.append(
                            "- <span style='color:#b45309'><strong>Yonlendirme</strong></span>: Comparison raporu var, ancak gercek simulasyon metrikleri yok. Bu rapor su an daha cok CSV farklarini gosteriyor."
                        )
                    if metric_source_message:
                        lines.append(f"- <strong>Kaynak Notu</strong>: {metric_source_message}")
                    return "\n".join(lines)

                def update_analysis_toolbar(*, has_chart_data: bool = False) -> None:
                    analysis_state = get_selected_scenario_analysis_state()
                    selected_name = str(analysis_state["selected_name"] or "-")
                    report_path = str(analysis_state.get("report_path", "") or "")
                    metric_source_status = str(analysis_state.get("metric_source_status", "unknown") or "unknown")
                    metric_source_message = str(analysis_state.get("metric_source_message", "") or "")
                    preparation_only_scenarios = list(analysis_state.get("preparation_only_scenarios", []))

                    last_refresh_label.set_text(
                        f"Son Guncelleme: {analysis_refresh_state.get('last_refresh_text', '-')}"
                    )
                    if report_path:
                        if metric_source_status == "unavailable":
                            analysis_data_status.set_text("Durum: comparison var, simulasyon metrigi yok")
                            analysis_status_badge.set_text("VERI EKSIK")
                            analysis_status_badge.classes(
                                remove="bg-slate-200 text-slate-700 bg-emerald-100 text-emerald-800 bg-amber-100 text-amber-800 bg-rose-100 text-rose-800"
                            )
                            analysis_status_badge.classes(add="bg-sky-100 text-sky-800")
                        else:
                            analysis_data_status.set_text("Durum: comparison raporu bulundu")
                            analysis_status_badge.set_text("GUNCEL")
                            analysis_status_badge.classes(
                                remove="bg-slate-200 text-slate-700 bg-amber-100 text-amber-800 bg-rose-100 text-rose-800 bg-sky-100 text-sky-800"
                            )
                            analysis_status_badge.classes(add="bg-emerald-100 text-emerald-800")
                    elif selected_name in preparation_only_scenarios:
                        analysis_data_status.set_text("Durum: sadece hazirlik tamamlandi")
                        analysis_status_badge.set_text("HAZIRLIKTA")
                        analysis_status_badge.classes(
                            remove="bg-slate-200 text-slate-700 bg-emerald-100 text-emerald-800 bg-rose-100 text-rose-800"
                        )
                        analysis_status_badge.classes(add="bg-amber-100 text-amber-800")
                    else:
                        analysis_data_status.set_text("Durum: comparison raporu yok")
                        analysis_status_badge.set_text("COMPARISON YOK")
                        analysis_status_badge.classes(
                            remove="bg-slate-200 text-slate-700 bg-emerald-100 text-emerald-800 bg-amber-100 text-amber-800"
                        )
                        analysis_status_badge.classes(add="bg-rose-100 text-rose-800")
                    analysis_workflow_markdown.set_content(
                        build_analysis_workflow_markdown(
                            selected_name=selected_name,
                            report_path=report_path,
                            metric_source_status=metric_source_status,
                            metric_source_message=metric_source_message,
                            preparation_only_scenarios=preparation_only_scenarios,
                            has_chart_data=has_chart_data,
                        )
                    )

                def refresh_all_analytics(*, update_timestamp: bool = True) -> None:
                    selected_analysis_state_cache["signature"] = None
                    selected_analysis_state_cache["value"] = None
                    refresh_recent_scenarios()
                    refresh_comparison()
                    refresh_energy_performance_chart()
                    refresh_run_to_run_trend_chart()
                    refresh_real_output_chart()
                    refresh_monthly_energy_chart()
                    refresh_zone_temperature_chart()
                    refresh_advanced_analysis()
                    if update_timestamp:
                        analysis_refresh_state["last_refresh_text"] = datetime.now().strftime("%H:%M:%S")

                    analysis_state = get_selected_scenario_analysis_state()
                    has_chart_data = bool(analysis_state.get("metrics_rows"))
                    update_analysis_toolbar(has_chart_data=has_chart_data)

                def refresh_energy_performance_chart() -> None:
                    analysis_state = get_selected_scenario_analysis_state()
                    scenario_styles = analysis_state["scenario_styles"]
                    selected_name = str(analysis_state["selected_name"])
                    metrics_rows = list(analysis_state["metrics_rows"])
                    missing_metric_ids = list(analysis_state["missing_metric_ids"])
                    null_metric_ids = list(analysis_state["null_metric_ids"])
                    report_path = str(analysis_state["report_path"])
                    metric_source_status = str(analysis_state.get("metric_source_status", "unknown") or "unknown")
                    metric_source_message = str(analysis_state.get("metric_source_message", "") or "")
                    preparation_only_scenarios = list(analysis_state.get("preparation_only_scenarios", []))

                    chart_model = build_energy_performance_chart_model(metrics_rows)
                    base_profile = get_base_scenario_visual_profile()
                    scenario_profile = scenario_styles.get(
                        selected_name,
                        build_scenario_visual_profile(selected_name),
                    )
                    legend_labels = build_overlay_legend_labels(base_profile, scenario_profile)
                    energy_performance_chart.options["yAxis"]["data"] = chart_model["labels"]
                    energy_performance_chart.options["xAxis"]["name"] = str(chart_model["unit"])
                    energy_performance_chart.options["legend"]["data"] = legend_labels
                    energy_performance_chart.options["tooltip"]["trigger"] = "axis"
                    energy_performance_chart.options["tooltip"]["axisPointer"] = {"type": "line"}
                    energy_performance_chart.options["tooltip"]["formatter"] = build_dumbbell_energy_tooltip_formatter(
                        chart_model
                    )

                    connector_series: list[list[object]] = []
                    base_points: list[list[object]] = []
                    scenario_points: list[list[object]] = []
                    for label, base_value, scenario_value in zip(
                        list(chart_model["labels"]),
                        list(chart_model["before_values"]),
                        list(chart_model["after_values"]),
                    ):
                        if base_value is None or scenario_value is None:
                            continue
                        connector_series.extend(
                            [
                                [float(base_value), str(label)],
                                [float(scenario_value), str(label)],
                                None,
                            ]
                        )
                        base_points.append([float(base_value), str(label)])
                        scenario_points.append([float(scenario_value), str(label)])

                    energy_performance_chart.options["series"][0]["name"] = "Baglanti"
                    energy_performance_chart.options["series"][0]["data"] = connector_series
                    energy_performance_chart.options["series"][0]["lineStyle"] = {
                        "color": "#94a3b8",
                        "width": 2,
                        "opacity": 0.7,
                    }
                    energy_performance_chart.options["series"][1]["name"] = legend_labels[0]
                    energy_performance_chart.options["series"][1]["data"] = base_points
                    energy_performance_chart.options["series"][1]["itemStyle"] = {
                        "color": str(base_profile["accent_color"])
                    }
                    energy_performance_chart.options["series"][2]["name"] = legend_labels[1]
                    energy_performance_chart.options["series"][2]["data"] = scenario_points
                    energy_performance_chart.options["series"][2]["itemStyle"] = {
                        "color": str(scenario_profile["accent_color"])
                    }
                    energy_performance_chart.update()
                    analytics_missing_metrics.set_content(
                        build_missing_metrics_markdown(
                            title="Enerji performansi",
                            selected_name=selected_name,
                            missing_metric_ids=missing_metric_ids,
                            null_metric_ids=null_metric_ids,
                            report_path=report_path,
                        )
                    )

                    status_items: list[str] = []
                    if report_path:
                        status_items.append(f"Comparison raporu bulundu: {report_path}")
                    elif selected_name and selected_name in preparation_only_scenarios:
                        status_items.append("Secili senaryo sadece hazirlik asamasinda; comparison raporu olusmamis.")
                    elif preparation_only_scenarios:
                        status_items.append(
                            "Sadece hazirlikta kalan senaryolar: " + ", ".join(preparation_only_scenarios[:4])
                        )
                    else:
                        status_items.append("Comparison raporu yok.")
                    if missing_metric_ids:
                        status_items.append("Eksik metric_id: " + ", ".join(missing_metric_ids))
                    if null_metric_ids:
                        status_items.append("Degeri bos metric_id: " + ", ".join(null_metric_ids))
                    if metric_source_status == "unavailable":
                        status_items.append(
                            metric_source_message
                            or "Bu comparison su an gercek simulasyon metrikleri yerine sadece CSV farklarini tasiyor."
                        )
                    energy_performance_status.set_content(
                        build_status_panel_markdown("Enerji Performansi Veri Durumu", status_items)
                    )
                    set_card_empty_hint(
                        energy_actions,
                        (
                            "Bu grafik icin comparison raporu gerekli. Devam etmek icin `Gercek Karsilastirmali Calistirma` butonunu kullan."
                            if not report_path
                            else (
                                "Comparison raporu var ama simulasyon enerji metrikleri yok. Bu run su an sadece CSV farklarini gosteriyor."
                                if metric_source_status == "unavailable"
                                else "Grafik bos kalirsa annual_heating / annual_cooling / total_energy metric'lerini kontrol et."
                            )
                        ),
                    )
                    if not report_path:
                        set_card_status_badge(
                            energy_actions,
                            "HAZIRLIKTA" if selected_name in preparation_only_scenarios else "GEREKLI",
                        )
                    elif metric_source_status == "unavailable":
                        set_card_status_badge(energy_actions, "VERI EKSIK")
                    elif not chart_model["has_data"]:
                        set_card_status_badge(energy_actions, "VERI EKSIK")
                    else:
                        set_card_status_badge(energy_actions, "GUNCEL")

                    if not selected_name:
                        energy_performance_info.set_text(
                            "Enerji performans grafigi icin once comparison raporu olan bir senaryo secin."
                        )
                        energy_performance_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Bu grafik gercek simulasyon comparison raporuyla doluyor.",
                                    (
                                        f"Son hazirlikta kalan senaryo: {preparation_only_scenarios[-1]}"
                                        if preparation_only_scenarios
                                        else "Henuz gosterilecek bir comparison raporu yok."
                                    ),
                                ],
                            )
                        )
                        return
                    if not chart_model["has_data"]:
                        energy_performance_info.set_text(
                            f"Secili senaryo: {selected_name} | Annual heating/cooling/total energy verisi bulunamadi. "
                            f"Null metrikler: {', '.join(null_metric_ids) if null_metric_ids else '-'} | Rapor: {report_path or '-'}"
                        )
                        energy_performance_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Bu grafikte annual_heating / annual_cooling / total_energy alanlarindan en az biri bos.",
                                    (
                                        "Senaryo sadece hazirlik asamasinda kalmis olabilir."
                                        if selected_name in preparation_only_scenarios
                                        else (
                                            "Comparison raporu var ama gercek simulasyon metrikleri uretilmemis; su an sadece CSV farklari karsilastiriliyor."
                                            if metric_source_status == "unavailable"
                                            else "Comparison raporu olussa bile gerekli enerji metrikleri null olabilir."
                                        )
                                    ),
                                ],
                            )
                        )
                        return
                    commentary_items = [
                        build_metric_change_commentary(label, base_value, updated_value, str(chart_model["unit"]))
                        for label, base_value, updated_value in zip(
                            list(chart_model["labels"]),
                            list(chart_model["before_values"]),
                            list(chart_model["after_values"]),
                        )
                    ]
                    if chart_model["missing_count"] or missing_metric_ids or null_metric_ids:
                        missing_text = ", ".join(chart_model["missing_labels"] or missing_metric_ids)
                        null_text = ", ".join(null_metric_ids) if null_metric_ids else "-"
                        energy_performance_info.set_text(
                            f"Secili senaryo: {selected_name} | Eksik metrikler: {missing_text} | "
                            f"Null metrikler: {null_text} | Rapor: {report_path or '-'} | "
                            f"{build_overlay_explanation('enerji performansi', base_profile, scenario_profile)}"
                        )
                    else:
                        energy_performance_info.set_text(
                            f"Secili senaryo: {selected_name} | "
                            f"{build_overlay_explanation('enerji performansi', base_profile, scenario_profile)}"
                        )
                    energy_performance_commentary.set_content(
                        build_commentary_panel_markdown("Kisa Yorum", commentary_items[:3])
                    )

                def refresh_real_output_chart() -> None:
                    analysis_state = get_selected_scenario_analysis_state()
                    scenario_styles = analysis_state["scenario_styles"]
                    selected_name = str(analysis_state["selected_name"])
                    metrics_rows = list(analysis_state["metrics_rows"])
                    missing_metric_ids = list(analysis_state["missing_metric_ids"])
                    null_metric_ids = list(analysis_state["null_metric_ids"])
                    report_path = str(analysis_state["report_path"])
                    metric_source_status = str(analysis_state.get("metric_source_status", "unknown") or "unknown")
                    metric_source_message = str(analysis_state.get("metric_source_message", "") or "")
                    preparation_only_scenarios = list(analysis_state.get("preparation_only_scenarios", []))

                    chart_model = build_real_output_comparison_chart_model(metrics_rows)
                    base_profile = get_base_scenario_visual_profile()
                    scenario_profile = scenario_styles.get(
                        selected_name,
                        build_scenario_visual_profile(selected_name),
                    )
                    legend_labels = build_overlay_legend_labels(base_profile, scenario_profile)
                    y_axis_name = (
                        "Normalize Edilmis Cikti"
                        if chart_model["is_normalized"]
                        else "Cikti"
                    )
                    real_output_chart.options["xAxis"]["data"] = chart_model["labels"]
                    real_output_chart.options["yAxis"]["name"] = y_axis_name
                    real_output_chart.options["legend"]["data"] = legend_labels
                    real_output_chart.options["series"][0]["name"] = legend_labels[0]
                    real_output_chart.options["series"][0]["data"] = chart_model["before_values"]
                    real_output_chart.options["series"][0]["lineStyle"] = {
                        "color": str(base_profile["accent_color"]),
                        "width": 3,
                        "type": "solid",
                    }
                    real_output_chart.options["series"][0]["itemStyle"] = {
                        "color": str(base_profile["accent_color"])
                    }
                    real_output_chart.options["series"][1]["name"] = legend_labels[1]
                    real_output_chart.options["series"][1]["data"] = chart_model["after_values"]
                    real_output_chart.options["series"][1]["lineStyle"] = {
                        "color": str(scenario_profile["accent_color"]),
                        "width": 3,
                        "type": "dashed",
                    }
                    real_output_chart.options["series"][1]["itemStyle"] = {
                        "color": str(scenario_profile["accent_color"])
                    }
                    real_output_chart.options["tooltip"]["formatter"] = build_parameter_overlay_tooltip_formatter(
                        chart_model
                    )
                    real_output_chart.update()
                    delta_chart_options = build_real_output_delta_chart_options(chart_model)
                    real_output_delta_chart.options["xAxis"]["data"] = delta_chart_options["xAxis"]["data"]
                    real_output_delta_chart.options["yAxis"]["name"] = delta_chart_options["yAxis"]["name"]
                    real_output_delta_chart.options["series"][0]["data"] = delta_chart_options["series"][0]["data"]
                    real_output_delta_chart.options["tooltip"]["formatter"] = delta_chart_options["tooltip"][
                        "formatter"
                    ]
                    real_output_delta_chart.update()
                    analytics_missing_metrics.set_content(
                        build_missing_metrics_markdown(
                            title="Gercek simulasyon sonucu",
                            selected_name=selected_name,
                            missing_metric_ids=missing_metric_ids,
                            null_metric_ids=null_metric_ids,
                            report_path=report_path,
                        )
                    )
                    real_status_items: list[str] = []
                    if report_path:
                        real_status_items.append(f"Comparison raporu bulundu: {report_path}")
                    elif selected_name and selected_name in preparation_only_scenarios:
                        real_status_items.append("Secili senaryo sadece hazirlik asamasinda; gercek sonuc raporu yok.")
                    else:
                        real_status_items.append("Comparison raporu yok.")
                    if missing_metric_ids:
                        real_status_items.append("Eksik metric_id: " + ", ".join(missing_metric_ids))
                    if null_metric_ids:
                        real_status_items.append("Degeri bos metric_id: " + ", ".join(null_metric_ids))
                    if metric_source_status == "unavailable":
                        real_status_items.append(
                            metric_source_message
                            or "Bu comparison su an gercek simulasyon metrikleri yerine sadece CSV farklarini tasiyor."
                        )
                    real_output_status.set_content(
                        build_status_panel_markdown("Gercek Sonuc Veri Durumu", real_status_items)
                    )
                    set_card_empty_hint(
                        real_output_actions,
                        (
                            "Bu grafik icin comparison raporu gerekli. Devam etmek icin `Gercek Karsilastirmali Calistirma` butonunu kullan."
                            if not report_path
                            else (
                                "Comparison raporu var ama peak/cost/zone gibi gercek simulasyon metrikleri uretilmemis."
                                if metric_source_status == "unavailable"
                                else "Grafik bos kalirsa peak, zone ve annual_cost metric'lerinin dolu oldugunu kontrol et."
                            )
                        ),
                    )
                    if not report_path:
                        set_card_status_badge(
                            real_output_actions,
                            "HAZIRLIKTA" if selected_name in preparation_only_scenarios else "GEREKLI",
                        )
                    elif metric_source_status == "unavailable":
                        set_card_status_badge(real_output_actions, "VERI EKSIK")
                    elif not chart_model["has_data"]:
                        set_card_status_badge(real_output_actions, "VERI EKSIK")
                    else:
                        set_card_status_badge(real_output_actions, "GUNCEL")

                    if not selected_name:
                        real_output_info.set_text(
                            "Gercek sonuc grafigi icin once comparison raporu olan bir senaryo secin."
                        )
                        real_output_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Bu alan comparison raporundaki old/new metriklerinden beslenir.",
                                    (
                                        f"Son hazirlikta kalan senaryo: {preparation_only_scenarios[-1]}"
                                        if preparation_only_scenarios
                                        else "Henuz yorum olusturacak bir rapor secilmedi."
                                    ),
                                ],
                            )
                        )
                        return
                    if not chart_model["has_data"]:
                        real_output_info.set_text(
                            f"Secili senaryo: {selected_name} | Gercek old/new ciktilari bulunamadi. "
                            f"Null metrikler: {', '.join(null_metric_ids) if null_metric_ids else '-'} | Rapor: {report_path or '-'}"
                        )
                        real_output_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Bu grafikte gercek old/new degerleri uretilememis.",
                                    (
                                        "Secili senaryo sadece hazirlik asamasinda."
                                        if selected_name in preparation_only_scenarios
                                        else (
                                            "Comparison raporu var ama gercek simulasyon metrikleri uretilmemis; su an yalnizca CSV farklari karsilastiriliyor."
                                            if metric_source_status == "unavailable"
                                            else "Comparison raporundaki peak, cost veya zone metrikleri null olabilir."
                                        )
                                    ),
                                ],
                            )
                        )
                        return
                    max_delta_index = (
                        max(
                            [index for index, value in enumerate(chart_model["delta_values"]) if value is not None],
                            key=lambda index: abs(float(chart_model["delta_values"][index])),
                        )
                        if any(value is not None for value in chart_model["delta_values"])
                        else None
                    )
                    summary = (
                        build_parameter_delta_summary(chart_model, max_delta_index)
                        if max_delta_index is not None
                        else "En belirgin fark hesaplanamadi."
                    )
                    commentary_items = [summary]
                    if "Annual Heating" in chart_model["labels"]:
                        heating_index = list(chart_model["labels"]).index("Annual Heating")
                        heating_comment = build_metric_change_commentary(
                            "Annual Heating",
                            list(chart_model["base_values"])[heating_index],
                            list(chart_model["updated_values"])[heating_index],
                            str(list(chart_model["units"])[heating_index]),
                        )
                        if heating_comment:
                            commentary_items.append(heating_comment)
                    if "Peak Cooling" in chart_model["labels"]:
                        peak_cooling_index = list(chart_model["labels"]).index("Peak Cooling")
                        peak_cooling_comment = build_metric_change_commentary(
                            "Peak Cooling",
                            list(chart_model["base_values"])[peak_cooling_index],
                            list(chart_model["updated_values"])[peak_cooling_index],
                            str(list(chart_model["units"])[peak_cooling_index]),
                        )
                        if peak_cooling_comment:
                            commentary_items.append(peak_cooling_comment)
                    if chart_model["is_normalized"]:
                        real_output_info.set_text(
                            f"Secili senaryo: {selected_name} | Grafik farkli birimler nedeniyle normalize edildi. "
                            f"Tooltip gercek degerleri gosterir. | Eksik metrikler: {', '.join(missing_metric_ids) if missing_metric_ids else '-'} | "
                            f"Null metrikler: {', '.join(null_metric_ids) if null_metric_ids else '-'} | {summary}"
                        )
                    else:
                        real_output_info.set_text(
                            f"Secili senaryo: {selected_name} | Eksik metrikler: {', '.join(missing_metric_ids) if missing_metric_ids else '-'} | "
                            f"Null metrikler: {', '.join(null_metric_ids) if null_metric_ids else '-'} | {summary}"
                        )
                    real_output_commentary.set_content(
                        build_commentary_panel_markdown("Kisa Yorum", commentary_items)
                    )

                def refresh_run_to_run_trend_chart() -> None:
                    comparison_entries = read_comparison_report_entries()
                    metric_id = str(run_trend_metric_select.value or "total_energy").strip() or "total_energy"
                    trend_model = build_run_to_run_trend_model(comparison_entries, metric_id=metric_id)
                    preparation_only_scenarios = list_preparation_only_scenarios(SCENARIO_RUNS_DIR)

                    run_trend_chart.options["xAxis"]["data"] = list(trend_model.get("labels", []))
                    run_trend_chart.options["yAxis"][0]["name"] = str(trend_model.get("unit", "") or "Deger")
                    run_trend_chart.options["series"][0]["data"] = list(trend_model.get("values", []))
                    run_trend_chart.options["series"][1]["data"] = [
                        value if value is not None else 0 for value in list(trend_model.get("deltas", []))
                    ]
                    run_trend_chart.update()
                    trend_status_items: list[str] = []
                    if comparison_entries:
                        trend_status_items.append(
                            f"Comparison raporu sayisi: {len(comparison_entries)}"
                        )
                    else:
                        trend_status_items.append("Trend icin comparison raporu yok.")
                    if preparation_only_scenarios:
                        trend_status_items.append(
                            "Sadece hazirlikta kalan senaryolar: " + ", ".join(preparation_only_scenarios[:4])
                        )
                    run_trend_status.set_content(
                        build_status_panel_markdown("Trend Veri Durumu", trend_status_items)
                    )
                    set_card_empty_hint(
                        run_trend_actions,
                        (
                            "Trend icin en az bir comparison raporu ve secili metrikte scenario_value gerekli."
                            if comparison_entries
                            else "Trend grafigi icin once gercek comparison raporu olustur."
                        ),
                    )
                    set_card_status_badge(
                        run_trend_actions,
                        "GUNCEL" if bool(trend_model.get("has_data")) else ("VERI EKSIK" if comparison_entries else "GEREKLI"),
                    )

                    if not bool(trend_model.get("has_data")):
                        run_trend_info.set_text(
                            "Trend verisi bulunamadi. Bu metrik icin en az bir comparison raporu gerekli."
                        )
                        run_trend_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Trend cizimi icin secili metrikte en az bir scenario_value gerekli.",
                                    "Yeterli run birikmediyse veya metric null ise grafik bos kalir.",
                                ],
                            )
                        )
                        return

                    run_trend_info.set_text(
                        f"Metrik: {trend_model.get('metric_label', metric_id)} | {trend_model.get('summary', '')}"
                    )
                    run_trend_commentary.set_content(
                        build_commentary_panel_markdown(
                            "Kisa Yorum",
                            [
                                f"Secili trend metrigi: {trend_model.get('metric_label', metric_id)}.",
                                str(trend_model.get("summary", "")),
                            ],
                        )
                    )

                def refresh_monthly_energy_chart() -> None:
                    comparison_entries = read_comparison_report_entries()
                    preparation_only_scenarios = list_preparation_only_scenarios(SCENARIO_RUNS_DIR)
                    available_names = [str(item.get("scenario_name", "")).strip() for item in comparison_entries]
                    selected_names = resolve_overlay_scenario_names(
                        available_names,
                        normalize_overlay_selection(overlay_scenarios_select.value),
                    )
                    overlay_model = build_monthly_energy_overlay_model(comparison_entries, selected_names)
                    heating_series = list(overlay_model.get("heating_series", []))
                    cooling_series = list(overlay_model.get("cooling_series", []))

                    def _apply_small_multiple_chart(target_chart: object, series_items: list[dict[str, object]]) -> None:
                        target_chart.options["xAxis"]["data"] = overlay_model["months"]
                        target_chart.options["yAxis"]["name"] = str(overlay_model["unit"])
                        target_chart.options["legend"]["data"] = [item["name"] for item in series_items]
                        target_chart.options["series"] = []
                        for index, item in enumerate(series_items):
                            max_delta_point = (
                                find_max_delta_point(
                                    list(overlay_model["months"]),
                                    list(series_items[0]["values"]) if series_items else [],
                                    [item],
                                )
                                if index > 0
                                else None
                            )
                            series_payload = {
                                "name": item["name"],
                                "type": "line",
                                "smooth": True,
                                "data": item["values"],
                                **build_line_series_style(item["profile"], color=str(item["color"]), width=3),
                            }
                            if max_delta_point:
                                series_payload["markPoint"] = {
                                    "symbol": "pin",
                                    "symbolSize": 34,
                                    "data": [
                                        {
                                            "name": "Max Delta",
                                            "coord": [
                                                list(overlay_model["months"])[int(max_delta_point["index"])],
                                                float(max_delta_point["series_value"]),
                                            ],
                                            "value": f"{float(max_delta_point['delta']):.2f}",
                                            "label": {"formatter": "Max Delta"},
                                        }
                                    ],
                                }
                            target_chart.options["series"].append(series_payload)
                        target_chart.update()

                    _apply_small_multiple_chart(monthly_heating_chart, heating_series)
                    _apply_small_multiple_chart(monthly_cooling_chart, cooling_series)
                    monthly_status_items: list[str] = []
                    if selected_names:
                        monthly_status_items.append("Secili overlay: " + ", ".join(selected_names))
                    else:
                        monthly_status_items.append("Overlay icin senaryo secilmedi.")
                    if preparation_only_scenarios:
                        monthly_status_items.append(
                            "Sadece hazirlikta kalan senaryolar: " + ", ".join(preparation_only_scenarios[:4])
                        )
                    monthly_energy_status.set_content(
                        build_status_panel_markdown("Aylik Overlay Veri Durumu", monthly_status_items)
                    )
                    set_card_empty_hint(
                        monthly_actions,
                        (
                            "Aylik overlay icin senaryo sec ve monthly_heating_cooling metric'inin dolu oldugunu kontrol et."
                            if selected_names
                            else "Bu grafik icin overlay listesinde en az bir senaryo sec."
                        ),
                    )
                    set_card_status_badge(
                        monthly_actions,
                        "GUNCEL" if overlay_model["has_data"] else ("VERI EKSIK" if selected_names else "GEREKLI"),
                    )

                    if not selected_names:
                        monthly_energy_info.set_text(
                            "Aylik grafik icin overlay listesinde en az bir senaryo secin."
                        )
                        monthly_energy_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Heating ve cooling overlay'i cizmek icin en az bir scenario secilmeli.",
                                    "Secim yoksa small-multiple panelleri bos kalir.",
                                ],
                            )
                        )
                        return
                    if not overlay_model["has_data"]:
                        monthly_energy_info.set_text(
                            f"Secili overlay: {', '.join(selected_names)} | Aylik heating/cooling verisi bulunamadi."
                        )
                        monthly_energy_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Secili senaryolarda monthly_heating_cooling metric'i eksik ya da bos.",
                                    "Comparison raporu olmayan senaryolar overlay serisine katkı vermez.",
                                ],
                            )
                        )
                        return
                    heating_max_delta = (
                        find_max_delta_point(
                            list(overlay_model["months"]),
                            list(heating_series[0]["values"]),
                            heating_series[1:],
                        )
                        if len(heating_series) > 1
                        else None
                    )
                    cooling_max_delta = (
                        find_max_delta_point(
                            list(overlay_model["months"]),
                            list(cooling_series[0]["values"]),
                            cooling_series[1:],
                        )
                        if len(cooling_series) > 1
                        else None
                    )
                    lead_profile = (
                        heating_series[1]["profile"]
                        if len(heating_series) > 1 and isinstance(heating_series[1].get("profile"), dict)
                        else get_base_scenario_visual_profile()
                    )
                    selected_text = ", ".join(selected_names)
                    monthly_energy_info.set_text(
                        f"Secili overlay senaryolari: {selected_text} | "
                        f"Sunum: Small Multiples (Heating + Cooling ayri panel) | "
                        f"{build_overlay_explanation('aylik heating + cooling', get_base_scenario_visual_profile(), lead_profile)} | "
                        f"{build_delta_summary_text('Heating overlay', heating_max_delta, str(overlay_model['unit']))} | "
                        f"{build_delta_summary_text('Cooling overlay', cooling_max_delta, str(overlay_model['unit']))}"
                    )
                    monthly_energy_commentary.set_content(
                        build_commentary_panel_markdown(
                            "Kisa Yorum",
                            [
                                build_delta_summary_text(
                                    "Heating overlay",
                                    heating_max_delta,
                                    str(overlay_model["unit"]),
                                ),
                                build_delta_summary_text(
                                    "Cooling overlay",
                                    cooling_max_delta,
                                    str(overlay_model["unit"]),
                                ),
                            ],
                        )
                    )

                def refresh_zone_temperature_chart() -> None:
                    comparison_entries = read_comparison_report_entries()
                    preparation_only_scenarios = list_preparation_only_scenarios(SCENARIO_RUNS_DIR)
                    reports_by_name = {
                        str(item.get("scenario_name", "")).strip(): item
                        for item in comparison_entries
                        if str(item.get("scenario_name", "")).strip()
                    }
                    available_names = [str(item.get("scenario_name", "")).strip() for item in comparison_entries]
                    selected_names = resolve_overlay_scenario_names(
                        available_names,
                        normalize_overlay_selection(overlay_scenarios_select.value),
                    )
                    zone_choice = str(zone_temperature_select.value or "").strip()
                    overlay_model = build_zone_temperature_overlay_model(
                        comparison_entries,
                        selected_names,
                        selected_zone=zone_choice,
                    )

                    zone_temperature_select.options = overlay_model["zone_options"]
                    zone_temperature_select.update()
                    if overlay_model["selected_zone"] != zone_choice:
                        zone_temperature_select.set_value(overlay_model["selected_zone"])

                    fallback_used = False
                    if not list(overlay_model.get("time_labels", [])) and selected_names:
                        fallback_used = True
                        fallback_label = "Last Known"
                        fallback_base_value = None
                        fallback_zone = str(overlay_model.get("selected_zone", "") or "")
                        fallback_scenarios: list[dict[str, object]] = []
                        for index, series in enumerate(list(overlay_model.get("scenario_series", []))):
                            scenario_name = selected_names[index] if index < len(selected_names) else ""
                            report = reports_by_name.get(scenario_name, {})
                            metrics_rows = (
                                list(report.get("metrics", []))
                                if isinstance(report, dict)
                                else []
                            )
                            last_known = build_zone_last_known_point_model(
                                metrics_rows,
                                selected_zone=str(overlay_model.get("selected_zone", "") or ""),
                            )
                            if not fallback_zone:
                                fallback_zone = str(last_known.get("zone", "") or "")
                            if index == 0:
                                fallback_base_value = try_parse_number(last_known.get("base_value"))

                            scenario_point = try_parse_number(last_known.get("scenario_value"))
                            fallback_scenarios.append(
                                {
                                    **series,
                                    "values": [scenario_point],
                                }
                            )

                        overlay_model = {
                            **overlay_model,
                            "selected_zone": fallback_zone,
                            "time_labels": [fallback_label],
                            "base_series": {
                                **dict(overlay_model.get("base_series", {})),
                                "values": [fallback_base_value],
                            },
                            "scenario_series": fallback_scenarios,
                            "has_data": (
                                fallback_base_value is not None
                                or any(
                                    try_parse_number(item["values"][0]) is not None
                                    for item in fallback_scenarios
                                    if isinstance(item, dict)
                                    and isinstance(item.get("values"), list)
                                    and item.get("values")
                                )
                            ),
                        }

                    zone_temperature_chart.options["xAxis"]["data"] = overlay_model["time_labels"]
                    zone_temperature_chart.options["yAxis"]["name"] = str(overlay_model["unit"])
                    zone_temperature_chart.options["legend"]["data"] = [
                        overlay_model["base_series"]["name"],
                        *[item["name"] for item in overlay_model["scenario_series"]],
                    ]
                    zone_temperature_chart.options["series"] = []
                    zone_temperature_chart.options["series"].append(
                        {
                            "name": overlay_model["base_series"]["name"],
                            "type": "line",
                            "smooth": True,
                            "data": overlay_model["base_series"]["values"],
                            "markArea": {
                                "silent": True,
                                "itemStyle": {"color": "rgba(16,185,129,0.12)"},
                                "data": [
                                    [
                                        {"yAxis": COMFORT_BAND_MIN_C},
                                        {"yAxis": COMFORT_BAND_MAX_C},
                                    ]
                                ],
                            },
                            **build_line_series_style(
                                overlay_model["base_series"]["profile"],
                                color=str(overlay_model["base_series"]["color"]),
                                width=3,
                            ),
                        }
                    )
                    for item in overlay_model["scenario_series"]:
                        max_delta_point = find_max_delta_point(
                            list(overlay_model["time_labels"]),
                            list(overlay_model["base_series"]["values"]),
                            [item],
                        )
                        series_payload = {
                            "name": item["name"],
                            "type": "line",
                            "smooth": True,
                            "data": item["values"],
                            **build_line_series_style(
                                item["profile"],
                                color=str(item["color"]),
                                width=3,
                            ),
                        }
                        if max_delta_point:
                            series_payload["markPoint"] = {
                                "symbol": "pin",
                                "symbolSize": 40,
                                "data": [
                                    {
                                        "name": "Max Delta",
                                        "coord": [
                                            list(overlay_model["time_labels"])[int(max_delta_point["index"])],
                                            float(max_delta_point["series_value"]),
                                        ],
                                        "value": f"{float(max_delta_point['delta']):.2f}",
                                        "label": {"formatter": "Max Delta"},
                                    }
                                ],
                            }
                        zone_temperature_chart.options["series"].append(series_payload)
                    zone_temperature_chart.update()
                    zone_status_items: list[str] = []
                    if selected_names:
                        zone_status_items.append("Secili overlay: " + ", ".join(selected_names))
                    else:
                        zone_status_items.append("Zone overlay icin senaryo secilmedi.")
                    if fallback_used:
                        zone_status_items.append("Zaman serisi bulunamadi; son bilinen tek nokta kullanildi.")
                    if preparation_only_scenarios:
                        zone_status_items.append(
                            "Sadece hazirlikta kalan senaryolar: " + ", ".join(preparation_only_scenarios[:4])
                        )
                    zone_temperature_status.set_content(
                        build_status_panel_markdown("Zone Overlay Veri Durumu", zone_status_items)
                    )
                    set_card_empty_hint(
                        zone_temperature_actions,
                        (
                            "Zone overlay icin zone_temperatures metric'i gerekli; comparison raporunu ve zone secimini kontrol et."
                            if selected_names
                            else "Bu grafik icin overlay listesinde en az bir senaryo sec."
                        ),
                    )
                    set_card_status_badge(
                        zone_temperature_actions,
                        "GUNCEL" if overlay_model["has_data"] else ("VERI EKSIK" if selected_names else "GEREKLI"),
                    )

                    if not selected_names:
                        zone_temperature_info.set_text(
                            "Sicaklik grafigi icin overlay listesinde en az bir senaryo secin."
                        )
                        zone_temperature_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Zone sicaklik overlay'i icin en az bir scenario secilmeli.",
                                    "Secim yoksa zone serileri olusturulmaz.",
                                ],
                            )
                        )
                        return
                    if not overlay_model["zone_options"]:
                        zone_temperature_info.set_text(
                            f"Secili overlay: {', '.join(selected_names)} | Zone sicaklik verisi bulunamadi."
                        )
                        zone_temperature_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Secili senaryolarda zone_temperatures metric'i bulunamadi.",
                                    "Bu durumda zone listesi ve overlay serisi bos kalir.",
                                ],
                            )
                        )
                        return
                    if not overlay_model["has_data"]:
                        zone_temperature_info.set_text(
                            f"Secili overlay: {', '.join(selected_names)} | {overlay_model['selected_zone']} icin sicaklik serisi eksik."
                        )
                        zone_temperature_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    f"{overlay_model['selected_zone']} icin sicaklik serisi eksik.",
                                    (
                                        "Fallback noktasi da uretilemedi."
                                        if not fallback_used
                                        else "Sadece son bilinen nokta ile sinirli bir gosterim yapildi."
                                    ),
                                ],
                            )
                        )
                        return
                    max_delta_point = find_max_delta_point(
                        list(overlay_model["time_labels"]),
                        list(overlay_model["base_series"]["values"]),
                        list(overlay_model["scenario_series"]),
                    )
                    lead_profile = (
                        overlay_model["scenario_series"][0]["profile"]
                        if overlay_model["scenario_series"]
                        and isinstance(overlay_model["scenario_series"][0].get("profile"), dict)
                        else get_base_scenario_visual_profile()
                    )
                    fallback_note = (
                        "Zaman serisi bulunamadigi icin son bilinen tek nokta gosteriliyor. | "
                        if fallback_used
                        else ""
                    )
                    zone_temperature_info.set_text(
                        f"Secili overlay senaryolari: {', '.join(selected_names)} | Zone: {overlay_model['selected_zone']} | "
                        + fallback_note
                        +
                        f"{build_overlay_explanation('zone temperature', get_base_scenario_visual_profile(), lead_profile, overlay_model['selected_zone'])} | "
                        f"{build_delta_summary_text('Zone temperature overlay', max_delta_point, str(overlay_model['unit']))}"
                    )
                    zone_temperature_commentary.set_content(
                        build_commentary_panel_markdown(
                            "Kisa Yorum",
                            [
                                (
                                    "Zaman serisi olmadigi icin son bilinen nokta gosteriliyor."
                                    if fallback_used
                                    else "Secili zone icin zaman serisi overlay'i olusturuldu."
                                ),
                                build_delta_summary_text(
                                    "Zone temperature overlay",
                                    max_delta_point,
                                    str(overlay_model["unit"]),
                                ),
                            ],
                        )
                    )

                def refresh_advanced_analysis() -> None:
                    analysis_state = get_selected_scenario_analysis_state()
                    selected_name = str(analysis_state["selected_name"])
                    metrics_rows: list[dict[str, object]] = list(analysis_state["metrics_rows"])
                    missing_metric_ids = list(analysis_state.get("missing_metric_ids", []))
                    null_metric_ids = list(analysis_state.get("null_metric_ids", []))
                    report_path = str(analysis_state.get("report_path", ""))
                    preparation_only_scenarios = list(analysis_state.get("preparation_only_scenarios", []))

                    if not selected_name or not metrics_rows:
                        advanced_analysis_info.set_text(
                            "Zengin analiz icin once karsilastirma raporu olan bir senaryo secin."
                        )
                        advanced_analysis_status.set_content(
                            build_status_panel_markdown(
                                "Advanced Analysis Veri Durumu",
                                [
                                    "Comparison raporu secilmedi.",
                                    (
                                        "Sadece hazirlikta kalan senaryolar: "
                                        + ", ".join(preparation_only_scenarios[:4])
                                        if preparation_only_scenarios
                                        else "Analiz icin metrics satiri yok."
                                    ),
                                ],
                            )
                        )
                        advanced_analysis_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                [
                                    "Zone heatmap ve detayli yorumlar icin dolu bir comparison raporu gerekli.",
                                    "Veri bekleniyor.",
                                ],
                            )
                        )
                        advanced_analysis_markdown.set_content("Veri bekleniyor.")
                        zone_heatmap_info.set_text(
                            "Zone bazinda sicaklik sapmasi ve konfor saatleri isi haritasi."
                        )
                        zone_heatmap_status.set_content(
                            build_status_panel_markdown(
                                "Zone Heatmap Veri Durumu",
                                ["Heatmap icin zone bazli veri bulunamadi."],
                            )
                        )
                        set_card_empty_hint(
                            zone_heatmap_actions,
                            "Zone heatmap icin comparison raporunda zone bazli konfor ve sicaklik verileri gerekli.",
                        )
                        set_card_status_badge(zone_heatmap_actions, "GEREKLI")
                        set_card_empty_hint(
                            advanced_actions,
                            "Advanced analysis icin once comparison raporu olan bir senaryo sec.",
                        )
                        set_card_status_badge(advanced_actions, "GEREKLI")
                        zone_heatmap_commentary.set_content(
                            build_commentary_panel_markdown(
                                "Kisa Yorum",
                                ["Zone bazli konfor ve sicaklik sapmasi verisi bekleniyor."],
                            )
                        )
                        zone_heatmap_chart.options["xAxis"]["data"] = []
                        zone_heatmap_chart.options["series"][0]["data"] = []
                        zone_heatmap_chart.update()
                        return

                    monthly_model = build_monthly_energy_chart_model(metrics_rows)
                    seasonal_model = build_seasonal_energy_analysis(monthly_model)
                    peak_model = build_peak_load_analysis(metrics_rows)
                    zone_model = build_zone_portfolio_analysis(metrics_rows)
                    heatmap_model = build_zone_heatmap_model(
                        zone_model,
                        metric_mode=str(zone_heatmap_metric_select.value or "temperature_vs_comfort"),
                    )

                    def fmt(value: object, suffix: str = "") -> str:
                        number = try_parse_number(value)
                        if number is None:
                            return "-"
                        return f"{float(number):.2f}{suffix}"

                    heat_loss_text = "-"
                    most_heat_loss_zone = zone_model.get("most_heat_loss_zone")
                    if isinstance(most_heat_loss_zone, dict):
                        heat_loss_text = (
                            f"{most_heat_loss_zone.get('zone', '-')} "
                            f"(ortalama sicaklik degisimi: {fmt(most_heat_loss_zone.get('avg_delta'), ' C')})"
                        )

                    overheating_text = "-"
                    most_overheating_zone = zone_model.get("most_overheating_zone")
                    if isinstance(most_overheating_zone, dict):
                        overheating_text = (
                            f"{most_overheating_zone.get('zone', '-')} "
                            f"(asiri sicak saat: {int(most_overheating_zone.get('scenario_hot_hours', 0))})"
                        )

                    zone_lines: list[str] = []
                    zone_rows = list(zone_model.get("zones", []))
                    for zone_row in zone_rows[:6]:
                        if not isinstance(zone_row, dict):
                            continue
                        zone_lines.append(
                            f"- {zone_row.get('zone', '-')} | "
                            f"ortalama (Old/New): {fmt(zone_row.get('base_avg'), ' C')} / {fmt(zone_row.get('scenario_avg'), ' C')} | "
                            f"konfor saati: {int(zone_row.get('scenario_in_band_hours', 0))} | "
                            f"stability std: {fmt(zone_row.get('scenario_stability_std'), ' C')}"
                        )

                    season_lines: list[str] = []
                    for season_row in list(seasonal_model.get("seasons", [])):
                        if not isinstance(season_row, dict):
                            continue
                        season_name = {
                            "kis": "Kis",
                            "yaz": "Yaz",
                            "gecis": "Gecis Mevsimi",
                        }.get(str(season_row.get("season", "")), str(season_row.get("season", "-")))
                        season_lines.append(
                            f"- {season_name}: {fmt(season_row.get('base_total'))} -> {fmt(season_row.get('scenario_total'))} {seasonal_model.get('unit', 'kWh')}"
                        )

                    advanced_analysis_info.set_text(
                        f"Secili senaryo: {selected_name} | Zone bazli + peak load + konfor + sezon analizi guncellendi."
                    )
                    zone_heatmap_status_items = [
                        f"Secili senaryo: {selected_name}",
                        f"Heatmap metrigi: {str(zone_heatmap_metric_select.value or 'temperature_vs_comfort')}",
                    ]
                    if missing_metric_ids:
                        zone_heatmap_status_items.append("Eksik metric_id: " + ", ".join(missing_metric_ids))
                    if null_metric_ids:
                        zone_heatmap_status_items.append("Degeri bos metric_id: " + ", ".join(null_metric_ids))
                    zone_heatmap_status.set_content(
                        build_status_panel_markdown("Zone Heatmap Veri Durumu", zone_heatmap_status_items)
                    )
                    set_card_empty_hint(
                        zone_heatmap_actions,
                        "Heatmap bos kalirsa zone_temperatures metric'ini ve secili heatmap modunu kontrol et.",
                    )
                    set_card_status_badge(
                        zone_heatmap_actions,
                        "GUNCEL" if list(heatmap_model.get("data", [])) else "VERI EKSIK",
                    )
                    zone_heatmap_info.set_text(
                        "Zone bazinda sicaklik sapmasi ve konfor saatleri isi haritasi. "
                        + str(heatmap_model.get("summary", ""))
                    )
                    zone_heatmap_chart.options["xAxis"]["data"] = list(
                        heatmap_model.get("x_labels", [])
                    )
                    zone_heatmap_chart.options["yAxis"]["data"] = list(
                        heatmap_model.get("y_labels", ["Avg Delta (C)", "Comfort Hours"])
                    )
                    zone_heatmap_chart.options["tooltip"] = {
                        "position": "top",
                        "formatter": (
                            "function (params) {"
                            "if (!params || !params.value || params.value.length < 5) return '';"
                            "const raw = params.value[3];"
                            "const unit = params.value[4] || '';"
                            "const display = (raw === null || raw === undefined) ? '-' : Number(raw).toFixed(2) + ' ' + unit;"
                            "return params.marker + ' ' + params.name + '<br/>' + display;"
                            "}"
                        ),
                    }
                    zone_heatmap_chart.options["series"][0]["label"] = {
                        "show": True,
                        "formatter": (
                            "function (params) {"
                            "if (!params || !params.value || params.value.length < 5) return '-';"
                            "const raw = params.value[3];"
                            "const unit = params.value[4] || '';"
                            "if (raw === null || raw === undefined) return '-';"
                            "return Number(raw).toFixed(1) + ' ' + unit;"
                            "}"
                        ),
                    }
                    zone_heatmap_chart.options["series"][0]["data"] = list(
                        heatmap_model.get("data", [])
                    )
                    zone_heatmap_chart.update()
                    zone_heatmap_commentary.set_content(
                        build_commentary_panel_markdown(
                            "Kisa Yorum",
                            [
                                str(heatmap_model.get("summary", "Heatmap ozeti olusturulamadi.")),
                                f"En kritik isi kaybi zone'u: {heat_loss_text}",
                                f"En cok asiri isinma: {overheating_text}",
                            ],
                        )
                    )
                    advanced_analysis_status_items = [
                        f"Secili senaryo: {selected_name}",
                        (f"Comparison raporu: {report_path}" if report_path else "Comparison raporu yolu yok."),
                    ]
                    if missing_metric_ids:
                        advanced_analysis_status_items.append("Eksik metric_id: " + ", ".join(missing_metric_ids))
                    if null_metric_ids:
                        advanced_analysis_status_items.append("Degeri bos metric_id: " + ", ".join(null_metric_ids))
                    advanced_analysis_status.set_content(
                        build_status_panel_markdown(
                            "Advanced Analysis Veri Durumu",
                            advanced_analysis_status_items,
                        )
                    )
                    set_card_empty_hint(
                        advanced_actions,
                        "Bu panel peak, seasonal ve zone metric'lerinden uretilir; eksik/null metric'leri kontrol et.",
                    )
                    set_card_status_badge(
                        advanced_actions,
                        "GUNCEL" if metrics_rows else "VERI EKSIK",
                    )
                    advanced_analysis_markdown.set_content(
                        "\n".join(
                            [
                                "**Zone Bazli Analiz**",
                                f"- En cok isi kaybeden zone: {heat_loss_text}",
                                f"- En cok asiri isinma olan zone: {overheating_text}",
                                *(
                                    zone_lines
                                    if zone_lines
                                    else ["- Zone bazli detay verisi bulunamadi."]
                                ),
                                "",
                                "**Peak Load Analizi**",
                                f"- Maksimum heating yuku (Old/New): {fmt(peak_model.get('peak_heating_base'))} / {fmt(peak_model.get('peak_heating_scenario'))} {peak_model.get('unit', 'kW')}",
                                f"- Maksimum cooling yuku (Old/New): {fmt(peak_model.get('peak_cooling_base'))} / {fmt(peak_model.get('peak_cooling_scenario'))} {peak_model.get('unit', 'kW')}",
                                "",
                                "**Konfor Analizi**",
                                f"- Konfor bandi: {zone_model.get('comfort_min_c', COMFORT_BAND_MIN_C):.0f}-{zone_model.get('comfort_max_c', COMFORT_BAND_MAX_C):.0f} C",
                                f"- Asiri sicak saat toplam (New): {sum(int(row.get('scenario_hot_hours', 0)) for row in zone_rows if isinstance(row, dict))}",
                                f"- Asiri soguk saat toplam (New): {sum(int(row.get('scenario_cold_hours', 0)) for row in zone_rows if isinstance(row, dict))}",
                                f"- Konfor araliginda gecen sure toplam (New): {sum(int(row.get('scenario_in_band_hours', 0)) for row in zone_rows if isinstance(row, dict))}",
                                "",
                                "**Sezon Bazli Analiz**",
                                *(
                                    season_lines
                                    if season_lines
                                    else ["- Sezon bazli enerji verisi bulunamadi."]
                                ),
                            ]
                        )
                    )
                    advanced_analysis_commentary.set_content(
                        build_commentary_panel_markdown(
                            "Kisa Yorum",
                            [
                                f"En kritik isi kaybi zone'u: {heat_loss_text}",
                                f"Asiri isinma acisindan one cikan zone: {overheating_text}",
                                (
                                    season_lines[0].replace("- ", "")
                                    if season_lines
                                    else "Mevsimsel enerji ozeti olusturulamadi."
                                ),
                            ],
                        )
                    )

                def refresh_comparison() -> None:
                    manifests_by_name = {
                        item.get("scenario_name"): item for item in read_manifest_entries()
                    }
                    reports_by_name = {
                        item.get("scenario_name"): item for item in read_comparison_report_entries()
                    }
                    left = manifests_by_name.get(comparison_left.value)
                    right = manifests_by_name.get(comparison_right.value)
                    if not left or not right:
                        comparison_markdown.set_content("Karsilastirma icin iki senaryo secin.")
                        return

                    left_report = reports_by_name.get(comparison_left.value, {})
                    right_report = reports_by_name.get(comparison_right.value, {})
                    left_summary = {}
                    right_summary = {}
                    if isinstance(left_report, dict):
                        left_summary = (
                            left_report.get("comparison_model", {}).get("summary", {})
                            if isinstance(left_report.get("comparison_model", {}), dict)
                            else {}
                        )
                    if isinstance(right_report, dict):
                        right_summary = (
                            right_report.get("comparison_model", {}).get("summary", {})
                            if isinstance(right_report.get("comparison_model", {}), dict)
                            else {}
                        )

                    difference = int(left.get("changed_field_count", 0)) - int(
                        right.get("changed_field_count", 0)
                    )
                    comparison_markdown.set_content(
                        "\n".join(
                            [
                                f"**Sol:** {left.get('scenario_name', '-')}",
                                f"- Degisen alan: {left.get('changed_field_count', 0)}",
                                f"- Islem sayisi: {left.get('operation_count', 0)}",
                                *_format_comparison_highlight(left_summary, "most_critical"),
                                *_format_comparison_highlight(left_summary, "best_improvement"),
                                *_format_comparison_highlight(left_summary, "worst_worsening"),
                                "",
                                f"**Sag:** {right.get('scenario_name', '-')}",
                                f"- Degisen alan: {right.get('changed_field_count', 0)}",
                                f"- Islem sayisi: {right.get('operation_count', 0)}",
                                *_format_comparison_highlight(right_summary, "most_critical"),
                                *_format_comparison_highlight(right_summary, "best_improvement"),
                                *_format_comparison_highlight(right_summary, "worst_worsening"),
                                "",
                                f"**Fark:** {difference}",
                            ]
                        )
                    )

                def refresh_metrics() -> None:
                    manifests = read_manifest_entries()
                    total_scenarios_value.set_text(str(len(manifests)))
                    total_changes_value.set_text(
                        str(sum(int(item.get("changed_field_count", 0)) for item in manifests))
                    )
                    last_scenario_value.set_text(manifests[-1].get("scenario_name", "-") if manifests else "-")

                    analytics_info.set_text(f"Karsilastirilan senaryo sayisi: {len(manifests)}")

                    scenario_names = [item.get("scenario_name", "-") for item in manifests]
                    change_values = [int(item.get("changed_field_count", 0)) for item in manifests]
                    operation_values = [int(item.get("operation_count", 0)) for item in manifests]

                    changes_chart.options["xAxis"]["data"] = scenario_names
                    changes_chart.options["series"][0]["data"] = change_values
                    changes_chart.options["series"][1]["data"] = operation_values
                    changes_chart.update()

                    flow_chart.options["xAxis"]["data"] = scenario_names
                    flow_chart.options["series"][0]["data"] = change_values
                    flow_chart.update()

                    comparison_left.options = scenario_names
                    comparison_left.update()
                    comparison_right.options = scenario_names
                    comparison_right.update()
                    analysis_scenario_select.options = scenario_names
                    analysis_scenario_select.update()
                    overlay_scenarios_select.options = scenario_names
                    overlay_scenarios_select.update()
                    if scenario_names and comparison_left.value not in scenario_names:
                        comparison_left.set_value(scenario_names[0])
                    if scenario_names and analysis_scenario_select.value not in scenario_names:
                        analysis_scenario_select.set_value(scenario_names[0])
                    if len(scenario_names) > 1 and comparison_right.value not in scenario_names:
                        comparison_right.set_value(scenario_names[1])
                    elif scenario_names and comparison_right.value not in scenario_names:
                        comparison_right.set_value(scenario_names[0])
                    resolved_overlay = resolve_overlay_scenario_names(
                        scenario_names,
                        normalize_overlay_selection(overlay_scenarios_select.value),
                    )
                    if resolved_overlay != normalize_overlay_selection(overlay_scenarios_select.value):
                        overlay_scenarios_select.set_value(resolved_overlay)

                    refresh_all_analytics(update_timestamp=False)
                    refresh_cost_tab()
                    update_analysis_toolbar(has_chart_data=bool(read_comparison_report_entries()))

                comparison_left.on_value_change(
                    lambda _: (
                        refresh_comparison(),
                        refresh_energy_performance_chart(),
                        refresh_run_to_run_trend_chart(),
                        refresh_real_output_chart(),
                        refresh_monthly_energy_chart(),
                        refresh_zone_temperature_chart(),
                        refresh_advanced_analysis(),
                        update_analysis_toolbar(has_chart_data=bool(get_selected_scenario_analysis_state().get("metrics_rows"))),
                    )
                )
                comparison_right.on_value_change(lambda _: refresh_comparison())
                run_trend_metric_select.on_value_change(lambda _: refresh_run_to_run_trend_chart())
                zone_heatmap_metric_select.on_value_change(lambda _: refresh_advanced_analysis())
                overlay_scenarios_select.on_value_change(
                    lambda _: (
                        refresh_monthly_energy_chart(),
                        refresh_zone_temperature_chart(),
                    )
                )
                zone_temperature_select.on_value_change(
                    lambda _: (
                        refresh_zone_temperature_chart(),
                        refresh_advanced_analysis(),
                    )
                )
                analysis_scenario_select.on_value_change(
                    lambda _: refresh_all_analytics()
                )
                refresh_all_button.on("click", lambda _: refresh_all_analytics())
                energy_actions["refresh_button"].on("click", lambda _: refresh_energy_performance_chart())
                real_output_actions["refresh_button"].on("click", lambda _: refresh_real_output_chart())
                run_trend_actions["refresh_button"].on("click", lambda _: refresh_run_to_run_trend_chart())
                monthly_actions["refresh_button"].on("click", lambda _: refresh_monthly_energy_chart())
                zone_temperature_actions["refresh_button"].on("click", lambda _: refresh_zone_temperature_chart())
                zone_heatmap_actions["refresh_button"].on("click", lambda _: refresh_advanced_analysis())
                advanced_actions["refresh_button"].on("click", lambda _: refresh_advanced_analysis())
                energy_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        energy_actions,
                        str(energy_actions["why_empty_label"].text or "Bu grafik icin comparison raporu gerekli."),
                    ),
                )
                real_output_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        real_output_actions,
                        str(real_output_actions["why_empty_label"].text or "Bu grafik icin comparison raporu gerekli."),
                    ),
                )
                run_trend_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        run_trend_actions,
                        str(run_trend_actions["why_empty_label"].text or "Trend icin comparison serisi gerekli."),
                    ),
                )
                monthly_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        monthly_actions,
                        str(monthly_actions["why_empty_label"].text or "Overlay secimi gerekli."),
                    ),
                )
                zone_temperature_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        zone_temperature_actions,
                        str(zone_temperature_actions["why_empty_label"].text or "Zone ve comparison verisi gerekli."),
                    ),
                )
                zone_heatmap_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        zone_heatmap_actions,
                        str(zone_heatmap_actions["why_empty_label"].text or "Zone heatmap verisi gerekli."),
                    ),
                )
                advanced_actions["why_empty_button"].on(
                    "click",
                    lambda _: set_card_empty_hint(
                        advanced_actions,
                        str(advanced_actions["why_empty_label"].text or "Advanced analysis icin comparison gerekli."),
                    ),
                )
                refresh_metrics()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="CSV Izleme Paneli",
        port=find_available_port(8090),
        reload=False,
    )
