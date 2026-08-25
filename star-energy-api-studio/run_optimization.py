"""Faz 6: NSGA-II ile cok amacli optimizasyon.

Vekil model hazir degilken --evaluator analytic ile calistirilabilir: bu mod
altyapiyi ucdan uca sinar ama SONUCLARI TEZDE KULLANILAMAZ. Gercek calisma icin
Faz 4 vekil modeli baglanmalidir.

Kullanim:
    python run_optimization.py --evaluator analytic --generations 40
    python run_optimization.py --evaluator surrogate --generations 200
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.mixed import MixedVariableGA
from pymoo.indicators.hv import HV
from pymoo.optimize import minimize

from engine.parameters import baseline_parameters
from optimization.objectives import window_u_from_results
from optimization.problem import (
    OBJECTIVE_LABELS,
    BuildingRetrofitProblem,
    collect_solutions,
    extreme_indices,
    normalise,
    topsis,
    write_front,
)

ROOT = Path(__file__).resolve().parent
RESULTS_CSV = ROOT / "data/parametric/results.csv"
OUTPUT = ROOT / "data/optimization"


def analytic_evaluator():
    """Vekil model yerine gecen basit, aciklanabilir tahmin.

    YALNIZCA ALTYAPI SINAMASI ICINDIR. Katsayilar taban kosusunun buyukluk
    mertebesine oturtulmustur ama hicbir simulasyona kalibre edilmemistir.
    """
    base = baseline_parameters()

    def evaluate(parameters):
        cooling_gain = 0.0
        # Cam tipi soguuma yukunu dogrudan etkiler; SHGC dususlerini kabaca
        # temsil eden sabit katsayilar.
        window_effect = {
            "penc_std_4mm": 0.0,
            "penc_renk_6mm": -60.0,
            "penc_lowe_4mm": -110.0,
            "penc_cont_6_4mm": -130.0,
            "penc_snerji_4mm": -150.0,
            "penc_lowe_argon_4mm": -160.0,
            "penc_triple_lowe_4mm": -180.0,
        }
        cooling_gain += window_effect.get(str(parameters["window_construction"]), 0.0)
        cooling_gain += -55.0 * (float(parameters["cooling_setpoint_c"]) - base["cooling_setpoint_c"])
        cooling_gain += 1119.56 * (base["chiller_cop"] / float(parameters["chiller_cop"]) - 1.0)

        heating_gain = -8.0 * (base["heating_setpoint_c"] - float(parameters["heating_setpoint_c"]))
        heating_gain += -20.0 * (base["infiltration_multiplier"] - float(parameters["infiltration_multiplier"]))
        heating_gain += -3.0 * (float(parameters["eps_thickness_cm"]) - base["eps_thickness_cm"])

        lighting_gain = 230.27 * (
            float(parameters["lighting_primary_w_m2"]) / base["lighting_primary_w_m2"] - 1.0
        )
        equipment_gain = 157.68 * (
            float(parameters["elevator_power_w"]) / base["elevator_power_w"] - 1.0
        )

        energy = 1920.0 + cooling_gain + heating_gain + lighting_gain + equipment_gain
        # Ayar noktasi bandi genisledikce konfor ihlali artar.
        band = float(parameters["cooling_setpoint_c"]) - float(parameters["heating_setpoint_c"])
        comfort = max(0.0, 118.0 + 55.0 * (band - 2.0))
        return max(energy, 1.0), comfort

    return evaluate


def load_window_lookup() -> dict[str, float]:
    if not RESULTS_CSV.is_file():
        return {}
    with RESULTS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return window_u_from_results(list(csv.DictReader(handle)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Faz 6 cok amacli optimizasyon.")
    parser.add_argument(
        "--evaluator",
        choices=("analytic", "surrogate"),
        default="analytic",
        help="analytic: altyapi sinamasi. surrogate: Faz 4 vekil modeli.",
    )
    parser.add_argument("--generations", type=int, default=40)
    parser.add_argument("--population", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260825)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    if args.evaluator == "surrogate":
        raise SystemExit(
            "Vekil model henuz bagli degil (Faz 4). Simdilik --evaluator analytic "
            "kullanin; o mod yalnizca altyapiyi sinar."
        )

    evaluator = analytic_evaluator()
    lookup = load_window_lookup()
    print(f"Cam U tablosu: {len(lookup)} konstruksiyon" + ("" if lookup else " (Faz 3 sonuclari bekleniyor)"))

    problem = BuildingRetrofitProblem(evaluator=evaluator, window_u_lookup=lookup)
    algorithm = MixedVariableGA(pop_size=args.population, survival=NSGA2().survival)

    started = time.time()
    result = minimize(
        problem,
        algorithm,
        ("n_gen", args.generations),
        seed=args.seed,
        save_history=True,
        verbose=False,
    )
    elapsed = time.time() - started

    solutions = collect_solutions(result)
    if not solutions:
        print("Uygun cozum bulunamadi; kisitlar cok siki olabilir.")
        return

    front = np.atleast_2d(result.F)

    # Hipervolum yakinsamasi. Normalize edilmis cephede referans nokta (1,1,1).
    history = []
    indicator = HV(ref_point=np.array([1.05, 1.05, 1.05]))
    for generation, entry in enumerate(result.history, start=1):
        feasible = entry.opt.get("F")
        if feasible is None or len(feasible) == 0:
            continue
        history.append(
            {
                "generation": generation,
                "front_size": int(len(feasible)),
                "hypervolume": round(float(indicator(normalise(np.atleast_2d(feasible)))), 6),
            }
        )

    compromise = topsis(front)
    extremes = extreme_indices(front)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = write_front(solutions, history, OUTPUT / "pareto_front.json", args.evaluator)

    print(f"\nDegerlendirme: {problem.evaluator.__name__ if hasattr(problem.evaluator, '__name__') else args.evaluator}")
    print(f"Nesil {args.generations} x popülasyon {args.population} -> {elapsed:.1f} sn")
    print(f"Pareto cephesi: {len(solutions)} cozum")
    if history:
        print(f"Hipervolum: {history[0]['hypervolume']:.4f} -> {history[-1]['hypervolume']:.4f}")

    print("\n=== UC NOKTALAR ===")
    for label, index in extremes.items():
        solution = solutions[index]
        print(f"  {label}")
        print("    " + " | ".join(f"{k}={v}" for k, v in solution.objectives.items()))

    print("\n=== UZLASI COZUMU (TOPSIS) ===")
    chosen = solutions[compromise]
    for key, value in chosen.objectives.items():
        print(f"  {key:<28}{value:>14,.2f}")
    print("  parametreler:")
    base = baseline_parameters()
    for key, value in sorted(chosen.parameters.items()):
        mark = "" if value == base[key] else "  <-- degisti"
        print(f"    {key:<26}{value}{mark}")

    print(f"\nCephe: {path}")
    print(
        "\nUYARI: analytic degerlendirici yalnizca altyapiyi sinar; bu sonuclar "
        "tezde kullanilamaz. Faz 4 vekil modeli baglanmalidir."
    )


if __name__ == "__main__":
    main()
