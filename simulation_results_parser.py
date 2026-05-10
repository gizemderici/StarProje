from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


COMMON_RESULT_FIELDS = (
    "metric_id",
    "label",
    "unit",
    "base_value",
    "scenario_value",
    "delta",
    "percent_delta",
)


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    label: str
    unit: str
    aliases: tuple[str, ...]


METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="annual_heating",
        label="Annual Heating",
        unit="kWh",
        aliases=("annual_heating", "annual heating", "heating_annual"),
    ),
    MetricSpec(
        metric_id="annual_cooling",
        label="Annual Cooling",
        unit="kWh",
        aliases=("annual_cooling", "annual cooling", "cooling_annual"),
    ),
    MetricSpec(
        metric_id="total_energy",
        label="Total Energy",
        unit="kWh",
        aliases=("total_energy", "total energy", "annual_total_energy"),
    ),
    MetricSpec(
        metric_id="eui",
        label="EUI",
        unit="kWh/m2-year",
        aliases=("eui", "energy_use_intensity", "energy use intensity"),
    ),
    MetricSpec(
        metric_id="unmet_hours",
        label="Unmet Hours",
        unit="h",
        aliases=("unmet_hours", "unmet hours", "annual_unmet_hours"),
    ),
    MetricSpec(
        metric_id="peak_heating",
        label="Peak Heating",
        unit="kW",
        aliases=("peak_heating", "peak heating", "heating_peak"),
    ),
    MetricSpec(
        metric_id="peak_cooling",
        label="Peak Cooling",
        unit="kW",
        aliases=("peak_cooling", "peak cooling", "cooling_peak"),
    ),
    MetricSpec(
        metric_id="zone_temperatures",
        label="Zone Temperatures",
        unit="C",
        aliases=("zone_temperatures", "zone temperatures", "zone_temperature"),
    ),
    MetricSpec(
        metric_id="monthly_heating_cooling",
        label="Monthly Heating/Cooling",
        unit="kWh",
        aliases=(
            "monthly_heating_cooling",
            "monthly heating/cooling",
            "monthly_heating",
            "monthly_cooling",
        ),
    ),
    MetricSpec(
        metric_id="annual_cost",
        label="Annual Cost",
        unit="currency",
        aliases=("annual_cost", "annual cost", "cost_annual"),
    ),
)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _normalize_metrics(raw_results: Mapping[str, Any] | None) -> dict[str, Any]:
    if not raw_results:
        return {}

    source: Any = raw_results.get("metrics", raw_results)
    if not isinstance(source, Mapping):
        return {}

    return {_normalize_key(str(key)): value for key, value in source.items()}


def _try_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _resolve_metric_value(normalized_metrics: Mapping[str, Any], spec: MetricSpec) -> Any:
    for alias in spec.aliases:
        key = _normalize_key(alias)
        if key in normalized_metrics:
            return normalized_metrics[key]
    return None


def _compute_delta(base_value: Any, scenario_value: Any) -> tuple[float | None, float | None]:
    base_number = _try_float(base_value)
    scenario_number = _try_float(scenario_value)
    if base_number is None or scenario_number is None:
        return None, None

    delta = scenario_number - base_number
    if base_number == 0:
        return delta, None

    percent_delta = (delta / base_number) * 100.0
    return delta, percent_delta


def parse_simulation_results(
    base_results: Mapping[str, Any] | None,
    scenario_results: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Build common metric rows used by UI and report layers."""
    normalized_base = _normalize_metrics(base_results)
    normalized_scenario = _normalize_metrics(scenario_results)

    rows: list[dict[str, Any]] = []
    for spec in METRIC_SPECS:
        base_value = _resolve_metric_value(normalized_base, spec)
        scenario_value = _resolve_metric_value(normalized_scenario, spec)
        delta, percent_delta = _compute_delta(base_value, scenario_value)

        rows.append(
            {
                "metric_id": spec.metric_id,
                "label": spec.label,
                "unit": spec.unit,
                "base_value": base_value,
                "scenario_value": scenario_value,
                "delta": delta,
                "percent_delta": percent_delta,
            }
        )

    return rows


def build_ui_results_model(
    base_results: Mapping[str, Any] | None,
    scenario_results: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    return parse_simulation_results(base_results, scenario_results)


def build_report_results_model(
    base_results: Mapping[str, Any] | None,
    scenario_results: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    return parse_simulation_results(base_results, scenario_results)


def validate_common_result_rows(rows: list[dict[str, Any]]) -> None:
    required_fields = set(COMMON_RESULT_FIELDS)
    for row in rows:
        if set(row.keys()) != required_fields:
            raise ValueError("Invalid common simulation result row shape.")


def _metric_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        metric_id = str(row.get("metric_id", "")).strip()
        if metric_id:
            index[metric_id] = row
    return index


def build_cost_summary_from_metrics(
    rows: list[dict[str, Any]],
    energy_unit_cost: float = 0.12,
    currency: str = "TRY",
) -> dict[str, Any]:
    """Return direct or derived annual cost summary for a metric row set.

    If annual_cost is available, it is used directly.
    Otherwise, total_energy is used for a simple derived estimate.
    """
    metric_map = _metric_index(rows)
    annual_cost = metric_map.get("annual_cost", {})
    direct_base = _try_float(annual_cost.get("base_value"))
    direct_scenario = _try_float(annual_cost.get("scenario_value"))

    if direct_base is not None and direct_scenario is not None:
        delta, percent_delta = _compute_delta(direct_base, direct_scenario)
        return {
            "has_data": True,
            "method": "annual_cost",
            "currency": currency,
            "base_cost": direct_base,
            "scenario_cost": direct_scenario,
            "delta": delta,
            "percent_delta": percent_delta,
            "message": "Maliyet economics/lifecycle annual_cost verisinden okundu.",
        }

    total_energy = metric_map.get("total_energy", {})
    base_energy = _try_float(total_energy.get("base_value"))
    scenario_energy = _try_float(total_energy.get("scenario_value"))

    if base_energy is not None and scenario_energy is not None and energy_unit_cost > 0:
        derived_base = base_energy * float(energy_unit_cost)
        derived_scenario = scenario_energy * float(energy_unit_cost)
        delta, percent_delta = _compute_delta(derived_base, derived_scenario)
        return {
            "has_data": True,
            "method": "estimated_from_total_energy",
            "currency": currency,
            "base_cost": derived_base,
            "scenario_cost": derived_scenario,
            "delta": delta,
            "percent_delta": percent_delta,
            "message": (
                "Maliyet annual_cost bulunamadigi icin total_energy uzerinden "
                "basit birim maliyet ile tahmin edildi."
            ),
        }

    return {
        "has_data": False,
        "method": "unavailable",
        "currency": currency,
        "base_cost": None,
        "scenario_cost": None,
        "delta": None,
        "percent_delta": None,
        "message": (
            "Maliyet verisi bulunamadi. Economics/lifecycle tanimi yoksa ilk etapta "
            "annual_cost uretilmeyebilir; tahmin icin total_energy verisi de gerekli."
        ),
    }
