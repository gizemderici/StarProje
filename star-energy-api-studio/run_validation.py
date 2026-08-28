"""Faz 7: simulasyon destekli sayisal dogrulama.

Pareto cephesinden secilen noktalari GERCEK EnergyPlus ile kosturur ve vekil
model tahminiyle karsilastirir. Tezin basligindaki "simulasyon destekli sayisal
dogrulama" ifadesinin karsiligi bu betigin urettigi tablodur.

Kullanim:
    python run_validation.py --points 8
    python run_validation.py --harvest-only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from engine.openstudio_runner import OpenStudioCase, run_cases
from engine.results import harvest_all
from optimization.problem import OBJECTIVE_LABELS, extreme_indices, topsis
from validation.selection import ValidationPoint, deviation, select_points, summarise

ROOT = Path(__file__).resolve().parent
PARETO_JSON = ROOT / "data/optimization/pareto_front.json"
RESULTS_CSV = ROOT / "data/parametric/results.csv"
RUNS_ROOT = ROOT / "data/validation/runs"
OUTPUT = ROOT / "data/validation"

# Vekil modelin tahmin ettigi saha enerjisi EnPI uzerinden verilir; karsilastirma
# icin geri cevrilir.
GJ_TO_KWH = 1000.0 / 3.6
FLOOR_AREA_M2 = 4246.18


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Faz 7 dogrulama.")
    parser.add_argument("--points", type=int, default=8)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--tolerance", type=float, default=5.0)
    parser.add_argument(
        "--harvest-only",
        action="store_true",
        help="Yeni kosu baslatma; mevcut dogrulama kosularini topla.",
    )
    return parser.parse_args()


def load_training_parameters() -> list[dict[str, float | str]]:
    if not RESULTS_CSV.is_file():
        return []
    with RESULTS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def choose_points(count: int) -> tuple[list[ValidationPoint], dict]:
    if not PARETO_JSON.is_file():
        raise SystemExit(
            f"Pareto cephesi bulunamadi: {PARETO_JSON}\n"
            "Once run_optimization.py calistirilmalidir."
        )
    payload = json.loads(PARETO_JSON.read_text(encoding="utf-8"))
    if not payload.get("usable_in_thesis", False):
        print(
            "UYARI: cephe '"
            + str(payload.get("evaluator", "?"))
            + "' degerlendiricisiyle uretilmis. Dogrulama yine calisir ama "
            "sonuclari tezde kullanilamaz."
        )

    solutions = payload.get("solutions", [])
    labels = payload.get("objective_labels", list(OBJECTIVE_LABELS))
    if not solutions:
        raise SystemExit("Cephede cozum yok.")

    front = np.array(
        [[float(item["objectives"][label]) for label in labels] for item in solutions],
        dtype=float,
    )
    points = select_points(
        solutions=solutions,
        objective_labels=labels,
        compromise_index=topsis(front),
        extreme_indices=extreme_indices(front),
        total=count,
        training_parameters=load_training_parameters(),
    )
    return points, payload


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    points, payload = choose_points(args.points)
    print(f"Dogrulama noktasi: {len(points)}")
    for point in points:
        print(f"  #{point.index:<4}{point.reason}")

    cases = [OpenStudioCase(parameters=point.parameters) for point in points]
    by_case_id = {case.case_id: point for case, point in zip(cases, points)}

    if not args.harvest_only:
        print(f"\nKosu klasoru: {RUNS_ROOT}")
        results = run_cases(
            cases=cases,
            project_root=ROOT,
            output_root=RUNS_ROOT,
            max_workers=args.workers,
        )
        failed = [item for item in results if not item["success"]]
        print(f"{len(results)} kosu, {len(failed)} basarisiz")

    outcomes, incomplete = harvest_all(RUNS_ROOT)
    if incomplete:
        print(f"{len(incomplete)} kosu tamamlanmamis; ayni komutu tekrar calistirin.")
    if not outcomes:
        print("Hasat edilecek tamamlanmis dogrulama kosusu yok.")
        return

    rows = []
    for outcome in outcomes:
        point = by_case_id.get(outcome.case_id)
        if point is None:
            continue
        predicted_enpi = point.predicted.get(OBJECTIVE_LABELS[0], 0.0)
        actual_enpi = outcome.site_energy_gj * GJ_TO_KWH / FLOOR_AREA_M2
        predicted_comfort = point.predicted.get(OBJECTIVE_LABELS[2], 0.0)

        rows.append(
            {
                "case_id": outcome.case_id,
                "reason": point.reason,
                "predicted_enpi_kwh_m2": round(predicted_enpi, 4),
                "actual_enpi_kwh_m2": round(actual_enpi, 4),
                "deviation_percent": round(deviation(predicted_enpi, actual_enpi), 4),
                "predicted_comfort_hours": round(predicted_comfort, 2),
                "actual_comfort_hours": round(outcome.comfort_violation_hours, 2),
                "comfort_deviation_percent": round(
                    deviation(predicted_comfort, outcome.comfort_violation_hours), 4
                ),
                "actual_site_energy_gj": round(outcome.site_energy_gj, 3),
                "severe_errors": outcome.severe_errors,
            }
        )

    if not rows:
        # Hicbir kosu hasat edilemedi. Mevcut rapor korunur; aksi halde
        # gecerli bir dogrulama kaydi bos bir sonucla ezilir.
        raise SystemExit(
            "Hicbir dogrulama kosusu hasat edilemedi; mevcut rapor "
            "degistirilmedi. Kosu gunluklerini inceleyin: "
            "data/validation/runs/*/openstudio_stderr.log"
        )

    summary = summarise(rows, args.tolerance)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "evaluator": payload.get("evaluator", "unknown"),
        "usable_in_thesis": payload.get("usable_in_thesis", False),
        "summary": summary,
        "points": rows,
    }
    (OUTPUT / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUTPUT / "validation_table.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\n=== DOGRULAMA TABLOSU ===")
    print(
        f"  {'case_id':<20}{'vekil':>10}{'gercek':>10}{'sapma':>9}   gerekce"
    )
    for row in sorted(rows, key=lambda item: abs(item["deviation_percent"]), reverse=True):
        print(
            f"  {row['case_id']:<20}{row['predicted_enpi_kwh_m2']:>10.2f}"
            f"{row['actual_enpi_kwh_m2']:>10.2f}{row['deviation_percent']:>8.2f}%"
            f"   {row['reason']}"
        )

    print(
        f"\n  en buyuk mutlak sapma : %{summary['max_absolute_deviation_percent']:.2f}"
        f"\n  ortalama mutlak sapma : %{summary['mean_absolute_deviation_percent']:.2f}"
        f"\n  tolerans              : %{args.tolerance:.1f}"
    )
    print(f"\nFaz 7 kapisi: {'GECILDI' if summary['within_tolerance'] else 'GECILMEDI'}")
    if not summary["within_tolerance"]:
        print(
            "  Sapan noktalari egitim kumesine ekleyip Faz 4'u tekrarlayin "
            "(adaptif ornekleme)."
        )
    print(f"\nRapor: {OUTPUT / 'validation_report.json'}")


if __name__ == "__main__":
    main()
