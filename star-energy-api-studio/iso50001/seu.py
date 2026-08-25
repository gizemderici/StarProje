"""Onemli Enerji Kullanimi (SEU) belirleme.

ISO 50001, enerji tuketiminin buyuk bolumunu olusturan kullanimlarin ayri
tanimlanmasini ve oncelikli izlenmesini ister. Burada Pareto olcutu uygulanir:
kumulatif pay esige ulasana kadar siralanan son kullanimlar SEU sayilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# Kumulatif pay esigi. %80 yaygin uygulamadir; ISO 50001 sayisal bir esik
# dayatmaz, kurulusun olcutu tanimlamasini ister.
DEFAULT_THRESHOLD = 0.80

# Son kullanim adlarinin Turkce karsiliklari.
END_USE_LABELS = {
    "Cooling": "Sogutma",
    "Heating": "Isitma",
    "Interior Lighting": "Ic aydinlatma",
    "Exterior Lighting": "Dis aydinlatma",
    "Interior Equipment": "Ic ekipman",
    "Exterior Equipment": "Dis ekipman",
    "Fans": "Fanlar",
    "Pumps": "Pompalar",
    "Heat Rejection": "Isi atimi",
    "Humidification": "Nemlendirme",
    "Heat Recovery": "Isi geri kazanimi",
    "Water Systems": "Su sistemleri",
    "Refrigeration": "Sogutma tesisati",
}


@dataclass(frozen=True, slots=True)
class EnergyUse:
    name: str
    label: str
    energy_gj: float
    share: float
    cumulative_share: float
    is_significant: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "energy_gj": round(self.energy_gj, 2),
            "share_percent": round(100 * self.share, 1),
            "cumulative_percent": round(100 * self.cumulative_share, 1),
            "significant": self.is_significant,
        }


def classify(
    end_uses_gj: Mapping[str, float],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[EnergyUse]:
    """Son kullanimlari buyukten kucuge siralar ve SEU olanlari isaretler."""
    positive = {name: value for name, value in end_uses_gj.items() if value > 0}
    total = sum(positive.values())
    if total <= 0:
        return []

    ordered = sorted(positive.items(), key=lambda item: item[1], reverse=True)
    uses: list[EnergyUse] = []
    cumulative = 0.0
    threshold_reached = False
    for name, energy in ordered:
        share = energy / total
        cumulative += share
        # Esige ulasan kullanim da SEU'ya dahildir; esikten SONRAKI ilk
        # kullanimdan itibaren kapsam disi kalinir.
        significant = not threshold_reached
        if cumulative >= threshold:
            threshold_reached = True
        uses.append(
            EnergyUse(
                name=name,
                label=END_USE_LABELS.get(name, name),
                energy_gj=energy,
                share=share,
                cumulative_share=cumulative,
                is_significant=significant,
            )
        )
    return uses


def summary(
    end_uses_gj: Mapping[str, float],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, object]:
    uses = classify(end_uses_gj, threshold)
    significant = [use for use in uses if use.is_significant]
    total = sum(use.energy_gj for use in uses)
    return {
        "threshold_percent": round(100 * threshold, 1),
        "total_gj": round(total, 2),
        "significant_uses": [use.label for use in significant],
        "significant_share_percent": round(
            100 * sum(use.share for use in significant), 1
        ),
        "uses": [use.to_dict() for use in uses],
    }
