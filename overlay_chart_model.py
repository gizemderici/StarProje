from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LineType = Literal["line", "area", "step"]
LineStyle = Literal["solid", "dashed", "dotted"]
SeriesOrigin = Literal["base", "scenario", "variant"]

BASE_SCENARIO_LABEL = "Base Scenario"
BASE_SCENARIO_ALIAS_TEXT = "Before / Base / Original"
BASE_SCENARIO_COLOR = "#1f2937"
BASE_SCENARIO_LINE_STYLE: LineStyle = "solid"
BASE_SCENARIO_LINE_TYPE: LineType = "line"
BASE_SCENARIO_LINE_WIDTH = 3

_BASE_NAME_ALIASES = {
    "base",
    "base scenario",
    "before",
    "original",
    "old",
    "old scenario",
}


@dataclass(frozen=True)
class OverlayLineSeries:
    name: str
    data: list[float | None]
    line_type: LineType = "line"
    color: str | None = None
    line_style: LineStyle = "solid"
    origin: SeriesOrigin = "scenario"


@dataclass(frozen=True)
class OverlayChartModel:
    chart_name: str
    x_labels: list[str]
    series: list[OverlayLineSeries]


@dataclass(frozen=True)
class ParameterValueOverlayModel:
    chart_name: str
    labels: list[str]
    base_series: list[float | None]
    updated_series: list[float | None]
    raw_base_series: list[float | None]
    raw_updated_series: list[float | None]
    units: list[str]
    is_normalized: bool
    missing_updated_labels: list[str]


def _coerce_labels(labels: list[object]) -> list[str]:
    return [str(item) for item in labels]


def _coerce_series_data(data: list[object], expected_len: int) -> list[float | None]:
    # Normalize series length to x-axis length so every line can be plotted safely.
    values: list[float | None] = []
    for item in data[:expected_len]:
        if item is None:
            values.append(None)
            continue
        try:
            values.append(float(str(item).strip()))
        except (TypeError, ValueError):
            values.append(None)

    if len(values) < expected_len:
        values.extend([None] * (expected_len - len(values)))

    return values


def _coerce_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _is_base_series(name: str, origin: SeriesOrigin) -> bool:
    if origin == "base":
        return True
    normalized_name = str(name).strip().lower()
    return normalized_name in _BASE_NAME_ALIASES


def _standardize_base_series_order(series: list[OverlayLineSeries]) -> list[OverlayLineSeries]:
    base_index: int | None = None
    for index, item in enumerate(series):
        if _is_base_series(item.name, item.origin):
            base_index = index
            break

    if base_index is None:
        return list(series)

    base_item = series[base_index]
    standardized_base = OverlayLineSeries(
        name=BASE_SCENARIO_LABEL,
        data=list(base_item.data),
        line_type=BASE_SCENARIO_LINE_TYPE,
        color=base_item.color or BASE_SCENARIO_COLOR,
        line_style=BASE_SCENARIO_LINE_STYLE,
        origin="base",
    )

    ordered = [standardized_base]
    ordered.extend(item for index, item in enumerate(series) if index != base_index)
    return ordered


def build_overlay_chart_model(
    chart_name: str,
    x_labels: list[object],
    series: list[dict[str, object]],
) -> OverlayChartModel:
    labels = _coerce_labels(x_labels)
    built_series: list[OverlayLineSeries] = []

    for item in series:
        raw_data = item.get("data", [])
        if not isinstance(raw_data, list):
            raw_data = []
        built_series.append(
            OverlayLineSeries(
                name=str(item.get("name", "Series")),
                data=_coerce_series_data(raw_data, len(labels)),
                line_type=(item.get("line_type") or "line"),  # type: ignore[arg-type]
                color=(str(item.get("color")) if item.get("color") is not None else None),
                line_style=(item.get("line_style") or "solid"),  # type: ignore[arg-type]
                origin=(item.get("origin") or "scenario"),  # type: ignore[arg-type]
            )
        )

    return OverlayChartModel(
        chart_name=str(chart_name),
        x_labels=labels,
        series=_standardize_base_series_order(built_series),
    )


def append_overlay_series(
    model: OverlayChartModel,
    name: str,
    data: list[object],
    line_type: LineType = "line",
    color: str | None = None,
    line_style: LineStyle = "solid",
    origin: SeriesOrigin = "scenario",
) -> OverlayChartModel:
    appended = list(model.series)
    appended.append(
        OverlayLineSeries(
            name=name,
            data=_coerce_series_data(data, len(model.x_labels)),
            line_type=line_type,
            color=color,
            line_style=line_style,
            origin=origin,
        )
    )
    return OverlayChartModel(
        chart_name=model.chart_name,
        x_labels=list(model.x_labels),
        series=_standardize_base_series_order(appended),
    )


def build_monthly_overlay_chart_model(
    chart_name: str,
    months: list[object],
    base_values: list[object],
    scenario_values: list[object],
    scenario_name: str = "Scenario A",
) -> OverlayChartModel:
    return build_overlay_chart_model(
        chart_name=chart_name,
        x_labels=months,
        series=[
            {
                "name": "Base Scenario",
                "data": base_values,
                "origin": "base",
                "line_type": "line",
                "line_style": "solid",
                "color": "#94a3b8",
            },
            {
                "name": scenario_name,
                "data": scenario_values,
                "origin": "scenario",
                "line_type": "line",
                "line_style": "solid",
                "color": "#0f766e",
            },
        ],
    )


def overlay_chart_model_to_echart_series(model: OverlayChartModel) -> list[dict[str, object]]:
    echart_series: list[dict[str, object]] = []
    for item in model.series:
        series_entry: dict[str, object] = {
            "name": item.name,
            "type": "line" if item.line_type in {"line", "area", "step"} else "line",
            "data": item.data,
            "smooth": item.line_type != "step",
            "lineStyle": {
                "type": item.line_style,
                "width": BASE_SCENARIO_LINE_WIDTH if item.origin == "base" else 2,
            },
            "meta": {
                "origin": item.origin,
                "description": (BASE_SCENARIO_ALIAS_TEXT if item.origin == "base" else "Scenario line"),
            },
            "z": 3 if item.origin == "base" else 2,
        }
        if item.line_type == "area":
            series_entry["areaStyle"] = {}
        if item.line_type == "step":
            series_entry["step"] = "middle"
        if item.color:
            series_entry["lineStyle"] = {
                "type": item.line_style,
                "color": item.color,
                "width": BASE_SCENARIO_LINE_WIDTH if item.origin == "base" else 2,
            }
            series_entry["itemStyle"] = {"color": item.color}
        echart_series.append(series_entry)

    return echart_series


def build_parameter_value_overlay_model(
    parameter_rows: list[dict[str, object]],
    chart_name: str = "Parametre Base vs Updated",
) -> ParameterValueOverlayModel:
    labels: list[str] = []
    raw_base_series: list[float | None] = []
    raw_updated_series: list[float | None] = []
    units: list[str] = []
    missing_updated_labels: list[str] = []

    distinct_units = {
        str(item.get("unit", "")).strip()
        for item in parameter_rows
        if _coerce_number(item.get("base_value")) is not None
    }
    distinct_units.discard("")
    is_normalized = len(distinct_units) > 1

    for item in parameter_rows:
        base_value = _coerce_number(item.get("base_value"))
        if base_value is None:
            continue

        label = str(item.get("label", "Parameter")).strip() or "Parameter"
        updated_value = _coerce_number(item.get("updated_value"))
        unit = str(item.get("unit", "")).strip()

        labels.append(label)
        raw_base_series.append(base_value)
        raw_updated_series.append(updated_value)
        units.append(unit)
        if updated_value is None:
            missing_updated_labels.append(label)

    if not is_normalized:
        return ParameterValueOverlayModel(
            chart_name=chart_name,
            labels=labels,
            base_series=list(raw_base_series),
            updated_series=list(raw_updated_series),
            raw_base_series=raw_base_series,
            raw_updated_series=raw_updated_series,
            units=units,
            is_normalized=False,
            missing_updated_labels=missing_updated_labels,
        )

    base_series: list[float | None] = []
    updated_series: list[float | None] = []

    for base_value, updated_value in zip(raw_base_series, raw_updated_series):
        scale_candidates = [abs(value) for value in (base_value, updated_value) if value is not None]
        scale = max(scale_candidates) if scale_candidates else 0.0
        if scale == 0:
            base_series.append(0.0 if base_value is not None else None)
            updated_series.append(0.0 if updated_value is not None else None)
            continue
        base_series.append((base_value / scale) if base_value is not None else None)
        updated_series.append((updated_value / scale) if updated_value is not None else None)

    return ParameterValueOverlayModel(
        chart_name=chart_name,
        labels=labels,
        base_series=base_series,
        updated_series=updated_series,
        raw_base_series=raw_base_series,
        raw_updated_series=raw_updated_series,
        units=units,
        is_normalized=True,
        missing_updated_labels=missing_updated_labels,
    )
