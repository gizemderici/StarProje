from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .sql_results import ArchivedScenario


@dataclass(slots=True)
class EstimatorAssumptions:
    """Hızlı modelin açık ve kullanıcı tarafından değiştirilebilir varsayımları."""

    baseline_thickness_cm: float = 5.0
    eps_conductivity_w_mk: float = 0.039
    # Arsivlenmis referans kosunun EPS iletkenligi. Kullanici eps_conductivity
    # degerini degistirdiginde BAZ DEGISMEZ; baz, o kosunun kendi degeriyle
    # hesaplanmalidir. Aksi halde ayni kalinlikta farkli bir iletkenlik secmek
    # "tasarruf yok" sonucu verir.
    baseline_conductivity_w_mk: float = 0.039
    fixed_layer_r_m2k_w: float = 1.9956
    interior_surface_r_m2k_w: float = 0.13
    exterior_surface_r_m2k_w: float = 0.04
    heating_envelope_share: float = 0.55
    cooling_envelope_share: float = 0.18
    fan_load_follow_share: float = 0.10
    pump_load_follow_share: float = 0.20


@dataclass(slots=True)
class EstimatePoint:
    thickness_cm: float
    conductivity_w_mk: float
    wall_r_m2k_w: float
    wall_u_w_m2k: float
    site_energy_gj: float
    eui_mj_m2: float
    heating_gj: float
    cooling_gj: float
    fan_gj: float
    pump_gj: float
    savings_gj: float
    savings_percent: float
    method: str = "Kalibre edilmemiş hızlı tahmin"

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


def wall_performance(
    thickness_cm: float,
    conductivity_w_mk: float,
    assumptions: EstimatorAssumptions | None = None,
) -> tuple[float, float]:
    assumptions = assumptions or EstimatorAssumptions()
    if thickness_cm <= 0:
        raise ValueError("EPS kalınlığı sıfırdan büyük olmalıdır.")
    if conductivity_w_mk <= 0:
        raise ValueError("Isıl iletkenlik sıfırdan büyük olmalıdır.")
    eps_r = thickness_cm / 100.0 / conductivity_w_mk
    total_r = (
        assumptions.fixed_layer_r_m2k_w
        + assumptions.interior_surface_r_m2k_w
        + assumptions.exterior_surface_r_m2k_w
        + eps_r
    )
    return total_r, 1.0 / total_r


def estimate_point(
    thickness_cm: float,
    baseline: ArchivedScenario,
    assumptions: EstimatorAssumptions | None = None,
) -> EstimatePoint:
    assumptions = assumptions or EstimatorAssumptions()
    # HATA DUZELTMESI: baz duvar, kullanicinin sectigi iletkenlikle degil
    # arsiv kosusunun kendi iletkenligiyle hesaplanir.
    baseline_r, baseline_u = wall_performance(
        assumptions.baseline_thickness_cm,
        assumptions.baseline_conductivity_w_mk,
        assumptions,
    )
    wall_r, wall_u = wall_performance(
        thickness_cm,
        assumptions.eps_conductivity_w_mk,
        assumptions,
    )
    del baseline_r
    u_ratio = wall_u / baseline_u

    base_heating = baseline.end_uses_gj.get("Heating", 0.0)
    base_cooling = baseline.end_uses_gj.get("Cooling", 0.0)
    base_fan = baseline.end_uses_gj.get("Fans", 0.0)
    base_pump = baseline.end_uses_gj.get("Pumps", 0.0)

    heating_factor = (1.0 - assumptions.heating_envelope_share) + (
        assumptions.heating_envelope_share * u_ratio
    )
    cooling_factor = (1.0 - assumptions.cooling_envelope_share) + (
        assumptions.cooling_envelope_share * u_ratio
    )
    hvac_factor = (heating_factor + cooling_factor) / 2.0
    fan_factor = (1.0 - assumptions.fan_load_follow_share) + (
        assumptions.fan_load_follow_share * hvac_factor
    )
    pump_factor = (1.0 - assumptions.pump_load_follow_share) + (
        assumptions.pump_load_follow_share * hvac_factor
    )

    heating = base_heating * heating_factor
    cooling = base_cooling * cooling_factor
    fan = base_fan * fan_factor
    pump = base_pump * pump_factor
    base_adjusted = base_heating + base_cooling + base_fan + base_pump
    new_adjusted = heating + cooling + fan + pump
    site_energy = baseline.site_energy_gj - base_adjusted + new_adjusted
    savings = baseline.site_energy_gj - site_energy
    savings_percent = (
        100.0 * savings / baseline.site_energy_gj
        if baseline.site_energy_gj > 0
        else 0.0
    )
    eui = (
        site_energy * 1000.0 / baseline.total_area_m2
        if baseline.total_area_m2 > 0
        else 0.0
    )
    return EstimatePoint(
        thickness_cm=round(float(thickness_cm), 2),
        conductivity_w_mk=round(assumptions.eps_conductivity_w_mk, 4),
        wall_r_m2k_w=round(wall_r, 4),
        wall_u_w_m2k=round(wall_u, 4),
        site_energy_gj=round(site_energy, 3),
        eui_mj_m2=round(eui, 3),
        heating_gj=round(heating, 3),
        cooling_gj=round(cooling, 3),
        fan_gj=round(fan, 3),
        pump_gj=round(pump, 3),
        savings_gj=round(savings, 3),
        savings_percent=round(savings_percent, 3),
    )


def run_parametric(
    thicknesses_cm: Iterable[float],
    baseline: ArchivedScenario,
    assumptions: EstimatorAssumptions | None = None,
) -> list[EstimatePoint]:
    assumptions = assumptions or EstimatorAssumptions()
    unique = sorted({round(float(value), 4) for value in thicknesses_cm})
    if not unique:
        raise ValueError("En az bir EPS kalınlığı verilmelidir.")
    return [estimate_point(value, baseline, assumptions) for value in unique]


def balance_point(points: list[EstimatePoint], threshold_percent_per_cm: float = 0.12) -> EstimatePoint:
    """Marjinal enerji kazancının yavaşladığı ilk noktayı döndürür."""

    if not points:
        raise ValueError("Denge noktası için sonuç bulunamadı.")
    ordered = sorted(points, key=lambda item: item.thickness_cm)
    for previous, current in zip(ordered, ordered[1:]):
        delta_cm = current.thickness_cm - previous.thickness_cm
        if delta_cm <= 0:
            continue
        marginal = (current.savings_percent - previous.savings_percent) / delta_cm
        if marginal < threshold_percent_per_cm and current.thickness_cm > 5:
            return current
    return ordered[-1]


def export_results(
    points: list[EstimatePoint],
    output_dir: Path,
    assumptions: EstimatorAssumptions,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "parametrik_sonuclar.csv"
    json_path = output_dir / "parametrik_sonuclar.json"
    rows = [point.to_dict() for point in points]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(
        json.dumps(
            {
                "mode": "uncalibrated_quick_estimate",
                "notice": (
                    "Bu sonuçlar arşivdeki 5 cm EnergyPlus koşusuna DAYANAN, ancak "
                    "kalibre EDİLMEMİŞ bir hızlı tahmindir. Arşivdeki 5/10/15 cm "
                    "koşuları birebir aynı sonucu verdiği için elde tek veri noktası "
                    "vardır; zarf payları (heating_envelope_share, "
                    "cooling_envelope_share) varsayımdır. Kalibre edilmiş tahmin için "
                    "Faz 4 vekil modelini kullanın."
                ),
                "assumptions": asdict(assumptions),
                "results": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return csv_path, json_path
