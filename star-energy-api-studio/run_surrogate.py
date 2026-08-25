"""Faz 4: vekil model egitimi ve karsilastirmasi.

Faz 3 sonuc tablosunu okur, uc aday modeli capraz dogrular, en iyisini bagimsiz
test kumesinde olcer, Sobol duyarlilik indislerini hesaplar ve hizlanmayi olcer.

Kullanim:
    python run_surrogate.py
    python run_surrogate.py --folds 5 --test-size 0.2
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

from surrogate.dataset import TARGETS, load_dataset, minimum_rows_for
from surrogate.models import (
    CANDIDATES,
    OBJECTIVE_TARGETS,
    best_per_target,
    compare,
    score,
)
from surrogate.sensitivity import sobol_indices, summarise

ROOT = Path(__file__).resolve().parent
RESULTS_CSV = ROOT / "data/parametric/results.csv"
# Faz 7 dogrulama kosulari da gercek EnergyPlus sonuclaridir; varsa egitim
# kumesine eklenir. Adaptif ornekleme: dogrulamada sapan noktalar bir sonraki
# turda modeli iyilestirir.
VALIDATION_CSV = ROOT / "data/validation/training_rows.csv"
OUTPUT = ROOT / "data/surrogate"
SPEEDUP_REFERENCE_SECONDS = 132.0  # Olculen ortalama EnergyPlus kosu suresi.


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Faz 4 vekil model.")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--sobol-samples", type=int, default=512)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    tables = [RESULTS_CSV]
    if VALIDATION_CSV.is_file():
        tables.append(VALIDATION_CSV)
        print(f"Dogrulama kosulari egitim kumesine ekleniyor: {VALIDATION_CSV.name}")
    dataset = load_dataset(tables)
    required = minimum_rows_for(dataset.n_features)
    print(f"Egitim kumesi: {len(dataset)} satir x {dataset.n_features} ozellik")
    if len(dataset) < required:
        print(
            f"UYARI: {dataset.n_features} ozellik icin en az {required} satir onerilir. "
            "Sonuclar guvenilir olmayabilir; parametrik calismanin bitmesini bekleyin."
        )

    # Bagimsiz test kumesi capraz dogrulamadan tamamen ayri tutulur.
    train_index, test_index = train_test_split(
        np.arange(len(dataset)), test_size=args.test_size, random_state=args.seed
    )
    train_features = dataset.features[train_index]
    test_features = dataset.features[test_index]

    print(f"Egitim {len(train_index)} / test {len(test_index)} satir\n")

    print("=== CAPRAZ DOGRULAMA (egitim kumesi) ===")
    cv_scores = compare(
        train_features,
        {name: dataset.target(name)[train_index] for name in TARGETS},
        folds=args.folds,
    )
    print(f"  {'model':<12}{'hedef':<26}{'R2':>8}{'CVRMSE':>10}{'NRMSE':>9}  olcut")
    for item in sorted(cv_scores, key=lambda s: (s.target, s.cvrmse)):
        print(
            f"  {item.model:<12}{item.target:<26}{item.r2:>8.3f}"
            f"{item.cvrmse:>9.2f}%{item.nrmse_range:>8.2f}%  {item.metric_name}"
        )

    best = best_per_target(cv_scores)
    print("\n=== SECILEN MODELLER ===")
    for target, item in best.items():
        print(f"  {target:<26}{item.model:<12}CVRMSE %{item.cvrmse:.2f}")

    print("\n=== BAGIMSIZ TEST KUMESI ===")
    fitted = {}
    test_scores = []
    for target, chosen in best.items():
        pipeline = CANDIDATES[chosen.model]()
        pipeline.fit(train_features, dataset.target(target)[train_index])
        predicted = pipeline.predict(test_features)
        result = score(chosen.model, target, dataset.target(target)[test_index], predicted)
        test_scores.append(result)
        fitted[target] = pipeline
        used = target in OBJECTIVE_TARGETS
        if not used:
            gate = "gecti (kapi disi)" if result.meets_target else "kaldi (kapi disi)"
        else:
            gate = "GECTI" if result.meets_target else "KALDI"
        olcut = (
            f"NRMSE %{result.nrmse_range:.2f}"
            if result.is_sparse
            else f"CVRMSE %{result.cvrmse:.2f}"
        )
        print(
            f"  {target:<26}{chosen.model:<12}R2={result.r2:>6.3f}  "
            f"{olcut:<16}[{gate}]"
        )

    # --- Hizlanma olcumu ---
    energy_model = fitted["site_energy_gj"]
    probe = np.repeat(test_features[:1], 1000, axis=0)
    started = time.perf_counter()
    energy_model.predict(probe)
    per_call = (time.perf_counter() - started) / 1000.0
    speedup = SPEEDUP_REFERENCE_SECONDS / per_call if per_call > 0 else 0.0
    print(
        f"\n=== HIZLANMA ===\n"
        f"  vekil model : {per_call * 1e6:.1f} mikrosaniye / degerlendirme\n"
        f"  EnergyPlus  : {SPEEDUP_REFERENCE_SECONDS:.0f} saniye / kosu\n"
        f"  oran        : {speedup:,.0f}x"
    )

    # --- Duyarlilik ---
    print("\n=== SOBOL DUYARLILIK (saha enerjisi) ===")
    indices = sobol_indices(energy_model, samples=args.sobol_samples, seed=args.seed)
    print(f"  {'degisken':<28}{'S1':>8}{'ST':>8}")
    for item in indices:
        mark = "  <- etkilesim baskin" if item.interaction_dominated else ""
        print(f"  {item.label:<28}{item.first_order:>8.3f}{item.total:>8.3f}{mark}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "dataset": {
            "rows": len(dataset),
            "features": dataset.n_features,
            "recommended_minimum_rows": required,
            "sufficient": len(dataset) >= required,
            "train_rows": len(train_index),
            "test_rows": len(test_index),
        },
        "cross_validation": [item.to_dict() for item in cv_scores],
        "selected": {target: item.model for target, item in best.items()},
        "test_scores": [item.to_dict() for item in test_scores],
        "speedup": {
            "surrogate_seconds_per_call": per_call,
            "energyplus_seconds_per_run": SPEEDUP_REFERENCE_SECONDS,
            "ratio": round(speedup, 1),
        },
        "sensitivity": summarise(indices),
        "gate_targets": sorted(OBJECTIVE_TARGETS),
        "gate_passed": all(
            item.meets_target
            for item in test_scores
            if item.target in OBJECTIVE_TARGETS
        ),
        "non_gating_failures": [
            item.target
            for item in test_scores
            if item.target not in OBJECTIVE_TARGETS and not item.meets_target
        ],
    }
    (OUTPUT / "surrogate_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUTPUT / "models.pkl").open("wb") as handle:
        pickle.dump({"models": fitted, "feature_names": dataset.feature_names}, handle)

    print(f"\nRapor : {OUTPUT / 'surrogate_report.json'}")
    print(f"Model : {OUTPUT / 'models.pkl'}")
    print(f"\nFaz 4 kapisi: {'GECILDI' if report['gate_passed'] else 'GECILMEDI'}")


if __name__ == "__main__":
    main()
