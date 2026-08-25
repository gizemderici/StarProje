"""NSGA-II problem tanimi.

Tasarim uzayi karmadir: on surekli degisken + bir kategorik (cam tipi). pymoo'nun
MixedVariableGA operatorleri bu birlesimi dogrudan destekler; kategorik degiskeni
sayisallastirip yuvarlamak yerine Choice olarak tasimak, gecersiz ara degerler
uretilmesini onler.

Degerlendirme vekil model uzerinden yapilir. Gercek EnergyPlus ile calistirmak da
mumkundur ama pratik degildir: kosu basina yaklasik 2 dakika surer, tipik bir
NSGA-II calismasi 10.000+ degerlendirme ister. Vekil modelin varlik sebebi tam
olarak budur ve tezde boyle gerekcelendirilmelidir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Choice, Real

from engine.parameters import PARAMETERS, baseline_parameters
from optimization.objectives import Evaluator, evaluate

OBJECTIVE_LABELS = (
    "EnPI (kWh/m2-yil)",
    "Yatirim maliyeti (TRY)",
    "Konfor ihlali (bolge-saat)",
)

CONSTRAINT_LABELS = (
    "TS 825 duvar U",
    "TS 825 cam U",
    "Konfor tavani",
    "Butce tavani",
    "Asgari olu bant",
)


def build_variables() -> dict[str, object]:
    """engine.parameters kaydindan pymoo degisken tanimlari."""
    variables: dict[str, object] = {}
    for spec in PARAMETERS:
        if spec.is_categorical:
            variables[spec.key] = Choice(options=list(spec.choices))
        else:
            variables[spec.key] = Real(bounds=(spec.minimum, spec.maximum))
    return variables


class BuildingRetrofitProblem(ElementwiseProblem):
    """Uc amacli, bes kisitli bina yenileme problemi."""

    def __init__(
        self,
        evaluator: Evaluator,
        window_u_lookup: Mapping[str, float] | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.window_u_lookup = dict(window_u_lookup or {})
        super().__init__(vars=build_variables(), n_obj=3, n_ieq_constr=5)

    def _evaluate(self, x, out, *args, **kwargs):  # noqa: ANN001
        objectives, checks, _ = evaluate(
            parameters=dict(x),
            evaluator=self.evaluator,
            window_u_lookup=self.window_u_lookup,
        )
        out["F"] = objectives.as_vector()
        out["G"] = checks.as_vector()


@dataclass(frozen=True, slots=True)
class ParetoSolution:
    parameters: dict[str, float | str]
    objectives: dict[str, float]
    constraints: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "parameters": self.parameters,
            "objectives": self.objectives,
            "constraints": self.constraints,
        }


def collect_solutions(result) -> list[ParetoSolution]:  # noqa: ANN001
    """pymoo sonucunu okunabilir cozum listesine cevirir."""
    if result.X is None:
        return []
    designs = result.X if isinstance(result.X, (list, np.ndarray)) else [result.X]
    objectives = np.atleast_2d(result.F)
    constraints = np.atleast_2d(result.G) if result.G is not None else None

    solutions: list[ParetoSolution] = []
    for index, design in enumerate(designs):
        values = dict(design)
        solutions.append(
            ParetoSolution(
                parameters={
                    key: (value if isinstance(value, str) else round(float(value), 6))
                    for key, value in values.items()
                },
                objectives={
                    label: round(float(objectives[index][axis]), 4)
                    for axis, label in enumerate(OBJECTIVE_LABELS)
                },
                constraints=(
                    {
                        label: round(float(constraints[index][axis]), 4)
                        for axis, label in enumerate(CONSTRAINT_LABELS)
                    }
                    if constraints is not None
                    else {}
                ),
            )
        )
    return solutions


def normalise(front: np.ndarray) -> np.ndarray:
    """Amaclari [0,1] araligina tasir.

    Uc amacin birimleri ve buyukluk mertebeleri cok farklidir (kWh/m2 ~ 100,
    TRY ~ 10^6, saat ~ 10^2). Hipervolum ve TOPSIS gibi olculer
    normalizasyonsuz en buyuk olcekli amaci baskin hale getirir.
    """
    minimum = front.min(axis=0)
    span = front.max(axis=0) - minimum
    span[span == 0] = 1.0
    return (front - minimum) / span


def topsis(front: np.ndarray, weights: Sequence[float] | None = None) -> int:
    """Uzlasi cozumunu secer; ideal noktaya en yakin cozumun indisini dondurur."""
    if len(front) == 0:
        raise ValueError("Bos Pareto cephesi.")
    scaled = normalise(np.atleast_2d(front))
    weight_vector = np.asarray(weights if weights is not None else [1 / 3] * scaled.shape[1])
    weight_vector = weight_vector / weight_vector.sum()
    weighted = scaled * weight_vector

    # Butun amaclar minimize edildigi icin ideal nokta orijindir.
    best = weighted.min(axis=0)
    worst = weighted.max(axis=0)
    to_best = np.linalg.norm(weighted - best, axis=1)
    to_worst = np.linalg.norm(weighted - worst, axis=1)
    closeness = np.divide(
        to_worst, to_best + to_worst, out=np.zeros_like(to_worst), where=(to_best + to_worst) > 0
    )
    return int(np.argmax(closeness))


def extreme_indices(front: np.ndarray) -> dict[str, int]:
    """Her amacta en iyi cozumun indisi."""
    array = np.atleast_2d(front)
    return {
        label: int(np.argmin(array[:, axis]))
        for axis, label in enumerate(OBJECTIVE_LABELS)
    }


def write_front(
    solutions: Sequence[ParetoSolution],
    history: Sequence[dict[str, float]],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "objective_labels": list(OBJECTIVE_LABELS),
        "constraint_labels": list(CONSTRAINT_LABELS),
        "baseline_parameters": baseline_parameters(),
        "solution_count": len(solutions),
        "convergence": list(history),
        "solutions": [solution.to_dict() for solution in solutions],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
