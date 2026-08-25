"""Enerji taban cizgisi (EnB) ve enerji performans gostergeleri (EnPI).

ISO 50001 icin gereken iki nesne burada uretilir. Onemli sinirlilik:

    Bu calismada EnB, olculmus tuketime degil ONARILMIS SIMULASYON MODELINE
    dayanir. Elde 12 aylik fatura veya sayac verisi yoktur, bu yuzden model
    ASHRAE Guideline 14 olcutlerine gore kalibre edilememistir.

Sonuc olarak mutlak degerler degil, senaryolar arasi GORELI degisimler
yorumlanmalidir. Bu, optimizasyon calismasini gecersiz kilmaz; cok amacli
optimizasyon zaten goreli karsilastirma uzerine kuruludur. Ancak tezde acikca
beyan edilmelidir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

GJ_TO_KWH = 1000.0 / 3.6


@dataclass(frozen=True, slots=True)
class EnergyBaseline:
    """Referans senaryo. ISO 50001 terimiyle enerji taban cizgisi."""

    source: str
    site_energy_gj: float
    total_area_m2: float
    occupant_count: float
    hdd: float
    cdd: float
    measured: bool = False

    @property
    def site_energy_kwh(self) -> float:
        return self.site_energy_gj * GJ_TO_KWH

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "measured": self.measured,
            "site_energy_gj": round(self.site_energy_gj, 2),
            "site_energy_kwh": round(self.site_energy_kwh, 1),
            "total_area_m2": round(self.total_area_m2, 2),
            "occupant_count": round(self.occupant_count, 1),
            "hdd": round(self.hdd, 1),
            "cdd": round(self.cdd, 1),
            "notice": (
                "Simulasyon tabanli referans senaryo. Olculmus taban cizgisi degildir; "
                "model faturaya kalibre edilmemistir."
            ),
        }


@dataclass(frozen=True, slots=True)
class Indicator:
    key: str
    label: str
    value: float
    unit: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "value": round(self.value, 4),
            "unit": self.unit,
        }


def indicators(
    site_energy_gj: float,
    baseline: EnergyBaseline,
) -> list[Indicator]:
    """Bir senaryo icin EnPI kumesi.

    Iklim degiskenleri senaryolar arasinda sabit oldugu icin (ayni EPW), derece-gun
    normalize gosterge bu calismada senaryolari birbirinden ayirmaz. Yine de
    hesaplanir: farkli hava yillariyla veya baska bir binayla karsilastirma
    yapildiginda ISO 50006'nin istedigi normalizasyon budur.
    """
    kwh = site_energy_gj * GJ_TO_KWH
    degree_days_total = baseline.hdd + baseline.cdd

    values = [
        Indicator(
            key="eui_kwh_m2",
            label="Birim alan basina yillik enerji",
            value=kwh / baseline.total_area_m2 if baseline.total_area_m2 else 0.0,
            unit="kWh/m2-yil",
        ),
        Indicator(
            key="energy_per_occupant_kwh",
            label="Kisi basina yillik enerji",
            value=kwh / baseline.occupant_count if baseline.occupant_count else 0.0,
            unit="kWh/kisi-yil",
        ),
        Indicator(
            key="eui_per_degree_day",
            label="Derece-gun normalize gosterge",
            value=(
                kwh / (baseline.total_area_m2 * degree_days_total)
                if baseline.total_area_m2 and degree_days_total
                else 0.0
            ),
            unit="kWh/m2-DG",
        ),
    ]
    return values


def improvement(
    scenario_energy_gj: float,
    baseline: EnergyBaseline,
) -> dict[str, float]:
    """Taban cizgisine gore iyilesme.

    Pozitif deger tasarruf, negatif deger artis anlamina gelir.
    """
    if baseline.site_energy_gj <= 0:
        return {"absolute_gj": 0.0, "percent": 0.0}
    absolute = baseline.site_energy_gj - scenario_energy_gj
    return {
        "absolute_gj": round(absolute, 2),
        "percent": round(100 * absolute / baseline.site_energy_gj, 3),
    }


def scenario_report(
    scenario_energy_gj: float,
    baseline: EnergyBaseline,
    parameters: Mapping[str, float | str] | None = None,
) -> dict[str, object]:
    return {
        "parameters": dict(parameters or {}),
        "site_energy_gj": round(scenario_energy_gj, 2),
        "indicators": [item.to_dict() for item in indicators(scenario_energy_gj, baseline)],
        "improvement": improvement(scenario_energy_gj, baseline),
    }
