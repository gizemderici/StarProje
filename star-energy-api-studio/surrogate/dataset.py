"""Vekil model egitim verisinin hazirlanmasi.

Faz 3 sonuc tablosunu okur, kategorik degiskeni one-hot kodlar ve hedefleri
ayirir. Olcekleme model boru hattinin icinde yapilir (StandardScaler), boylece
capraz dogrulamada egitim katmanindan test katmanina bilgi sizmasi olmaz.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from engine.parameters import PARAMETERS, BY_KEY

# Vekil modelin tahmin edecegi hedefler. Faz 6'nin uc amac fonksiyonu bunlardan
# beslenir: site_energy_gj -> EnPI, comfort_violation_hours -> konfor.
TARGETS: tuple[str, ...] = (
    "site_energy_gj",
    "cooling_gj",
    "heating_gj",
    "comfort_violation_hours",
)

CONTINUOUS_KEYS: tuple[str, ...] = tuple(
    spec.key for spec in PARAMETERS if not spec.is_categorical
)
CATEGORICAL_KEYS: tuple[str, ...] = tuple(
    spec.key for spec in PARAMETERS if spec.is_categorical
)


@dataclass(slots=True)
class Dataset:
    features: np.ndarray
    targets: dict[str, np.ndarray]
    feature_names: list[str]
    case_ids: list[str]

    def __len__(self) -> int:
        return int(self.features.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.features.shape[1])

    def target(self, name: str) -> np.ndarray:
        if name not in self.targets:
            raise KeyError(f"Bilinmeyen hedef: {name}")
        return self.targets[name]


def feature_names() -> list[str]:
    """One-hot kodlama sonrasi sutun adlari."""
    names = list(CONTINUOUS_KEYS)
    for key in CATEGORICAL_KEYS:
        for choice in BY_KEY[key].choices:
            names.append(f"{key}={choice}")
    return names


def encode_row(parameters: dict[str, float | str]) -> list[float]:
    """Tek bir parametre sozlugunu ozellik vektorune cevirir.

    Kategorik degisken one-hot kodlanir. Sayisallastirip tek sutuna sikistirmak,
    modele var olmayan bir siralama ogretirdi (cam tipleri arasinda dogal bir
    sira yoktur).
    """
    vector = [float(parameters[key]) for key in CONTINUOUS_KEYS]
    for key in CATEGORICAL_KEYS:
        value = str(parameters[key])
        vector.extend(1.0 if value == choice else 0.0 for choice in BY_KEY[key].choices)
    return vector


def load_dataset(results_csv: Path, targets: Sequence[str] = TARGETS) -> Dataset:
    """Faz 3 sonuc tablosunu egitim kumesine cevirir."""
    if not results_csv.is_file():
        raise FileNotFoundError(f"Sonuc tablosu bulunamadi: {results_csv}")

    with results_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Sonuc tablosu bos: {results_csv}")

    vectors: list[list[float]] = []
    collected: dict[str, list[float]] = {name: [] for name in targets}
    case_ids: list[str] = []
    skipped = 0

    for row in rows:
        try:
            parameters: dict[str, float | str] = {}
            for spec in PARAMETERS:
                raw = row[spec.key]
                parameters[spec.key] = raw if spec.is_categorical else float(raw)
            values = {name: float(row[name]) for name in targets}
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue

        # Sifir enerjili satir yarida kesilmis bir kosunun izidir; egitim
        # kumesine girerse modeli bozar.
        if values.get("site_energy_gj", 1.0) <= 0:
            skipped += 1
            continue

        vectors.append(encode_row(parameters))
        for name in targets:
            collected[name].append(values[name])
        case_ids.append(row.get("case_id", ""))

    if not vectors:
        raise ValueError(
            f"{results_csv} icinde kullanilabilir satir yok ({skipped} satir atlandi)."
        )

    return Dataset(
        features=np.asarray(vectors, dtype=float),
        targets={name: np.asarray(values, dtype=float) for name, values in collected.items()},
        feature_names=feature_names(),
        case_ids=case_ids,
    )


def minimum_rows_for(n_features: int, ratio: float = 3.0) -> int:
    """Anlamli bir egitim icin gereken asgari satir sayisi.

    Ozellik sayisinin birkac kati satir olmadan capraz dogrulama sonuclari
    guvenilir degildir; 11 degisken one-hot sonrasi 17 sutuna cikar.
    """
    return int(n_features * ratio)
