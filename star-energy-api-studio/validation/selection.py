"""Dogrulama noktalarinin secimi.

Pareto cephesinden gercek EnergyPlus ile kosulacak noktalar secilir. Secim
rastgele degildir; uc kural birlikte uygulanir:

1. Her amacin UC NOKTASI. Vekil model cephenin kenarlarinda en cok zorlanir.
2. TOPSIS UZLASI cozumu. Tezde onerilecek cozum budur; dogrulanmasi sarttir.
3. Cephenin geri kalanindan DUZGUN DAGILIMLI noktalar.

Ayrica secilen noktalar egitim kumesinde BULUNMAMALIDIR; aksi halde dogrulama,
modelin ezberledigi noktalari olcer ve anlamsizlasir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class ValidationPoint:
    index: int
    reason: str
    parameters: dict[str, float | str]
    predicted: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "reason": self.reason,
            "parameters": self.parameters,
            "predicted": self.predicted,
        }


def _spread_indices(front: np.ndarray, taken: set[int], count: int) -> list[int]:
    """Alinmis noktalardan en uzak noktalari sirayla secer.

    Basit bir maksimin secimi: her adimda, secilmis kumeye en uzak olan aday
    eklenir. Boylece cephenin orta bolgesi de temsil edilir.
    """
    if count <= 0 or len(front) <= len(taken):
        return []

    minimum = front.min(axis=0)
    span = front.max(axis=0) - minimum
    span[span == 0] = 1.0
    scaled = (front - minimum) / span

    chosen: list[int] = []
    selected = set(taken)
    for _ in range(count):
        candidates = [i for i in range(len(front)) if i not in selected]
        if not candidates:
            break
        reference = list(selected) or chosen
        if not reference:
            best = candidates[0]
        else:
            distances = [
                min(float(np.linalg.norm(scaled[i] - scaled[j])) for j in reference)
                for i in candidates
            ]
            best = candidates[int(np.argmax(distances))]
        chosen.append(best)
        selected.add(best)
    return chosen


def select_points(
    solutions: Sequence[Mapping[str, object]],
    objective_labels: Sequence[str],
    compromise_index: int,
    extreme_indices: Mapping[str, int],
    total: int = 8,
    training_parameters: Sequence[Mapping[str, float | str]] = (),
    exclude_training: bool = True,
) -> list[ValidationPoint]:
    """Dogrulanacak noktalari secer.

    `exclude_training` acikken egitim kumesindeki cozumler aday havuzundan
    tamamen cikarilir. Adaptif ornekleme turlerinde bu sarttir: onceki turun
    dogrulama noktalari egitim kumesine eklendigi icin, yeniden secilirlerse
    dogrulama dairesel hale gelir ve modelin ezberini olcer.
    """
    if not solutions:
        return []

    trained = {_signature(item) for item in training_parameters}
    if exclude_training and trained:
        usable = [
            index
            for index, item in enumerate(solutions)
            if _signature(item["parameters"]) not in trained  # type: ignore[arg-type]
        ]
        if not usable:
            return []
    else:
        usable = list(range(len(solutions)))

    front = np.array(
        [[float(item["objectives"][label]) for label in objective_labels] for item in solutions],
        dtype=float,
    )
    allowed = set(usable)

    reasons: dict[int, str] = {}
    for label, index in extreme_indices.items():
        if index in allowed:
            reasons.setdefault(index, f"uc nokta: {label}")
    if compromise_index in allowed:
        reasons.setdefault(compromise_index, "TOPSIS uzlasi cozumu")

    remaining = max(total - len(reasons), 0)
    excluded = set(range(len(solutions))) - allowed
    for index in _spread_indices(front, set(reasons) | excluded, remaining):
        reasons[index] = "cephe dagilimi"

    points: list[ValidationPoint] = []
    for index in sorted(reasons):
        parameters = dict(solutions[index]["parameters"])  # type: ignore[arg-type]
        reason = reasons[index]
        if _signature(parameters) in trained:
            # Egitim kumesindeki bir noktayi dogrulamak, modelin ezberini
            # olcer; isaretlenir ki rapor bunu gizlemesin.
            reason += " (UYARI: egitim kumesinde)"
        points.append(
            ValidationPoint(
                index=index,
                reason=reason,
                parameters=parameters,
                predicted={
                    label: float(solutions[index]["objectives"][label])  # type: ignore[index]
                    for label in objective_labels
                },
            )
        )
    return points


def _signature(parameters: Mapping[str, float | str]) -> tuple:
    """Parametre kumesinin karsilastirilabilir imzasi."""
    return tuple(
        (key, value if isinstance(value, str) else round(float(value), 4))
        for key, value in sorted(parameters.items())
    )


def deviation(predicted: float, actual: float) -> float:
    """Yuzde sapma. Pozitif deger vekil modelin FAZLA tahmin ettigini gosterir."""
    if actual == 0:
        return 0.0
    return 100.0 * (predicted - actual) / actual


def summarise(
    rows: Sequence[Mapping[str, object]], tolerance_percent: float = 5.0
) -> dict[str, object]:
    """Dogrulama tablosunun ozeti; Faz 7 kapisi buradan okunur."""
    deviations = [abs(float(row["deviation_percent"])) for row in rows if "deviation_percent" in row]
    worst = max(deviations) if deviations else 0.0
    return {
        "point_count": len(rows),
        "tolerance_percent": tolerance_percent,
        "max_absolute_deviation_percent": round(worst, 3),
        "mean_absolute_deviation_percent": round(
            float(np.mean(deviations)) if deviations else 0.0, 3
        ),
        "within_tolerance": worst <= tolerance_percent,
        "failing_points": [
            row["case_id"]
            for row in rows
            if abs(float(row.get("deviation_percent", 0.0))) > tolerance_percent
        ],
    }
