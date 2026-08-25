"""Yatirim maliyeti modeli.

UYARI - BIRIM FIYATLAR VARSAYIMDIR

Buradaki birim fiyatlar piyasa teklifi degildir; buyukluk mertebesi
yerlestiricileridir. Tezde kullanilmadan once guncel piyasa listesiyle
degistirilmeli ve kaynak belirtilmelidir. Degistirmek icin yalnizca UNIT_PRICES
sozlugu duzenlenir; hesap mantigi ayni kalir.

Miktarlar ise varsayim DEGILDIR; onarilmis modelden ve taban kosusundan
okunmustur:

    Brut duvar alani      2.072,10 m2
    Cam alani             1.628,77 m2
    Opak duvar alani        443,33 m2   (brut - cam)
    Toplam bina alani     4.246,18 m2
    Chiller kapasitesi      258,74 kW
    Kazan kapasitesi        162,67 kW
    Aydinlatma birincil   2.740,74 m2  (7 W/m2)
    Aydinlatma ikincil    1.290,96 m2  (3 W/m2)

Opak duvar alaninin cam alaninin dortte biri olmasi, EPS kalinliginin bu binada
neden sinirli etki yarattigini nicel olarak aciklar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from engine.parameters import baseline_parameters

# --- Modelden okunan miktarlar (varsayim degil) -----------------------------
GROSS_WALL_AREA_M2 = 2072.10
WINDOW_AREA_M2 = 1628.77
OPAQUE_WALL_AREA_M2 = GROSS_WALL_AREA_M2 - WINDOW_AREA_M2
FLOOR_AREA_M2 = 4246.18
CHILLER_CAPACITY_KW = 258.74
BOILER_CAPACITY_KW = 162.67

# Aydinlatma tanimlarinin kapsadigi alanlar; OpenStudio SDK ile her tanima bagli
# mekanlarin alani toplanarak olculmustur. Birincil grup ofis, konferans salonu
# ve atolye (7 W/m2); ikincil grup merdiven, koridor, mecoda ve WC (3 W/m2).
# Toplam 4.031,70 m2; kalan 214,48 m2'de aydinlatma tanimi yoktur.
PRIMARY_LIGHTING_AREA_M2 = 2740.74
SECONDARY_LIGHTING_AREA_M2 = 1290.96

CURRENCY = "TRY"


# --- Birim fiyatlar (VARSAYIM - degistirilmeli) -----------------------------
UNIT_PRICES: dict[str, float] = {
    # Cam konstruksiyonlari, m2 basina takili fiyat farki (referansa gore).
    "window_penc_std_4mm": 0.0,
    "window_penc_lowe_4mm": 900.0,
    "window_penc_lowe_argon_4mm": 1150.0,
    "window_penc_cont_6_4mm": 1050.0,
    "window_penc_triple_lowe_4mm": 2100.0,
    "window_penc_snerji_4mm": 1300.0,
    "window_penc_renk_6mm": 800.0,
    # EPS: m2 basina, santimetre basina (mantolama dahil).
    "eps_per_m2_per_cm": 95.0,
    # Chiller: COP artisi icin kW basina.
    "chiller_per_kw_per_cop_step": 1800.0,
    # Kazan: verim artisi icin kW basina.
    "boiler_per_kw_per_point": 2400.0,
    # Aydinlatma: m2 basina LED donusumu.
    "lighting_per_m2": 420.0,
    # Sizdirmazlik: brut duvar alani m2 basina.
    "sealing_per_m2": 260.0,
    # Asansor motoru degisimi, sabit.
    "elevator_motor": 185000.0,
}

# Referans degerden daha kotu bir secim maliyet dogurmaz ama tasarruf da
# getirmez; negatif maliyet uretmemek icin sifira kirpilir.
MIN_ITEM_COST = 0.0


@dataclass(frozen=True, slots=True)
class CostItem:
    key: str
    label: str
    amount: float
    basis: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "amount": round(self.amount, 2),
            "basis": self.basis,
        }


@dataclass(frozen=True, slots=True)
class CostEstimate:
    total: float
    currency: str
    items: list[CostItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "total": round(self.total, 2),
            "currency": self.currency,
            "items": [item.to_dict() for item in self.items],
            "notice": (
                "Birim fiyatlar varsayimdir; guncel piyasa listesiyle "
                "degistirilmelidir. Miktarlar modelden okunmustur."
            ),
        }


def _window_cost(construction: str) -> CostItem:
    price = UNIT_PRICES.get(f"window_{construction}", 0.0)
    return CostItem(
        key="window",
        label=f"Cam degisimi ({construction})",
        amount=price * WINDOW_AREA_M2,
        basis=f"{WINDOW_AREA_M2:.2f} m2 x {price:.2f} {CURRENCY}/m2",
    )


def _eps_cost(thickness_cm: float, baseline_cm: float) -> CostItem:
    added = max(thickness_cm - baseline_cm, MIN_ITEM_COST)
    price = UNIT_PRICES["eps_per_m2_per_cm"]
    return CostItem(
        key="eps",
        label=f"EPS kalinlik artisi (+{added:.2f} cm)",
        amount=added * price * OPAQUE_WALL_AREA_M2,
        basis=f"{OPAQUE_WALL_AREA_M2:.2f} m2 x {added:.2f} cm x {price:.2f} {CURRENCY}/m2-cm",
    )


def _chiller_cost(cop: float, baseline_cop: float) -> CostItem:
    steps = max(cop - baseline_cop, MIN_ITEM_COST)
    price = UNIT_PRICES["chiller_per_kw_per_cop_step"]
    return CostItem(
        key="chiller",
        label=f"Chiller COP artisi (+{steps:.2f})",
        amount=steps * price * CHILLER_CAPACITY_KW,
        basis=f"{CHILLER_CAPACITY_KW:.2f} kW x {steps:.2f} COP x {price:.2f} {CURRENCY}/kW",
    )


def _boiler_cost(efficiency: float, baseline_efficiency: float) -> CostItem:
    points = max(100.0 * (efficiency - baseline_efficiency), MIN_ITEM_COST)
    price = UNIT_PRICES["boiler_per_kw_per_point"]
    return CostItem(
        key="boiler",
        label=f"Kazan verim artisi (+{points:.1f} puan)",
        amount=points * price * BOILER_CAPACITY_KW / 100.0,
        basis=f"{BOILER_CAPACITY_KW:.2f} kW x {points:.1f} puan",
    )


def _lighting_cost(
    primary: float, secondary: float, base_primary: float, base_secondary: float
) -> CostItem:
    price = UNIT_PRICES["lighting_per_m2"]
    area = 0.0
    if primary < base_primary:
        area += PRIMARY_LIGHTING_AREA_M2
    if secondary < base_secondary:
        area += SECONDARY_LIGHTING_AREA_M2
    return CostItem(
        key="lighting",
        label="LED donusumu",
        amount=area * price,
        basis=f"{area:.2f} m2 x {price:.2f} {CURRENCY}/m2",
    )


def _sealing_cost(multiplier: float, baseline_multiplier: float) -> CostItem:
    # Sizdirmazlik iyilestirmesi carpani DUSURUR; maliyet dusus miktariyla
    # orantilidir. Carpani artirmak (daha sizdiran bina) bir yatirim degildir.
    reduction = max(baseline_multiplier - multiplier, MIN_ITEM_COST)
    price = UNIT_PRICES["sealing_per_m2"]
    return CostItem(
        key="sealing",
        label=f"Sizdirmazlik iyilestirmesi (-{100 * reduction:.0f}%)",
        amount=reduction * price * GROSS_WALL_AREA_M2,
        basis=f"{GROSS_WALL_AREA_M2:.2f} m2 x {reduction:.2f} x {price:.2f} {CURRENCY}/m2",
    )


def _elevator_cost(power_w: float, baseline_power_w: float) -> CostItem:
    # Motor degisimi ya yapilir ya yapilmaz; kismi maliyet yoktur.
    replaced = power_w < baseline_power_w
    return CostItem(
        key="elevator",
        label="Asansor motoru degisimi",
        amount=UNIT_PRICES["elevator_motor"] if replaced else 0.0,
        basis="sabit" if replaced else "degisim yok",
    )


def estimate(parameters: Mapping[str, float | str]) -> CostEstimate:
    """Bir senaryonun referansa gore yatirim maliyeti."""
    base = baseline_parameters()
    values = {**base, **parameters}

    items = [
        _window_cost(str(values["window_construction"])),
        _eps_cost(float(values["eps_thickness_cm"]), float(base["eps_thickness_cm"])),
        _chiller_cost(float(values["chiller_cop"]), float(base["chiller_cop"])),
        _boiler_cost(float(values["boiler_efficiency"]), float(base["boiler_efficiency"])),
        _lighting_cost(
            float(values["lighting_primary_w_m2"]),
            float(values["lighting_secondary_w_m2"]),
            float(base["lighting_primary_w_m2"]),
            float(base["lighting_secondary_w_m2"]),
        ),
        _sealing_cost(
            float(values["infiltration_multiplier"]),
            float(base["infiltration_multiplier"]),
        ),
        _elevator_cost(float(values["elevator_power_w"]), float(base["elevator_power_w"])),
    ]
    return CostEstimate(
        total=sum(item.amount for item in items), currency=CURRENCY, items=items
    )


def zero_cost_measures(parameters: Mapping[str, float | str]) -> list[str]:
    """Yatirim gerektirmeyen degisiklikler.

    Ayar noktalari yalnizca isletme ayaridir; ISO 50001 acisindan en makbul
    eylem tipidir ve maliyet modeline girmez.
    """
    base = baseline_parameters()
    values = {**base, **parameters}
    changed = []
    for key in ("heating_setpoint_c", "cooling_setpoint_c"):
        if values[key] != base[key]:
            changed.append(key)
    return changed
