from __future__ import annotations

from typing import Any


COMMON_COMPARISON_FIELDS = (
    "comparison_id",
    "comparison_type",
    "item_id",
    "label",
    "unit",
    "base_value",
    "scenario_value",
    "delta",
    "percent_delta",
    "context",
    "source",
)


SEVERITY_THRESHOLDS = (
    (30.0, "kritik", 4),
    (15.0, "yuksek", 3),
    (5.0, "orta", 2),
    (0.0, "dusuk", 1),
)


SEVERITY_COLORS = {
    "kritik": "negative",
    "yuksek": "warning",
    "orta": "amber",
    "dusuk": "grey",
    "bilinmiyor": "grey",
}


SEVERITY_WORDS = {
    "kritik": "cok belirgin",
    "yuksek": "belirgin",
    "orta": "olcumlenebilir",
    "dusuk": "sinirli",
    "bilinmiyor": "yorumlanamayan",
}


def _try_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _compute_delta(base_value: Any, scenario_value: Any) -> tuple[float | None, float | None]:
    base_number = _try_float(base_value)
    scenario_number = _try_float(scenario_value)
    if base_number is None or scenario_number is None:
        return None, None

    delta = scenario_number - base_number
    if base_number == 0:
        return delta, None
    return delta, (delta / base_number) * 100.0


def classify_percent_delta(percent_delta: Any) -> tuple[str, int]:
    number = _try_float(percent_delta)
    if number is None:
        return "bilinmiyor", 0

    absolute_value = abs(number)
    for threshold, label, score in SEVERITY_THRESHOLDS:
        if absolute_value >= threshold:
            return label, score
    return "bilinmiyor", 0


def _infer_trend(comparison_type: str, item_id: str, delta: Any) -> str:
    delta_number = _try_float(delta)
    if delta_number is None:
        return "bilinmiyor"
    if delta_number == 0:
        return "stabil"

    lower_is_better = False
    normalized_type = str(comparison_type).strip().lower()
    normalized_item_id = str(item_id).strip().lower()
    if normalized_type in {"metric", "cost"}:
        lower_is_better = True
    if normalized_item_id in {
        "annual_heating",
        "annual_cooling",
        "total_energy",
        "eui",
        "unmet_hours",
        "peak_heating",
        "peak_cooling",
        "annual_cost",
    }:
        lower_is_better = True

    if lower_is_better:
        return "iyilesme" if delta_number < 0 else "kotulesme"
    return "artis" if delta_number > 0 else "azalis"


def _absolute_percent(item: dict[str, Any]) -> float:
    value = _try_float(item.get("percent_delta"))
    return abs(value) if value is not None else -1.0


def _format_percent(percent_delta: Any) -> str:
    number = _try_float(percent_delta)
    if number is None:
        return "-"
    return f"{number:.1f}%"


def _build_auto_comment(
    comparison_type: str,
    item_id: str,
    label: str,
    percent_delta: Any,
    severity_level: str,
    trend: str,
) -> str:
    severity_word = SEVERITY_WORDS.get(severity_level, "olcumlenebilir")
    percent_text = _format_percent(percent_delta)
    metric_id = str(item_id).strip().lower()

    if comparison_type == "metric":
        if metric_id == "annual_heating":
            if trend == "iyilesme":
                return f"Heating yukunde {severity_word} bir azalma goruldu ({percent_text})."
            if trend == "kotulesme":
                return f"Heating yukunde {severity_word} bir artis goruldu ({percent_text})."
        if metric_id == "annual_cooling":
            if trend == "iyilesme":
                return f"Cooling yukunde {severity_word} bir azalma goruldu ({percent_text})."
            if trend == "kotulesme":
                return f"Cooling yukunde {severity_word} bir artis goruldu ({percent_text})."
        if metric_id == "unmet_hours":
            if trend == "iyilesme":
                return f"Konfor disi saatlerde {severity_word} iyilesme goruldu ({percent_text})."
            if trend == "kotulesme":
                return f"Konfor disi saatlerde {severity_word} kotulesme goruldu ({percent_text})."
        if metric_id == "annual_cost":
            if trend == "iyilesme":
                return f"Yillik maliyette {severity_word} bir azalis var ({percent_text})."
            if trend == "kotulesme":
                return f"Yillik maliyette {severity_word} bir artis var ({percent_text})."

    if comparison_type == "cost":
        if trend == "iyilesme":
            return f"Maliyet tarafinda {severity_word} iyilesme goruluyor ({percent_text})."
        if trend == "kotulesme":
            return f"Maliyet tarafinda {severity_word} kotulesme goruluyor ({percent_text})."

    if comparison_type == "parameter":
        return f"{label} parametresinde {severity_word} degisim var ({percent_text})."
    if comparison_type == "layer_impact":
        return f"Katman etkisinde {severity_word} degisim tespit edildi ({percent_text})."

    if trend == "iyilesme":
        return f"{label} sonucunda {severity_word} bir iyilesme var ({percent_text})."
    if trend == "kotulesme":
        return f"{label} sonucunda {severity_word} bir kotulesme var ({percent_text})."
    return f"{label} sonucunda {severity_word} bir degisim izlendi ({percent_text})."


def build_comparison_item(
    *,
    comparison_type: str,
    item_id: str,
    label: str,
    unit: str,
    base_value: Any,
    scenario_value: Any,
    delta: Any = None,
    percent_delta: Any = None,
    context: dict[str, Any] | None = None,
    source: str = "",
) -> dict[str, Any]:
    computed_delta = delta
    computed_percent_delta = percent_delta
    if computed_delta is None and computed_percent_delta is None:
        computed_delta, computed_percent_delta = _compute_delta(base_value, scenario_value)

    severity_level, severity_score = classify_percent_delta(computed_percent_delta)
    trend = _infer_trend(comparison_type, item_id, computed_delta)
    auto_comment = _build_auto_comment(
        comparison_type=comparison_type,
        item_id=item_id,
        label=label,
        percent_delta=computed_percent_delta,
        severity_level=severity_level,
        trend=trend,
    )
    merged_context = dict(context or {})
    merged_context.update(
        {
            "severity_level": severity_level,
            "severity_score": severity_score,
            "severity_color": SEVERITY_COLORS.get(severity_level, "grey"),
            "trend": trend,
            "auto_comment": auto_comment,
        }
    )

    return {
        "comparison_id": f"{comparison_type}:{item_id}",
        "comparison_type": comparison_type,
        "item_id": item_id,
        "label": label,
        "unit": unit,
        "base_value": base_value,
        "scenario_value": scenario_value,
        "delta": computed_delta,
        "percent_delta": computed_percent_delta,
        "context": merged_context,
        "source": source,
    }


def build_items_from_changed_cells(changed_cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, cell in enumerate(changed_cells, start=1):
        row_key = str(cell.get("row_key", "")).strip()
        column = str(cell.get("column", "")).strip() or f"cell_{index}"
        items.append(
            build_comparison_item(
                comparison_type="parameter",
                item_id=f"{row_key}::{column}" if row_key else column,
                label=column,
                unit="-",
                base_value=cell.get("baseline_value"),
                scenario_value=cell.get("scenario_value"),
                context={"row_key": row_key},
                source="simulation_runner.changed_cells",
            )
        )
    return items


def build_items_from_metric_rows(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in metric_rows:
        metric_id = str(row.get("metric_id", "")).strip()
        if not metric_id:
            continue
        items.append(
            build_comparison_item(
                comparison_type="metric",
                item_id=metric_id,
                label=str(row.get("label", metric_id)),
                unit=str(row.get("unit", "-")),
                base_value=row.get("base_value"),
                scenario_value=row.get("scenario_value"),
                delta=row.get("delta"),
                percent_delta=row.get("percent_delta"),
                source="simulation_results_parser.metrics",
            )
        )
    return items


def build_items_from_cost_summary(cost_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not cost_summary:
        return []

    return [
        build_comparison_item(
            comparison_type="cost",
            item_id="annual_cost",
            label="Annual Cost",
            unit=str(cost_summary.get("currency", "-")),
            base_value=cost_summary.get("base_cost"),
            scenario_value=cost_summary.get("scenario_cost"),
            delta=cost_summary.get("delta"),
            percent_delta=cost_summary.get("percent_delta"),
            context={
                "method": str(cost_summary.get("method", "")),
                "has_data": bool(cost_summary.get("has_data", False)),
                "message": str(cost_summary.get("message", "")),
            },
            source="simulation_results_parser.cost_summary",
        )
    ]


def build_items_from_layer_impact_rows(layer_impact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in layer_impact_rows:
        item_id = str(row.get("id", "")).strip() or str(row.get("layer_name", "layer")).strip()
        changed_field = str(row.get("changed_field", "Layer Impact")).strip() or "Layer Impact"
        items.append(
            build_comparison_item(
                comparison_type="layer_impact",
                item_id=item_id,
                label=changed_field,
                unit="-",
                base_value=row.get("old_value"),
                scenario_value=row.get("new_value"),
                context={
                    "layer_name": str(row.get("layer_name", "")),
                    "material_name": str(row.get("material_name", "")),
                    "construction_names": str(row.get("construction_names", "")),
                    "badge": str(row.get("badge", "")),
                },
                source="nicegui.layer_impact_rows",
            )
        )
    return items


def build_unified_comparison_model(
    *,
    changed_cells: list[dict[str, Any]] | None = None,
    metric_rows: list[dict[str, Any]] | None = None,
    cost_summary: dict[str, Any] | None = None,
    layer_impact_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    items.extend(build_items_from_changed_cells(changed_cells or []))
    items.extend(build_items_from_metric_rows(metric_rows or []))
    items.extend(build_items_from_cost_summary(cost_summary))
    items.extend(build_items_from_layer_impact_rows(layer_impact_rows or []))

    by_type: dict[str, int] = {}
    for item in items:
        key = str(item.get("comparison_type", "unknown"))
        by_type[key] = by_type.get(key, 0) + 1

    ranked_items = sorted(
        items,
        key=lambda item: (
            int(item.get("context", {}).get("severity_score", 0)),
            _absolute_percent(item),
        ),
        reverse=True,
    )

    def _compact(item: dict[str, Any] | None) -> dict[str, Any] | None:
        if not item:
            return None
        return {
            "comparison_id": item.get("comparison_id"),
            "label": item.get("label"),
            "percent_delta": item.get("percent_delta"),
            "severity_level": item.get("context", {}).get("severity_level"),
            "trend": item.get("context", {}).get("trend"),
            "auto_comment": item.get("context", {}).get("auto_comment"),
        }

    critical_item = next(
        (item for item in ranked_items if str(item.get("context", {}).get("severity_level", "")) == "kritik"),
        None,
    )
    improvement_item = next(
        (item for item in ranked_items if str(item.get("context", {}).get("trend", "")) == "iyilesme"),
        None,
    )
    worsening_item = next(
        (item for item in ranked_items if str(item.get("context", {}).get("trend", "")) == "kotulesme"),
        None,
    )

    return {
        "summary": {
            "total_count": len(items),
            "by_type": by_type,
            "top_changed": [_compact(item) for item in ranked_items[:5]],
            "most_critical": _compact(critical_item),
            "best_improvement": _compact(improvement_item),
            "worst_worsening": _compact(worsening_item),
        },
        "items": items,
    }


def validate_common_comparison_items(items: list[dict[str, Any]]) -> None:
    required_fields = set(COMMON_COMPARISON_FIELDS)
    for item in items:
        if set(item.keys()) != required_fields:
            raise ValueError("Invalid common comparison item shape.")
