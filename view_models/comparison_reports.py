from __future__ import annotations

import json
from pathlib import Path


EXPECTED_COMPARISON_METRIC_IDS: tuple[str, ...] = (
    "annual_heating",
    "annual_cooling",
    "total_energy",
    "peak_heating",
    "peak_cooling",
    "zone_temperatures",
    "monthly_heating_cooling",
    "annual_cost",
)

LOWER_IS_BETTER_METRIC_IDS: frozenset[str] = frozenset(
    {
        "annual_heating",
        "annual_cooling",
        "total_energy",
        "peak_heating",
        "peak_cooling",
        "annual_cost",
    }
)

_COMPARISON_REPORT_CACHE: dict[tuple[tuple[str, float], tuple[str, ...]], list[dict]] = {}


def _read_json_file(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_comparison_report_files(base_dir: Path) -> list[Path]:
    if not Path(base_dir).exists():
        return []
    return sorted(Path(base_dir).rglob("*__comparison.json"))


def extract_scenario_name_from_comparison_report(report_path: Path) -> str:
    stem = report_path.stem
    if stem.endswith("__comparison"):
        return stem[: -len("__comparison")]
    return report_path.parent.parent.name


def summarize_metric_availability(
    metrics: list[dict[str, object]],
    expected_metric_ids: tuple[str, ...] = EXPECTED_COMPARISON_METRIC_IDS,
) -> dict[str, object]:
    metric_map: dict[str, dict[str, object]] = {}
    for row in metrics:
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id", "")).strip()
        if metric_id:
            metric_map[metric_id] = row

    available_metric_ids = sorted(metric_map.keys())
    missing_metric_ids = [metric_id for metric_id in expected_metric_ids if metric_id not in metric_map]

    null_metric_ids: list[str] = []
    populated_metric_ids: list[str] = []
    for metric_id, row in metric_map.items():
        has_base_value = row.get("base_value") is not None
        has_scenario_value = row.get("scenario_value") is not None
        if has_base_value or has_scenario_value:
            populated_metric_ids.append(metric_id)
        else:
            null_metric_ids.append(metric_id)

    return {
        "available_metric_ids": available_metric_ids,
        "missing_metric_ids": missing_metric_ids,
        "null_metric_ids": sorted(null_metric_ids),
        "populated_metric_ids": sorted(populated_metric_ids),
        "has_any_metric_data": bool(populated_metric_ids),
    }


def read_comparison_report_entries(
    base_dir: Path,
    expected_metric_ids: tuple[str, ...] = EXPECTED_COMPARISON_METRIC_IDS,
) -> list[dict]:
    report_files = collect_comparison_report_files(base_dir)
    cache_signature = (
        tuple((path.as_posix(), path.stat().st_mtime) for path in report_files),
        tuple(expected_metric_ids),
    )
    cached_entries = _COMPARISON_REPORT_CACHE.get(cache_signature)
    if cached_entries is not None:
        return [dict(item) for item in cached_entries]

    entries: list[dict] = []
    for report_path in report_files:
        raw_data = _read_json_file(report_path)
        if not isinstance(raw_data, dict):
            continue

        metrics = raw_data.get("metrics", [])
        if not isinstance(metrics, list):
            metrics = []

        metric_summary = summarize_metric_availability(metrics, expected_metric_ids)
        metric_source = raw_data.get("metric_source", {})
        if not isinstance(metric_source, dict):
            metric_source = {}
        metric_source_status = str(metric_source.get("status", "")).strip().lower() or "unknown"
        metric_source_message = str(metric_source.get("message", "")).strip()
        entries.append(
            {
                "scenario_name": extract_scenario_name_from_comparison_report(report_path),
                "report_path": report_path.as_posix(),
                "report_mtime": report_path.stat().st_mtime,
                "metrics": metrics,
                "metric_source": metric_source,
                "metric_source_status": metric_source_status,
                "metric_source_message": metric_source_message,
                "comparison_model": raw_data.get("comparison_model", {}),
                **metric_summary,
            }
        )

    entries.sort(key=lambda item: item.get("report_mtime", 0))
    _COMPARISON_REPORT_CACHE.clear()
    _COMPARISON_REPORT_CACHE[cache_signature] = [dict(item) for item in entries]
    return entries


def list_preparation_only_scenarios(runs_root: Path) -> list[str]:
    root_path = Path(runs_root)
    if not root_path.exists():
        return []

    scenario_names: list[str] = []
    for run_dir in sorted(path for path in root_path.iterdir() if path.is_dir()):
        metadata_path = run_dir / "run_metadata.json"
        if not metadata_path.exists():
            continue
        comparison_reports = list(run_dir.rglob("*__comparison.json"))
        if comparison_reports:
            continue
        scenario_names.append(run_dir.name)
    return scenario_names


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


def build_run_to_run_trend_model(
    comparison_entries: list[dict[str, object]],
    metric_id: str = "total_energy",
) -> dict[str, object]:
    normalized_metric_id = str(metric_id or "").strip().lower()
    if not normalized_metric_id:
        normalized_metric_id = "total_energy"

    points: list[dict[str, object]] = []
    for entry in sorted(comparison_entries, key=lambda item: float(item.get("report_mtime", 0) or 0)):
        metrics = entry.get("metrics", [])
        if not isinstance(metrics, list):
            continue

        selected_metric: dict[str, object] | None = None
        for row in metrics:
            if not isinstance(row, dict):
                continue
            if str(row.get("metric_id", "")).strip().lower() == normalized_metric_id:
                selected_metric = row
                break
        if selected_metric is None:
            continue

        scenario_value = _parse_numeric_value(selected_metric.get("scenario_value"))
        if scenario_value is None:
            continue

        points.append(
            {
                "scenario_name": str(entry.get("scenario_name", "")).strip() or "-",
                "report_mtime": float(entry.get("report_mtime", 0) or 0),
                "report_path": str(entry.get("report_path", "")).strip(),
                "metric_id": normalized_metric_id,
                "metric_label": str(selected_metric.get("label", normalized_metric_id)).strip() or normalized_metric_id,
                "unit": str(selected_metric.get("unit", "")).strip(),
                "value": scenario_value,
            }
        )

    if not points:
        return {
            "metric_id": normalized_metric_id,
            "metric_label": normalized_metric_id,
            "unit": "",
            "labels": [],
            "values": [],
            "deltas": [],
            "points": [],
            "improvement_count": 0,
            "worsening_count": 0,
            "unchanged_count": 0,
            "has_data": False,
            "summary": "Trend verisi bulunamadi.",
        }

    lower_is_better = normalized_metric_id in LOWER_IS_BETTER_METRIC_IDS
    improvement_count = 0
    worsening_count = 0
    unchanged_count = 0
    deltas: list[float | None] = []

    previous_value: float | None = None
    for point in points:
        current_value = float(point["value"])
        if previous_value is None:
            point["delta_from_previous"] = None
            point["trend"] = "baseline"
            deltas.append(None)
            previous_value = current_value
            continue

        delta = current_value - previous_value
        point["delta_from_previous"] = delta
        deltas.append(delta)
        if delta == 0:
            point["trend"] = "unchanged"
            unchanged_count += 1
        elif (delta < 0 and lower_is_better) or (delta > 0 and not lower_is_better):
            point["trend"] = "improvement"
            improvement_count += 1
        else:
            point["trend"] = "worsening"
            worsening_count += 1
        previous_value = current_value

    latest_delta = deltas[-1] if deltas else None
    latest_text = "baseline"
    if latest_delta is not None:
        if latest_delta == 0:
            latest_text = "sabit"
        elif (latest_delta < 0 and lower_is_better) or (latest_delta > 0 and not lower_is_better):
            latest_text = "iyilesme"
        else:
            latest_text = "kotulesme"

    unit = str(points[0].get("unit", ""))
    delta_text = "-"
    if latest_delta is not None:
        delta_text = f"{latest_delta:+.2f}"
        if unit:
            delta_text += f" {unit}"

    summary = (
        f"{len(points)} run icinde {improvement_count} iyilesme, {worsening_count} kotulesme, "
        f"{unchanged_count} sabit adim var. Son adim: {latest_text} ({delta_text})."
    )

    return {
        "metric_id": normalized_metric_id,
        "metric_label": str(points[0].get("metric_label", normalized_metric_id)),
        "unit": unit,
        "labels": [str(point.get("scenario_name", "-")) for point in points],
        "values": [float(point.get("value", 0)) for point in points],
        "deltas": deltas,
        "points": points,
        "improvement_count": improvement_count,
        "worsening_count": worsening_count,
        "unchanged_count": unchanged_count,
        "has_data": True,
        "summary": summary,
    }
