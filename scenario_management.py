from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path

from build_simulation_output import build_output_paths
from scenario_builder import sanitize_scenario_name


SIMULATION_OUTPUT_ROOT = Path("simulation_outputs")
_RISK_ORDER = {
    "low": 1,
    "minor": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
    "severe": 4,
}


def build_scenario_output_paths(input_dataset: str, scenario_name: str) -> tuple[str, str]:
    output_path, log_path, _ = build_output_paths(
        scenario_name,
        Path(str(input_dataset or "")),
        SIMULATION_OUTPUT_ROOT,
    )
    return output_path.as_posix(), log_path.as_posix()


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ensure_management_metadata(
    scenario: dict[str, object],
    scenario_path: str | Path | None = None,
    timestamp: str | None = None,
) -> dict[str, object]:
    normalized = deepcopy(scenario)
    management = normalized.get("management", {})
    if not isinstance(management, dict):
        management = {}

    scenario_name = str(normalized.get("scenario_name", "")).strip() or "scenario"
    scenario_path_value = str(scenario_path or management.get("scenario_path") or "").strip()
    current_timestamp = timestamp or str(management.get("updated_at") or "").strip() or _utc_timestamp()
    version_group = str(management.get("version_group", "")).strip() or sanitize_scenario_name(scenario_name)
    history = management.get("history", [])
    if not isinstance(history, list):
        history = []

    if not history:
        history = [
            {
                "event": "created",
                "scenario_name": scenario_name,
                "scenario_path": scenario_path_value,
                "timestamp": current_timestamp,
            }
        ]

    version_index = int(management.get("version_index", 1) or 1)
    normalized["management"] = {
        "version_group": version_group,
        "version_index": version_index,
        "scenario_path": scenario_path_value,
        "created_at": str(management.get("created_at", current_timestamp) or current_timestamp),
        "updated_at": current_timestamp,
        "history": history,
    }
    return normalized


def build_copied_scenario_definition(
    scenario: dict[str, object],
    source_path: str | Path,
    new_name: str,
    timestamp: str | None = None,
) -> dict[str, object]:
    current_timestamp = timestamp or _utc_timestamp()
    normalized = ensure_management_metadata(scenario, source_path, current_timestamp)
    copied = deepcopy(normalized)
    scenario_name = sanitize_scenario_name(new_name)
    copied["scenario_name"] = scenario_name
    output_path, log_path = build_scenario_output_paths(str(copied.get("input", "")), scenario_name)
    copied["output"] = output_path
    copied["log_output"] = log_path

    management = copied.get("management", {})
    history = list(management.get("history", [])) if isinstance(management, dict) else []
    source_name = str(normalized.get("scenario_name", "")).strip()
    history.append(
        {
            "event": "copied",
            "scenario_name": scenario_name,
            "source_scenario_name": source_name,
            "source_scenario_path": str(source_path),
            "timestamp": current_timestamp,
        }
    )
    copied["management"] = {
        "version_group": str(management.get("version_group", "")).strip() or sanitize_scenario_name(source_name),
        "version_index": int(management.get("version_index", 1) or 1) + 1,
        "scenario_path": "",
        "created_at": str(management.get("created_at", current_timestamp) or current_timestamp),
        "updated_at": current_timestamp,
        "history": history,
    }
    return copied


def build_renamed_scenario_definition(
    scenario: dict[str, object],
    source_path: str | Path,
    new_name: str,
    timestamp: str | None = None,
) -> dict[str, object]:
    current_timestamp = timestamp or _utc_timestamp()
    normalized = ensure_management_metadata(scenario, source_path, current_timestamp)
    renamed = deepcopy(normalized)
    previous_name = str(renamed.get("scenario_name", "")).strip()
    scenario_name = sanitize_scenario_name(new_name)
    renamed["scenario_name"] = scenario_name
    output_path, log_path = build_scenario_output_paths(str(renamed.get("input", "")), scenario_name)
    renamed["output"] = output_path
    renamed["log_output"] = log_path

    management = renamed.get("management", {})
    history = list(management.get("history", [])) if isinstance(management, dict) else []
    history.append(
        {
            "event": "renamed",
            "scenario_name": scenario_name,
            "previous_scenario_name": previous_name,
            "source_scenario_path": str(source_path),
            "timestamp": current_timestamp,
        }
    )
    renamed["management"] = {
        "version_group": str(management.get("version_group", "")).strip() or sanitize_scenario_name(previous_name),
        "version_index": int(management.get("version_index", 1) or 1) + 1,
        "scenario_path": "",
        "created_at": str(management.get("created_at", current_timestamp) or current_timestamp),
        "updated_at": current_timestamp,
        "history": history,
    }
    return renamed


def build_version_history_entries(
    scenario_entries: list[dict[str, object]],
    selected_path: str | Path | None,
) -> list[dict[str, object]]:
    normalized_selected = str(selected_path or "").strip()
    selected_entry = next(
        (item for item in scenario_entries if str(item.get("path", "")).strip() == normalized_selected),
        None,
    )
    if not isinstance(selected_entry, dict):
        return []

    management = selected_entry.get("management", {})
    version_group = ""
    if isinstance(management, dict):
        version_group = str(management.get("version_group", "")).strip()
    if not version_group:
        version_group = sanitize_scenario_name(str(selected_entry.get("scenario_name", "")).strip())

    related_entries: list[dict[str, object]] = []
    for item in scenario_entries:
        candidate_management = item.get("management", {})
        candidate_group = ""
        if isinstance(candidate_management, dict):
            candidate_group = str(candidate_management.get("version_group", "")).strip()
        if not candidate_group:
            candidate_group = sanitize_scenario_name(str(item.get("scenario_name", "")).strip())
        if candidate_group != version_group:
            continue
        related_entries.append(
            {
                "scenario_name": str(item.get("scenario_name", "-")),
                "path": str(item.get("path", "")),
                "version_index": int(
                    (candidate_management.get("version_index", 1) if isinstance(candidate_management, dict) else 1)
                    or 1
                ),
                "updated_at": str(
                    (candidate_management.get("updated_at", "") if isinstance(candidate_management, dict) else "")
                    or item.get("mtime_label", "")
                ),
                "is_selected": str(item.get("path", "")).strip() == normalized_selected,
            }
        )

    related_entries.sort(
        key=lambda item: (
            int(item.get("version_index", 1) or 1),
            str(item.get("updated_at", "")),
            str(item.get("scenario_name", "")),
        ),
        reverse=True,
    )
    return related_entries


def build_scenario_diff_rows(
    left_scenario: dict[str, object] | None,
    right_scenario: dict[str, object] | None,
) -> list[dict[str, str]]:
    if not isinstance(left_scenario, dict) or not isinstance(right_scenario, dict):
        return []

    def labels_for(scenario: dict[str, object]) -> list[str]:
        labels = []
        for change in scenario.get("changes", []):
            if isinstance(change, dict):
                labels.append(str(change.get("label", "-")))
        return sorted(set(labels))

    def records_for(scenario: dict[str, object]) -> list[str]:
        records = []
        for change in scenario.get("changes", []):
            if isinstance(change, dict):
                records.append(str(change.get("record_label", "-")))
        return sorted(set(records))

    left_labels = labels_for(left_scenario)
    right_labels = labels_for(right_scenario)
    left_records = records_for(left_scenario)
    right_records = records_for(right_scenario)

    rows = [
        {
            "label": "Veri Seti",
            "left": str(left_scenario.get("input", "-")),
            "right": str(right_scenario.get("input", "-")),
        },
        {
            "label": "Degisiklik Sayisi",
            "left": str(len(left_scenario.get("changes", []))),
            "right": str(len(right_scenario.get("changes", []))),
        },
        {
            "label": "Islem Sayisi",
            "left": str(len(left_scenario.get("operations", []))),
            "right": str(len(right_scenario.get("operations", []))),
        },
        {
            "label": "Parametreler",
            "left": ", ".join(left_labels[:6]) or "-",
            "right": ", ".join(right_labels[:6]) or "-",
        },
        {
            "label": "Kayitlar",
            "left": ", ".join(left_records[:6]) or "-",
            "right": ", ".join(right_records[:6]) or "-",
        },
        {
            "label": "Sadece Solda",
            "left": ", ".join(sorted(set(left_labels) - set(right_labels))[:6]) or "-",
            "right": "-",
        },
        {
            "label": "Sadece Sagda",
            "left": "-",
            "right": ", ".join(sorted(set(right_labels) - set(left_labels))[:6]) or "-",
        },
    ]
    for row in rows:
        row["status"] = "Ayni" if row["left"] == row["right"] else "Farkli"
    return rows


def filter_scenario_diff_rows(
    diff_rows: list[dict[str, str]],
    selected_filter: str,
) -> list[dict[str, str]]:
    if selected_filter == "Sadece Farklilar":
        return [row for row in diff_rows if str(row.get("status", "")) != "Ayni"]
    if selected_filter == "Sadece Aynilar":
        return [row for row in diff_rows if str(row.get("status", "")) == "Ayni"]
    return list(diff_rows)


def build_multi_scenario_comparison_rows(
    left_scenario: dict[str, object] | None,
    right_scenario: dict[str, object] | None,
    third_scenario: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    scenarios = [
        ("left", left_scenario if isinstance(left_scenario, dict) else None),
        ("right", right_scenario if isinstance(right_scenario, dict) else None),
        ("third", third_scenario if isinstance(third_scenario, dict) else None),
    ]
    active = [(key, scenario) for key, scenario in scenarios if scenario is not None]
    if len(active) < 2:
        return []

    def labels_for(scenario: dict[str, object]) -> list[str]:
        labels = []
        for change in scenario.get("changes", []):
            if isinstance(change, dict):
                labels.append(str(change.get("label", "-")))
        return sorted(set(labels))

    def records_for(scenario: dict[str, object]) -> list[str]:
        records = []
        for change in scenario.get("changes", []):
            if isinstance(change, dict):
                records.append(str(change.get("record_label", "-")))
        return sorted(set(records))

    def cell_value(key: str, scenario: dict[str, object] | None, extractor) -> str:
        if scenario is None:
            return "-"
        return str(extractor(scenario))

    left_labels = labels_for(left_scenario) if isinstance(left_scenario, dict) else []
    right_labels = labels_for(right_scenario) if isinstance(right_scenario, dict) else []
    third_labels = labels_for(third_scenario) if isinstance(third_scenario, dict) else []

    rows = [
        {
            "label": "Veri Seti",
            "left": cell_value("left", left_scenario, lambda item: item.get("input", "-")),
            "right": cell_value("right", right_scenario, lambda item: item.get("input", "-")),
            "third": cell_value("third", third_scenario, lambda item: item.get("input", "-")),
        },
        {
            "label": "Degisiklik Sayisi",
            "left": cell_value("left", left_scenario, lambda item: len(item.get("changes", []))),
            "right": cell_value("right", right_scenario, lambda item: len(item.get("changes", []))),
            "third": cell_value("third", third_scenario, lambda item: len(item.get("changes", []))),
        },
        {
            "label": "Islem Sayisi",
            "left": cell_value("left", left_scenario, lambda item: len(item.get("operations", []))),
            "right": cell_value("right", right_scenario, lambda item: len(item.get("operations", []))),
            "third": cell_value("third", third_scenario, lambda item: len(item.get("operations", []))),
        },
        {
            "label": "Kayitlar",
            "left": cell_value("left", left_scenario, lambda item: ", ".join(records_for(item)[:6]) or "-"),
            "right": cell_value("right", right_scenario, lambda item: ", ".join(records_for(item)[:6]) or "-"),
            "third": cell_value("third", third_scenario, lambda item: ", ".join(records_for(item)[:6]) or "-"),
        },
    ]

    all_labels = sorted(set(left_labels) | set(right_labels) | set(third_labels))
    for parameter_label in all_labels:
        rows.append(
            {
                "label": f"Parametre: {parameter_label}",
                "left": "Var" if parameter_label in left_labels else "-",
                "right": "Var" if parameter_label in right_labels else "-",
                "third": "Var" if parameter_label in third_labels else "-",
            }
        )

    for row in rows:
        values = [row.get("left", "-"), row.get("right", "-")]
        if row.get("third", "-") != "-":
            values.append(row.get("third", "-"))
        unique_values = {str(value) for value in values}
        row["status"] = "Ayni" if len(unique_values) == 1 else "Farkli"
    return rows


def filter_multi_scenario_comparison_rows(
    comparison_rows: list[dict[str, str]],
    selected_filter: str,
    comparison_mode: str,
) -> list[dict[str, str]]:
    filtered_rows = list(comparison_rows)
    if selected_filter == "Sadece Farklilar":
        filtered_rows = [row for row in filtered_rows if str(row.get("status", "")) != "Ayni"]
    elif selected_filter == "Sadece Aynilar":
        filtered_rows = [row for row in filtered_rows if str(row.get("status", "")) == "Ayni"]

    if comparison_mode == "Ozet Fark Modu":
        filtered_rows = [
            row
            for row in filtered_rows
            if str(row.get("status", "")) != "Ayni" and str(row.get("label", "")).startswith("Parametre:")
        ]
    return filtered_rows


def build_multi_scenario_commentary(
    scenarios: list[tuple[str, dict[str, object] | None]],
) -> str:
    active = [(name, scenario) for name, scenario in scenarios if isinstance(scenario, dict)]
    if len(active) < 2:
        return "Yorum olusturmak icin en az iki senaryo secin."

    metrics: list[tuple[str, int, int, str]] = []
    for name, scenario in active:
        metrics.append(
            (
                name,
                len(scenario.get("changes", [])),
                len(scenario.get("operations", [])),
                str(scenario.get("input", "-")),
            )
        )

    lightest = min(metrics, key=lambda item: (item[1], item[2], item[0]))
    broadest = max(metrics, key=lambda item: (item[1], item[2], item[0]))
    datasets = sorted({item[3] for item in metrics})

    lines = [
        f"- En kontrollu secenek gibi gorunen senaryo: **{lightest[0]}** "
        f"(degisiklik: {lightest[1]}, islem: {lightest[2]}).",
        f"- En kapsamli senaryo: **{broadest[0]}** "
        f"(degisiklik: {broadest[1]}, islem: {broadest[2]}).",
    ]
    if len(datasets) == 1:
        lines.append(f"- Tum secenekler ayni veri setini hedefliyor: `{datasets[0]}`.")
    else:
        lines.append("- Senaryolar farkli veri setlerine dokunuyor; birebir kazanan yorumu dikkatli okunmali.")
    return "\n".join(lines)


def _parse_numeric_value(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract_metric_value(report: dict[str, object] | None, metric_id: str) -> float | None:
    if not isinstance(report, dict):
        return None
    metrics = report.get("metrics", [])
    if not isinstance(metrics, list):
        return None
    normalized_metric = str(metric_id).strip().lower()
    for row in metrics:
        if not isinstance(row, dict):
            continue
        if str(row.get("metric_id", "")).strip().lower() != normalized_metric:
            continue
        return _parse_numeric_value(row.get("scenario_value"))
    return None


def _extract_risk_level(report: dict[str, object] | None) -> tuple[int, str]:
    if not isinstance(report, dict):
        return (999, "bilinmiyor")
    comparison_model = report.get("comparison_model", {})
    if not isinstance(comparison_model, dict):
        return (999, "bilinmiyor")
    summary = comparison_model.get("summary", {})
    if not isinstance(summary, dict):
        return (999, "bilinmiyor")
    most_critical = summary.get("most_critical", {})
    if not isinstance(most_critical, dict):
        return (999, "bilinmiyor")
    severity = str(most_critical.get("severity_level", "")).strip().lower() or "bilinmiyor"
    return (_RISK_ORDER.get(severity, 999), severity)


def build_multi_scenario_decision_commentary(
    scenarios: list[tuple[str, dict[str, object] | None]],
    reports_by_name: dict[str, dict[str, object]] | None = None,
) -> str:
    report_lookup = reports_by_name or {}
    active = [(name, scenario) for name, scenario in scenarios if isinstance(scenario, dict)]
    if len(active) < 2:
        return "Karar yorumu icin en az iki senaryo secin."

    energy_scores: list[tuple[str, float]] = []
    cost_scores: list[tuple[str, float]] = []
    risk_scores: list[tuple[str, int, str]] = []
    for name, _scenario in active:
        report = report_lookup.get(name, {})
        energy_value = _extract_metric_value(report, "total_energy")
        cost_value = _extract_metric_value(report, "annual_cost")
        if energy_value is not None:
            energy_scores.append((name, energy_value))
        if cost_value is not None:
            cost_scores.append((name, cost_value))
        risk_rank, risk_label = _extract_risk_level(report)
        if risk_rank != 999:
            risk_scores.append((name, risk_rank, risk_label))

    lines: list[str] = []
    if energy_scores:
        best_energy = min(energy_scores, key=lambda item: (item[1], item[0]))
        lines.append(
            f"- Enerji tarafinda en iyi gorunen senaryo: **{best_energy[0]}** "
            f"(toplam enerji: {best_energy[1]:.2f})."
        )
    if cost_scores:
        best_cost = min(cost_scores, key=lambda item: (item[1], item[0]))
        lines.append(
            f"- Maliyet tarafinda en iyi gorunen senaryo: **{best_cost[0]}** "
            f"(yillik maliyet: {best_cost[1]:.2f})."
        )
    if risk_scores:
        best_risk = min(risk_scores, key=lambda item: (item[1], item[0]))
        lines.append(
            f"- Risk acisindan daha guvenli duran secenek: **{best_risk[0]}** "
            f"(kritik seviye: {best_risk[2]})."
        )

    if lines:
        if len(lines) >= 2:
            leaders = [line.split("**")[1] for line in lines if "**" in line]
            unique_leaders = sorted(set(leaders))
            if len(unique_leaders) == 1:
                lines.append(
                    f"- Genel tabloya gore en dengeli aday su an **{unique_leaders[0]}** gibi gorunuyor."
                )
            else:
                lines.append(
                    "- Tek bir mutlak kazanan yok; enerji, maliyet ve risk onceligine gore secim degisebilir."
                )
        return "\n".join(lines)

    return build_multi_scenario_commentary(scenarios)


def build_multi_scenario_score_rows(
    scenarios: list[tuple[str, dict[str, object] | None]],
    reports_by_name: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    report_lookup = reports_by_name or {}
    active_names = [name for name, scenario in scenarios if isinstance(scenario, dict)]
    if not active_names:
        return []

    energy_values = {
        name: _extract_metric_value(report_lookup.get(name, {}), "total_energy")
        for name in active_names
    }
    cost_values = {
        name: _extract_metric_value(report_lookup.get(name, {}), "annual_cost")
        for name in active_names
    }
    risk_values = {
        name: _extract_risk_level(report_lookup.get(name, {}))
        for name in active_names
    }

    valid_energy = [value for value in energy_values.values() if value is not None]
    valid_cost = [value for value in cost_values.values() if value is not None]
    valid_risk = [value[0] for value in risk_values.values() if value[0] != 999]

    def normalized_score(value: float | None, minimum: float | None, maximum: float | None) -> float | None:
        if value is None or minimum is None or maximum is None:
            return None
        if maximum <= minimum:
            return 10.0
        ratio = (value - minimum) / (maximum - minimum)
        return round(10.0 - (ratio * 9.0), 1)

    energy_min = min(valid_energy) if valid_energy else None
    energy_max = max(valid_energy) if valid_energy else None
    cost_min = min(valid_cost) if valid_cost else None
    cost_max = max(valid_cost) if valid_cost else None
    risk_min = min(valid_risk) if valid_risk else None
    risk_max = max(valid_risk) if valid_risk else None

    rows: list[dict[str, object]] = []
    for name in active_names:
        energy_score = normalized_score(energy_values.get(name), energy_min, energy_max)
        cost_score = normalized_score(cost_values.get(name), cost_min, cost_max)
        risk_rank, risk_label = risk_values.get(name, (999, "bilinmiyor"))
        risk_score = (
            normalized_score(float(risk_rank), float(risk_min), float(risk_max))
            if risk_rank != 999 and risk_min is not None and risk_max is not None
            else None
        )
        available_scores = [score for score in [energy_score, cost_score, risk_score] if score is not None]
        total_score = round(sum(available_scores) / len(available_scores), 1) if available_scores else None
        rows.append(
            {
                "scenario_name": name,
                "energy_score": energy_score,
                "cost_score": cost_score,
                "risk_score": risk_score,
                "risk_label": risk_label,
                "total_score": total_score,
            }
        )

    rows.sort(
        key=lambda item: (
            -(float(item["total_score"]) if item.get("total_score") is not None else -1.0),
            str(item.get("scenario_name", "")),
        )
    )
    return rows


def build_multi_scenario_chart_model(
    scenarios: list[tuple[str, dict[str, object] | None]],
) -> dict[str, object]:
    labels: list[str] = []
    change_counts: list[int] = []
    operation_counts: list[int] = []
    for name, scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        labels.append(name)
        change_counts.append(len(scenario.get("changes", [])))
        operation_counts.append(len(scenario.get("operations", [])))
    return {
        "labels": labels,
        "change_counts": change_counts,
        "operation_counts": operation_counts,
        "has_data": bool(labels),
    }
