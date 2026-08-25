"""Faz 3 ornekleme tasarimi.

Karar degiskenleri engine.parameters icindeki kayittan okunur; bu modul yalnizca
o uzayi nasil tarayacagimizi tanimlar. Tam faktoriyel yerine dusuk tutarsizlikli
(Sobol) dizi kullanilir: 11 degiskende tam faktoriyel uc seviyede bile 177.147
kosu demektir, bu da yaklasik 600 gun surerdi.

Tasarima referans nokta her zaman dahil edilir. Star.zip parametrik calismasinin
cokme sebebi tam olarak buydu: taranan izgara referansi kapsamiyordu, bu yuzden
19 senaryonun hepsi referanstan kotu cikti ve raporlama betigi referansi
filtreleyip attigi icin "en iyi senaryo" olarak yanlis bir noktayi gosterdi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from engine.parameters import PARAMETERS, ParameterSpec, baseline_parameters


@dataclass(frozen=True, slots=True)
class DesignPoint:
    """Tasarim matrisinin tek satiri."""

    index: int
    parameters: dict[str, float | str]
    role: str  # "baseline" | "sample"


def _sobol_unit_matrix(dimensions: int, count: int, seed: int) -> list[list[float]]:
    """[0,1) araliginda dusuk tutarsizlikli ornekler.

    scipy varsa Sobol dizisi, yoksa scrambled Halton benzeri bir yedek kullanilir.
    Yedek yol, scipy kurulu olmayan bir makinede tasarimin uretilebilmesi icindir;
    uretim kosularinda scipy onerilir.
    """
    try:
        from scipy.stats import qmc  # type: ignore

        engine = qmc.Sobol(d=dimensions, scramble=True, seed=seed)
        return [list(row) for row in engine.random(count)]
    except ImportError:
        import random

        rng = random.Random(seed)
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        offsets = [rng.random() for _ in range(dimensions)]

        def halton(index: int, base: int) -> float:
            fraction, result, i = 1.0, 0.0, index
            while i > 0:
                fraction /= base
                result += fraction * (i % base)
                i //= base
            return result

        rows = []
        for point in range(1, count + 1):
            row = []
            for axis in range(dimensions):
                base = primes[axis % len(primes)]
                row.append((halton(point, base) + offsets[axis]) % 1.0)
            rows.append(row)
        return rows


def _map_unit_value(spec: ParameterSpec, unit_value: float) -> float | str:
    """[0,1) degerini parametrenin kendi araligina tasir."""
    if spec.is_categorical:
        index = min(int(unit_value * len(spec.choices)), len(spec.choices) - 1)
        return spec.choices[index]
    low = spec.minimum
    high = spec.maximum
    if low is None or high is None:
        raise ValueError(f"{spec.key}: surekli degisken icin alt/ust sinir gerekir.")
    return round(low + unit_value * (high - low), 6)


def build_design(
    count: int = 150,
    seed: int = 20260825,
    specs: Sequence[ParameterSpec] = PARAMETERS,
) -> list[DesignPoint]:
    """Referans nokta + `count` adet ornek uretir."""
    if count < 1:
        raise ValueError("En az bir ornek gerekir.")

    points = [DesignPoint(index=0, parameters=baseline_parameters(), role="baseline")]
    matrix = _sobol_unit_matrix(len(specs), count, seed)
    for offset, row in enumerate(matrix, start=1):
        values = {
            spec.key: _map_unit_value(spec, unit)
            for spec, unit in zip(specs, row)
        }
        points.append(DesignPoint(index=offset, parameters=values, role="sample"))
    return points


def write_design(points: Sequence[DesignPoint], path: Path, seed: int) -> Path:
    """Tasarimi yeniden uretilebilir bicimde diske yazar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed": seed,
        "count": len(points),
        "parameters": [spec.key for spec in PARAMETERS],
        "points": [
            {"index": point.index, "role": point.role, "parameters": point.parameters}
            for point in points
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
