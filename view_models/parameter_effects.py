from __future__ import annotations

from parameter_catalog import ParameterDefinition


PARAMETER_IMPACT_DIMENSIONS = (
    "heating_energy",
    "cooling_energy",
    "total_energy",
    "peak_load",
    "temperature_stability",
    "overheating_risk",
    "surface_solar",
    "cost_payback",
)
PARAMETER_IMPACT_LABELS: dict[str, str] = {
    "heating_energy": "Isitma Enerjisi",
    "cooling_energy": "Sogutma Enerjisi",
    "total_energy": "Toplam Enerji",
    "peak_load": "Tepe Yuk",
    "temperature_stability": "Ic Sicaklik Kararliligi",
    "overheating_risk": "Asiri Isinma Riski",
    "surface_solar": "Gunes ve Yuzey Etkisi",
    "cost_payback": "Maliyet",
}
PARAMETER_IMPACT_WEIGHTS: dict[str, dict[str, int]] = {
    "u_value": {"heating_energy": 3, "cooling_energy": 1, "total_energy": 3, "peak_load": 2, "cost_payback": 2},
    "thermal_mass": {"temperature_stability": 3, "overheating_risk": 2, "cooling_energy": 1, "peak_load": 1},
    "assembly_thickness": {"heating_energy": 2, "cooling_energy": 1, "total_energy": 2, "peak_load": 1},
    "heat_transfer": {"heating_energy": 2, "cooling_energy": 2, "total_energy": 2, "peak_load": 1},
    "envelope_performance": {"heating_energy": 2, "cooling_energy": 2, "total_energy": 3, "cost_payback": 2},
    "heat_loss": {"heating_energy": 3, "total_energy": 2, "temperature_stability": 1, "cost_payback": 2},
    "heat_storage": {"temperature_stability": 3, "overheating_risk": 1, "cooling_energy": 1},
    "temperature_response": {"temperature_stability": 3, "overheating_risk": 2, "peak_load": 1},
    "surface_exchange": {"surface_solar": 2, "temperature_stability": 1, "cooling_energy": 1},
    "radiative_behavior": {"surface_solar": 2, "overheating_risk": 2, "cooling_energy": 1},
    "solar_gain": {"surface_solar": 3, "cooling_energy": 3, "overheating_risk": 3, "heating_energy": 1},
    "surface_temperature": {"surface_solar": 3, "overheating_risk": 2, "temperature_stability": 1},
    "daylight_reflectance": {"surface_solar": 1, "cost_payback": 1, "temperature_stability": 1},
    "surface_optics": {"surface_solar": 2, "overheating_risk": 1},
    "assembly_behavior": {"temperature_stability": 2, "peak_load": 1, "total_energy": 1},
    "assembly_composition": {"heating_energy": 2, "cooling_energy": 1, "total_energy": 2, "temperature_stability": 1},
    "thermal_performance": {"heating_energy": 2, "cooling_energy": 2, "total_energy": 3, "cost_payback": 2},
    "wall_u_value": {"heating_energy": 3, "cooling_energy": 1, "total_energy": 2, "temperature_stability": 1},
    "roof_u_value": {"cooling_energy": 3, "heating_energy": 2, "total_energy": 3, "overheating_risk": 2, "surface_solar": 2},
    "floor_u_value": {"heating_energy": 2, "total_energy": 2, "temperature_stability": 1},
    "window_heat_transfer": {"heating_energy": 3, "cooling_energy": 2, "total_energy": 3, "peak_load": 2, "cost_payback": 2},
    "heating_load": {"heating_energy": 3, "peak_load": 2, "cost_payback": 2},
    "cooling_load": {"cooling_energy": 3, "peak_load": 2, "overheating_risk": 2, "cost_payback": 2},
    "daylight_balance": {"surface_solar": 1, "temperature_stability": 1, "cost_payback": 1},
    "construction_mapping": {"heating_energy": 2, "cooling_energy": 2, "total_energy": 2, "peak_load": 1},
    "surface_assignment": {"surface_solar": 2, "overheating_risk": 1, "total_energy": 1},
    "layer_order": {"temperature_stability": 2, "overheating_risk": 1, "surface_solar": 1},
    "surface_behavior": {"surface_solar": 2, "overheating_risk": 2, "cooling_energy": 1},
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


def format_chart_value(value: object, unit: str = "") -> str:
    number = try_parse_number(value)
    if number is None:
        return "-"
    suffix = f" {unit}" if unit else ""
    return f"{number:.4f}".rstrip("0").rstrip(".") + suffix


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
        return {"has_effective_change": False, "reason": "Yeni deger girilmedi.", "multiplier": 0, "direction": "none"}

    value_type = str(parameter.value_type or "").strip().lower()
    if value_type in {"float", "integer"}:
        current_number = try_parse_number(current_value)
        new_number = try_parse_number(new_value)
        if current_number is None or new_number is None:
            return {"has_effective_change": False, "reason": "Gecerli sayisal deger girilmedi.", "multiplier": 0, "direction": "none"}
        delta = float(new_number) - float(current_number)
        if delta == 0:
            return {"has_effective_change": False, "reason": "Yeni deger mevcut degerle ayni.", "multiplier": 0, "direction": "none"}
        relative_change = abs(delta) if current_number == 0 else abs(delta / float(current_number))
        multiplier = 1 if relative_change < 0.05 else 2 if relative_change < 0.20 else 3
        return {"has_effective_change": True, "reason": "", "multiplier": multiplier, "direction": "up" if delta > 0 else "down"}

    if new_text == current_text:
        return {"has_effective_change": False, "reason": "Yeni deger mevcut degerle ayni.", "multiplier": 0, "direction": "none"}
    return {"has_effective_change": True, "reason": "", "multiplier": 2, "direction": "changed"}


def _build_impact_level(score: int) -> dict[str, str | int]:
    if score >= 4:
        return {"score": score, "label": "guclu", "emoji": "G", "text": "guclu", "classes": "bg-emerald-50 text-emerald-800 border border-emerald-200"}
    if score >= 2:
        return {"score": score, "label": "orta", "emoji": "O", "text": "orta", "classes": "bg-amber-50 text-amber-800 border border-amber-200"}
    if score >= 1:
        return {"score": score, "label": "dusuk", "emoji": "D", "text": "dusuk", "classes": "bg-slate-50 text-slate-700 border border-slate-200"}
    return {"score": score, "label": "sinirli", "emoji": "S", "text": "sinirli", "classes": "bg-slate-50 text-slate-500 border border-slate-200"}


def build_parameter_impact_map_model(selected_parameter_state: dict[str, dict[str, object]]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for parameter_id, item in selected_parameter_state.items():
        parameter = item.get("definition")
        if parameter is None:
            continue
        change_state = analyze_parameter_change_state(parameter=parameter, current_value=item.get("current_value"), new_value=item.get("new_value"))
        if not bool(change_state.get("has_effective_change")):
            continue
        scores = {dimension: 0 for dimension in PARAMETER_IMPACT_DIMENSIONS}
        matched_impacts: list[str] = []
        for raw_impact in getattr(parameter, "expected_impacts", ()) or ():
            impact_key = str(raw_impact or "").strip().lower()
            if not impact_key:
                continue
            matched_impacts.append(impact_key)
            for dimension, weight in PARAMETER_IMPACT_WEIGHTS.get(impact_key, {}).items():
                if dimension in scores:
                    scores[dimension] += int(weight) * int(change_state.get("multiplier", 1))
        row: dict[str, object] = {
            "parameter_id": parameter_id,
            "parameter_label": str(getattr(parameter, "label", parameter_id)),
            "matched_impacts": matched_impacts,
            "change_state": change_state,
        }
        for dimension in PARAMETER_IMPACT_DIMENSIONS:
            row[dimension] = _build_impact_level(scores[dimension])
        rows.append(row)
    return {"rows": rows, "has_data": bool(rows), "columns": list(PARAMETER_IMPACT_DIMENSIONS)}


def build_parameter_impact_summary_cards(impact_map_model: dict[str, object]) -> list[dict[str, str | int]]:
    rows = list(impact_map_model.get("rows", []))
    if not rows:
        return []
    cards: list[dict[str, str | int]] = []
    for dimension in PARAMETER_IMPACT_DIMENSIONS:
        best_row = max(rows, key=lambda item: int(dict(item.get(dimension, {})).get("score", 0)))
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
    series: list[dict[str, object]] = [{"name": "Mevcut Durum", "values": [0 for _ in PARAMETER_IMPACT_DIMENSIONS], "color": "#64748b", "line_type": "dashed"}]
    palette = ["#2563eb", "#0f766e", "#dc2626", "#ca8a04", "#7c3aed", "#0891b2"]
    combined_values = [0 for _ in PARAMETER_IMPACT_DIMENSIONS]
    for index, row in enumerate(rows):
        values: list[int] = []
        for dim_index, dimension in enumerate(PARAMETER_IMPACT_DIMENSIONS):
            score = int(dict(row.get(dimension, {})).get("score", 0))
            values.append(score)
            combined_values[dim_index] += score
        series.append({"name": str(row.get("parameter_label", f"Parametre {index + 1}")), "values": values, "color": palette[index % len(palette)], "line_type": "solid"})
    if len(rows) > 1:
        series.append({"name": "Birlesik Senaryo", "values": combined_values, "color": "#111827", "line_type": "solid", "line_width": 4})
    return series


def build_single_parameter_impact_chart_options(parameter_label: str, dimension_scores: dict[str, int]) -> dict[str, object]:
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
        "yAxis": {"type": "value", "name": "Goreli Etki", "min": 0, "max": axis_max, "splitLine": {"lineStyle": {"color": "#e2e8f0"}}},
        "series": [
            {"name": "Mevcut Durum", "type": "line", "data": [0 for _ in PARAMETER_IMPACT_DIMENSIONS], "smooth": True, "symbol": "circle", "symbolSize": 8, "lineStyle": {"type": "dashed", "width": 2, "color": "#94a3b8"}, "itemStyle": {"color": "#94a3b8"}},
            {"name": "Yeni Durum", "type": "line", "data": new_values, "smooth": True, "symbol": "circle", "symbolSize": 8, "lineStyle": {"width": 3, "color": "#2563eb"}, "itemStyle": {"color": "#2563eb"}, "areaStyle": {"color": "rgba(37,99,235,0.10)"}},
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
                "lineStyle": {"type": str(row.get("line_type", "solid")), "width": int(row.get("line_width", 3)), "color": str(row.get("color", "#2563eb"))},
                "itemStyle": {"color": str(row.get("color", "#2563eb"))},
                "areaStyle": {"color": "rgba(15,118,110,0.08)"} if str(row.get("name", "")) == "Birlesik Senaryo" else None,
            }
        )
    return {"tooltip": {"trigger": "axis"}, "legend": {"top": 4}, "grid": {"left": 44, "right": 24, "top": 44, "bottom": 32, "containLabel": True}, "xAxis": {"type": "category", "data": labels}, "yAxis": {"type": "value", "name": "Goreli Etki", "min": 0, "max": max(3, max_value) + 1, "splitLine": {"lineStyle": {"color": "#e2e8f0"}}}, "series": chart_series}


def build_parameter_change_summary_text(parameter: ParameterDefinition, current_value: object, new_value: object, change_state: dict[str, object]) -> str:
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
        direction_text = {"up": "artis", "down": "azalis", "changed": "degisim"}.get(direction, "degisim")
        return f"{format_chart_value(current_number, unit)} -> {format_chart_value(new_number, unit)} | {direction_text}: {sign}{format_chart_value(delta, unit)}"
    return f"{str(current_value or '-')} -> {str(new_value or '-')} | deger guncellendi"


def build_parameter_expected_effect_text(parameter_impact_row: dict[str, object]) -> str:
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
