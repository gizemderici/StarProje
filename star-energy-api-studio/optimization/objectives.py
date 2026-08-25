"""Amac fonksiyonlari ve kisitlar.

Uc amac da MINIMIZE edilir:

    f1  EnPI            kWh/m2-yil
    f2  Yatirim maliyeti TRY
    f3  Konfor ihlali    bolge-saat

Degerlendirme vekil model uzerinden yapilir (Faz 4). Vekil model hazir
degilken de bu modul kullanilabilir: `Evaluator` arayuzu herhangi bir tahmin
kaynagini kabul eder, gercek EnergyPlus kosusu dahil.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol

from engine.parameters import BY_KEY, baseline_parameters
from optimization.cost_model import CostEstimate, estimate

GJ_TO_KWH = 1000.0 / 3.6
FLOOR_AREA_M2 = 4246.18


class Evaluator(Protocol):
    """Bir senaryonun enerji ve konfor sonucunu tahmin eden kaynak."""

    def __call__(
        self, parameters: Mapping[str, float | str]
    ) -> tuple[float, float]:
        """(saha enerjisi GJ, konfor ihlali bolge-saat) dondurur."""


# --- Kisitlar ---------------------------------------------------------------

# TS 825 azami U degerleri (W/m2K). Bolge secimi VARSAYIMDIR ve dogrulanmalidir:
# Mugla ili birden fazla iklim bolgesine yayilir; bina 646 m rakimda, ic
# kesimdedir. Burada 3. bolge kabul edilmistir.
TS825_ZONE = 3
TS825_MAX_U = {
    1: {"wall": 0.70, "window": 2.40},
    2: {"wall": 0.60, "window": 2.40},
    3: {"wall": 0.50, "window": 2.00},
    4: {"wall": 0.40, "window": 1.80},
}

# Duvar U hesabi icin sabit katman direnci. duvr_std_eps konstruksiyonunun
# EPS disindaki katmanlari + yuzey filmleri.
# Dogrulama: 5 cm / 0,039 -> U = 0,290 W/m2K; EnergyPlus 0,2901 raporluyor.
WALL_FIXED_R = 1.9956
SURFACE_FILM_R = 0.13 + 0.04

# Konfor tavani: yillik bolge-saat cinsinden ust sinir.
# Taban kosusunda 118 bolge-saat olculmustur (iklimlendirilen alti bolge).
MAX_COMFORT_VIOLATION_HOURS = 500.0

# Butce tavani (TRY). Birim fiyatlar gibi bu da bir kabuldur.
MAX_BUDGET = 6_000_000.0

# Asgari olu bant. SetThermostatSetpoints measure'i bunun altini reddeder;
# kisit olmadan optimizasyon simulasyonun kosamayacagi tasarimlar uretir.
# Isitma ve sogutma araliklari ust uste bindigi icin (isitma 15-24, sogutma
# 22-30) bu kisit sart.
MIN_DEAD_BAND_K = 0.5


def wall_u_value(thickness_cm: float, conductivity_w_mk: float) -> float:
    """EPS kalinligi ve iletkenliginden duvar U degeri."""
    if conductivity_w_mk <= 0:
        raise ValueError("Isil iletkenlik sifirdan buyuk olmalidir.")
    eps_r = (thickness_cm / 100.0) / conductivity_w_mk
    return 1.0 / (WALL_FIXED_R + SURFACE_FILM_R + eps_r)


@dataclass(frozen=True, slots=True)
class Objectives:
    enpi_kwh_m2: float
    investment_cost: float
    comfort_violation_hours: float

    def as_vector(self) -> list[float]:
        return [self.enpi_kwh_m2, self.investment_cost, self.comfort_violation_hours]


@dataclass(frozen=True, slots=True)
class ConstraintCheck:
    """Kisit ihlalleri.

    Her deger <= 0 ise kisit saglanir; pozitif deger ihlal miktaridir.
    pymoo bu isareti bekler.
    """

    wall_u: float
    window_u: float
    comfort: float
    budget: float
    dead_band: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return all(value <= 0 for value in self.as_vector())

    def as_vector(self) -> list[float]:
        return [self.wall_u, self.window_u, self.comfort, self.budget, self.dead_band]


def evaluate(
    parameters: Mapping[str, float | str],
    evaluator: Evaluator,
    window_u_lookup: Mapping[str, float] | None = None,
) -> tuple[Objectives, ConstraintCheck, CostEstimate]:
    """Bir senaryoyu amac ve kisit vektorlerine cevirir.

    `window_u_lookup` cam konstruksiyonu -> U degeri esleme tablosudur; Faz 3
    kosularindan uretilir (her kosu kendi cam U degerini raporlar). Tablo
    verilmezse cam U kisiti degerlendirilmez ve bu durum notes icinde bildirilir.
    """
    values = {**baseline_parameters(), **parameters}
    energy_gj, comfort_hours = evaluator(values)
    cost = estimate(values)

    enpi = energy_gj * GJ_TO_KWH / FLOOR_AREA_M2
    objectives = Objectives(
        enpi_kwh_m2=enpi,
        investment_cost=cost.total,
        comfort_violation_hours=comfort_hours,
    )

    limits = TS825_MAX_U[TS825_ZONE]
    wall_u = wall_u_value(
        float(values["eps_thickness_cm"]), float(values["eps_conductivity_w_mk"])
    )

    notes: list[str] = []
    construction = str(values["window_construction"])
    if window_u_lookup and construction in window_u_lookup:
        window_violation = window_u_lookup[construction] - limits["window"]
    else:
        window_violation = 0.0
        notes.append(
            f"Cam U degeri bilinmiyor ({construction}); TS 825 cam kisiti "
            "degerlendirilmedi."
        )

    dead_band = float(values["cooling_setpoint_c"]) - float(values["heating_setpoint_c"])
    checks = ConstraintCheck(
        wall_u=wall_u - limits["wall"],
        window_u=window_violation,
        comfort=comfort_hours - MAX_COMFORT_VIOLATION_HOURS,
        budget=cost.total - MAX_BUDGET,
        dead_band=MIN_DEAD_BAND_K - dead_band,
        notes=notes,
    )
    return objectives, checks, cost


def window_u_from_results(rows: list[Mapping[str, object]]) -> dict[str, float]:
    """Faz 3 sonuc tablosundan cam konstruksiyonu -> U esleme tablosu."""
    lookup: dict[str, float] = {}
    for row in rows:
        construction = str(row.get("window_construction", "")).strip()
        try:
            u_value = float(row.get("glass_u_factor", 0) or 0)
        except (TypeError, ValueError):
            continue
        if construction and u_value > 0:
            lookup.setdefault(construction, u_value)
    return lookup


def describe_limits() -> dict[str, object]:
    limits = TS825_MAX_U[TS825_ZONE]
    return {
        "ts825_zone": TS825_ZONE,
        "ts825_zone_is_assumption": True,
        "max_wall_u_w_m2k": limits["wall"],
        "max_window_u_w_m2k": limits["window"],
        "max_comfort_violation_hours": MAX_COMFORT_VIOLATION_HOURS,
        "max_budget": MAX_BUDGET,
        "min_dead_band_k": MIN_DEAD_BAND_K,
        "baseline_wall_u_w_m2k": round(
            wall_u_value(
                float(baseline_parameters()["eps_thickness_cm"]),
                float(baseline_parameters()["eps_conductivity_w_mk"]),
            ),
            4,
        ),
        "decision_variables": list(BY_KEY),
    }
