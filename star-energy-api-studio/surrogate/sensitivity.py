"""Varyans tabanli duyarlilik analizi (Sobol indisleri).

Saltelli semasi ile birinci mertebe (S1) ve toplam (ST) indisler hesaplanir.
Ek bir kutuphane gerektirmez; ornekleme scipy.stats.qmc.Sobol ile yapilir,
degerlendirme egitilmis vekil modelle.

S1  degiskenin TEK BASINA cikti varyansina katkisi
ST  etkilesimler dahil TOPLAM katkisi

ST >> S1 ise degisken baskin olarak etkilesim uzerinden calisiyordur. Bu binada
beklenen ornek: chiller COP ile sogutma ayar noktasi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from engine.parameters import PARAMETERS, BY_KEY
from surrogate.dataset import CATEGORICAL_KEYS, CONTINUOUS_KEYS, encode_row


@dataclass(slots=True)
class SensitivityIndex:
    key: str
    label: str
    first_order: float
    total: float

    @property
    def interaction_dominated(self) -> bool:
        """Etkilesim uzerinden calisan degisken."""
        return self.total > 2 * max(self.first_order, 1e-9)

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "first_order": round(self.first_order, 4),
            "total": round(self.total, 4),
            "interaction_dominated": self.interaction_dominated,
        }


def _unit_to_parameters(row: Sequence[float]) -> dict[str, float | str]:
    """[0,1) vektorunu parametre sozlugune cevirir."""
    parameters: dict[str, float | str] = {}
    for index, key in enumerate(CONTINUOUS_KEYS):
        spec = BY_KEY[key]
        parameters[key] = spec.minimum + row[index] * (spec.maximum - spec.minimum)
    offset = len(CONTINUOUS_KEYS)
    for position, key in enumerate(CATEGORICAL_KEYS):
        spec = BY_KEY[key]
        unit = row[offset + position]
        choice = min(int(unit * len(spec.choices)), len(spec.choices) - 1)
        parameters[key] = spec.choices[choice]
    return parameters


def _predict(model, rows: np.ndarray) -> np.ndarray:  # noqa: ANN001
    encoded = np.asarray(
        [encode_row(_unit_to_parameters(row)) for row in rows], dtype=float
    )
    return np.asarray(model.predict(encoded), dtype=float)


def sobol_indices(
    model,  # noqa: ANN001
    samples: int = 1024,
    seed: int = 20260825,
) -> list[SensitivityIndex]:
    """Saltelli semasiyla S1 ve ST indisleri.

    Toplam degerlendirme sayisi: samples * (dimensions + 2). Vekil model
    kullanildigi icin bu saniyeler surer; gercek EnergyPlus ile aylar surerdi.
    """
    from scipy.stats import qmc

    dimensions = len(CONTINUOUS_KEYS) + len(CATEGORICAL_KEYS)
    engine = qmc.Sobol(d=2 * dimensions, scramble=True, seed=seed)
    draw = engine.random(samples)
    matrix_a = draw[:, :dimensions]
    matrix_b = draw[:, dimensions:]

    output_a = _predict(model, matrix_a)
    output_b = _predict(model, matrix_b)
    variance = float(np.var(np.concatenate([output_a, output_b])))
    if variance <= 0:
        return []

    indices: list[SensitivityIndex] = []
    for axis, spec in enumerate(
        [BY_KEY[key] for key in CONTINUOUS_KEYS] + [BY_KEY[key] for key in CATEGORICAL_KEYS]
    ):
        matrix_ab = matrix_a.copy()
        matrix_ab[:, axis] = matrix_b[:, axis]
        output_ab = _predict(model, matrix_ab)

        # Saltelli 2010 tahmin edicileri.
        first = float(np.mean(output_b * (output_ab - output_a))) / variance
        total = float(np.mean((output_a - output_ab) ** 2)) / (2.0 * variance)
        indices.append(
            SensitivityIndex(
                key=spec.key,
                label=spec.label,
                first_order=max(first, 0.0),
                total=max(total, 0.0),
            )
        )

    indices.sort(key=lambda item: item.total, reverse=True)
    return indices


def summarise(indices: Sequence[SensitivityIndex]) -> dict[str, object]:
    return {
        "ranking": [item.key for item in indices],
        "indices": [item.to_dict() for item in indices],
        "interaction_dominated": [
            item.key for item in indices if item.interaction_dominated
        ],
        "notice": (
            "S1 degiskenin tek basina, ST etkilesimler dahil toplam katkisidir. "
            "Indisler vekil model uzerinden hesaplanir; vekil modelin dogrulugu "
            "kadar guvenilirdir."
        ),
    }
