"""Derece-gun hesabi ve normalizasyon degiskenleri.

Butun degerler dogrudan EPW dosyasindan uretilir; dis veri gerekmez. Saf Python
kullanilir cunku bu makinede numpy.random Application Control tarafindan
engellidir (bkz. docs/faz3_parametrik_calisma.md).

ISO 50006, enerji performans gostergelerinin ilgili degiskenlere gore
normalize edilmesini ister. Bu bina icin ilgili degiskenler iklim (derece-gun)
ve kullanim yogunlugudur.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# EPW veri satirlarinda kuru termometre sicakligi 7. alandir (0 tabanli 6).
EPW_HEADER_LINES = 8
EPW_DRY_BULB_INDEX = 6

# EnergyPlus eksik veri isareti.
EPW_MISSING = 99.9


@dataclass(frozen=True, slots=True)
class DegreeDays:
    """Yillik ve aylik derece-gun toplamlari."""

    heating_base_c: float
    cooling_base_c: float
    hdd: float
    cdd: float
    monthly_hdd: list[float]
    monthly_cdd: list[float]
    hours_used: int
    mean_temperature_c: float

    def to_dict(self) -> dict[str, object]:
        return {
            "heating_base_c": self.heating_base_c,
            "cooling_base_c": self.cooling_base_c,
            "hdd": round(self.hdd, 2),
            "cdd": round(self.cdd, 2),
            "monthly_hdd": [round(value, 2) for value in self.monthly_hdd],
            "monthly_cdd": [round(value, 2) for value in self.monthly_cdd],
            "hours_used": self.hours_used,
            "mean_temperature_c": round(self.mean_temperature_c, 2),
        }


def read_hourly_temperatures(epw_path: Path) -> list[tuple[int, float]]:
    """(ay, kuru termometre) ciftlerini dondurur."""
    rows: list[tuple[int, float]] = []
    with epw_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        for index, record in enumerate(reader):
            if index < EPW_HEADER_LINES:
                continue
            if len(record) <= EPW_DRY_BULB_INDEX:
                continue
            try:
                month = int(record[1])
                temperature = float(record[EPW_DRY_BULB_INDEX])
            except ValueError:
                continue
            if temperature >= EPW_MISSING:
                continue
            rows.append((month, temperature))
    return rows


def degree_days(
    epw_path: Path,
    heating_base_c: float = 18.0,
    cooling_base_c: float = 22.0,
) -> DegreeDays:
    """Saatlik yontemle derece-gun hesaplar.

    Saatlik yontem gunluk ortalamaya gore daha dogrudur: gun icinde hem isitma
    hem sogutma ihtiyaci olan gecis mevsimlerinde gunluk ortalama ikisini de
    gizler.

    Taban sicakliklari TS 825 ve yaygin uygulamayla uyumlu secilmistir; ikisi de
    parametredir ve duyarlilik analizi icin degistirilebilir.
    """
    readings = read_hourly_temperatures(epw_path)
    if not readings:
        raise ValueError(f"EPW dosyasindan sicaklik okunamadi: {epw_path}")

    monthly_hdd = [0.0] * 12
    monthly_cdd = [0.0] * 12
    total = 0.0
    for month, temperature in readings:
        index = min(max(month - 1, 0), 11)
        if temperature < heating_base_c:
            monthly_hdd[index] += (heating_base_c - temperature) / 24.0
        if temperature > cooling_base_c:
            monthly_cdd[index] += (temperature - cooling_base_c) / 24.0
        total += temperature

    return DegreeDays(
        heating_base_c=heating_base_c,
        cooling_base_c=cooling_base_c,
        hdd=sum(monthly_hdd),
        cdd=sum(monthly_cdd),
        monthly_hdd=monthly_hdd,
        monthly_cdd=monthly_cdd,
        hours_used=len(readings),
        mean_temperature_c=total / len(readings),
    )
