"""Aday vekil modeller ve degerlendirme metrikleri.

Tez "yontem tasarimi" dedigi icin en az iki adayin karsilastirilmasi gerekir.
Uc aday tanimlidir:

    polinom   2. derece + etkilesim terimleri. Yorumlanabilir: hangi degisken
              ciftinin etkilesimli oldugu katsayilardan okunur.
    kriging   Gaussian Process, Matern cekirdek. Bina enerjisi vekil modeli
              literaturunde en yaygin secim; tahmin belirsizligi de verir.
    boosting  Histogram tabanli gradient boosting. Dogrusal olmayan
              etkilesimlerde referans nokta.

OLCUT SECIMI

CVRMSE, ASHRAE Guideline 14'un kalibrasyon olcutudur ve TUM BINA ENERJISI gibi
buyuk, kararli buyuklukler icin dogru araciir. Ancak sifira YAKLASAN
buyukluklerde yaniltir: ortalamaya boldugu icin kucuk bir mutlak hata yuzde
yuzlere ciker.

Bu veri kumesinde:
    site_energy_gj   630-3763 GJ, hicbiri sifira yakin degil  -> CVRMSE uygun
    cooling_gj       231-2992 GJ, hicbiri sifira yakin degil  -> CVRMSE uygun
    heating_gj         0-312 GJ, 151 kosunun 79'u sifira yakin -> CVRMSE yaniltir
    comfort_hours      0-49158, 63'u sifira yakin              -> CVRMSE yaniltir

Bu yuzden seyrek hedefler icin ARALIGA normalize edilmis RMSE ve R2 kullanilir.
Olcut hedefe gore secilir, kapi gevsetilmez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


def build_polynomial() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("expand", PolynomialFeatures(degree=2, include_bias=False)),
            # RidgeCV: 2. derece genisleme sutun sayisini hizla buyutur,
            # duzenlilestirme olmadan model asiri uyum yapar.
            ("fit", RidgeCV(alphas=np.logspace(-3, 3, 13))),
        ]
    )


def build_kriging() -> Pipeline:
    # Sinirlar genis tutulur; dar sinirlar lbfgs'i sinira dayandirip
    # ConvergenceWarning uretiyordu. normalize_y=True hedefi olcekledigi icin
    # sabit terimin genis olmasi sorun degildir.
    kernel = (
        ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e8))
        * Matern(length_scale=1.0, length_scale_bounds=(1e-3, 1e5), nu=2.5)
        + WhiteKernel(1e-3, noise_level_bounds=(1e-10, 1e2))
    )
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "fit",
                GaussianProcessRegressor(
                    kernel=kernel,
                    normalize_y=True,
                    n_restarts_optimizer=2,
                    random_state=20260825,
                ),
            ),
        ]
    )


def build_boosting() -> Pipeline:
    return Pipeline(
        [
            (
                "fit",
                HistGradientBoostingRegressor(
                    max_iter=400,
                    learning_rate=0.06,
                    random_state=20260825,
                ),
            )
        ]
    )


CANDIDATES: dict[str, Callable[[], Pipeline]] = {
    "polinom": build_polynomial,
    "kriging": build_kriging,
    "boosting": build_boosting,
}


def cvrmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Degisim katsayisi cinsinden kok ortalama kare hata, yuzde.

    ASHRAE Guideline 14 kalibrasyon olcutuyle ayni tanim.
    """
    mean = float(np.mean(actual))
    if mean == 0:
        return float("inf")
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    return 100.0 * rmse / abs(mean)


def nmbe(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Normalize edilmis ortalama yanlilik hatasi, yuzde."""
    mean = float(np.mean(actual))
    if mean == 0:
        return float("inf")
    return 100.0 * float(np.sum(actual - predicted)) / (len(actual) * mean)


def r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    residual = float(np.sum((actual - predicted) ** 2))
    total = float(np.sum((actual - np.mean(actual)) ** 2))
    return 1.0 - residual / total if total > 0 else 0.0


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def nrmse_range(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Araliga normalize edilmis RMSE, yuzde.

    Ortalamasi sifira yaklasan buyukluklerde CVRMSE'nin yerini alir; bolen
    olarak ortalama degil gozlenen aralik kullanilir.
    """
    span = float(np.max(actual) - np.min(actual))
    if span == 0:
        return 0.0
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    return 100.0 * rmse / span


# Degerlerin buyuk bolumu sifira yaklastigi icin CVRMSE'nin yaniltici oldugu
# hedefler. Bunlarda araliga normalize RMSE ve R2 kullanilir.
SPARSE_TARGETS: frozenset[str] = frozenset({"heating_gj", "comfort_violation_hours"})

# Faz 6'nin amac fonksiyonlarini besleyen hedefler. Faz 4 kapisi bunlara
# bakar; vekil model YALNIZCA bu iki buyukluk icin kullanilir.
#
#   site_energy_gj          -> f1 EnPI
#   comfort_violation_hours -> f3 konfor ihlali
#   (f2 yatirim maliyeti analitik hesaplanir, vekil model gerektirmez)
#
# cooling_gj ve heating_gj raporlanir ama optimizasyonda kullanilmaz; kapiyi
# belirlemezler. Bu bir olcut gevsetmesi degildir: kapi, modelin fiilen
# kullanildigi yerde dogru olup olmadigini sinar.
OBJECTIVE_TARGETS: frozenset[str] = frozenset(
    {"site_energy_gj", "comfort_violation_hours"}
)


@dataclass(slots=True)
class Score:
    model: str
    target: str
    r2: float
    cvrmse: float
    nmbe: float
    mae: float
    n_samples: int
    nrmse_range: float = 0.0

    @property
    def is_sparse(self) -> bool:
        return self.target in SPARSE_TARGETS

    @property
    def metric_name(self) -> str:
        return "NRMSE(aralik)+R2" if self.is_sparse else "CVRMSE"

    @property
    def meets_target(self) -> bool:
        """Faz 4 kapisi.

        Yogun hedeflerde CVRMSE < %10 (ASHRAE G14 olcutu).
        Seyrek hedeflerde araliga normalize RMSE < %10 VE R2 > 0,90;
        CVRMSE bu buyukluklerde ortalamaya boldugu icin yaniltir.
        """
        if self.is_sparse:
            return self.nrmse_range < 10.0 and self.r2 > 0.90
        return self.cvrmse < 10.0

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "target": self.target,
            "r2": round(self.r2, 4),
            "metric": self.metric_name,
            "cvrmse_percent": round(self.cvrmse, 3),
            "nrmse_range_percent": round(self.nrmse_range, 3),
            "nmbe_percent": round(self.nmbe, 3),
            "mae": round(self.mae, 4),
            "n_samples": self.n_samples,
            "meets_target": self.meets_target,
        }


def score(model: str, target: str, actual: np.ndarray, predicted: np.ndarray) -> Score:
    return Score(
        model=model,
        target=target,
        r2=r_squared(actual, predicted),
        cvrmse=cvrmse(actual, predicted),
        nmbe=nmbe(actual, predicted),
        mae=mae(actual, predicted),
        n_samples=int(len(actual)),
        nrmse_range=nrmse_range(actual, predicted),
    )


def cross_validate(
    builder: Callable[[], Pipeline],
    features: np.ndarray,
    target: np.ndarray,
    folds: int = 5,
    seed: int = 20260825,
) -> np.ndarray:
    """k-katli capraz dogrulama; her ornek icin kat-disi tahmin dondurur.

    Kat-disi tahminler tek bir vektorde toplandigi icin metrikler tum veri
    uzerinden hesaplanabilir ve katlar arasi ortalama alma gerekmez.
    """
    if len(features) < folds:
        raise ValueError(f"{folds} kat icin en az {folds} ornek gerekir.")
    predictions = np.zeros_like(target, dtype=float)
    splitter = KFold(n_splits=folds, shuffle=True, random_state=seed)
    for train_index, test_index in splitter.split(features):
        pipeline = builder()
        pipeline.fit(features[train_index], target[train_index])
        predictions[test_index] = pipeline.predict(features[test_index])
    return predictions


def compare(
    features: np.ndarray,
    targets: dict[str, np.ndarray],
    candidates: Iterable[str] = tuple(CANDIDATES),
    folds: int = 5,
) -> list[Score]:
    """Her aday modeli her hedef icin capraz dogrular."""
    results: list[Score] = []
    for name in candidates:
        builder = CANDIDATES[name]
        for target_name, values in targets.items():
            predicted = cross_validate(builder, features, values, folds=folds)
            results.append(score(name, target_name, values, predicted))
    return results


def _selection_error(item: Score) -> float:
    """Model secerken kullanilan hata olcutu; hedefin turune gore degisir."""
    return item.nrmse_range if item.is_sparse else item.cvrmse


def best_per_target(scores: list[Score]) -> dict[str, Score]:
    """Her hedef icin en dusuk hataya sahip model."""
    best: dict[str, Score] = {}
    for item in scores:
        current = best.get(item.target)
        if current is None or _selection_error(item) < _selection_error(current):
            best[item.target] = item
    return best
