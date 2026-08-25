from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.estimator import EstimatorAssumptions, export_results, run_parametric
from engine.openstudio_runner import OpenStudioCase, prepare_workflows, run_cases
from engine.sql_results import ResultsRepository


ROOT = Path(__file__).resolve().parent
ARCHIVED_RUNS = ROOT / "data/archived_runs"
GENERATED = ROOT / "data/generated"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EPS kalınlığı için hızlı tahmin veya gerçek OpenStudio koşusu üretir."
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "openstudio"),
        default="quick",
        help="quick: anlık kalibre tahmini, openstudio: gerçek EnergyPlus koşusu",
    )
    parser.add_argument(
        "--scenarios",
        help="Senaryo listesi iceren JSON dosyasi. Verilirse --thicknesses yok sayilir.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Paralel kosu sayisi (varsayilan: cekirdek sayisi - 1).",
    )
    parser.add_argument(
        "--thicknesses",
        nargs="+",
        type=float,
        default=[3, 5, 8, 10, 12, 15, 20, 25, 30],
        help="EPS kalınlıkları (cm)",
    )
    parser.add_argument("--conductivity", type=float, default=0.039)
    parser.add_argument("--openstudio-exe", default=None)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="OpenStudio modunda yalnızca OSW dosyalarını hazırlar.",
    )
    return parser.parse_args()


def quick_simulation(args: argparse.Namespace) -> None:
    repository = ResultsRepository(ARCHIVED_RUNS).load()
    assumptions = EstimatorAssumptions(eps_conductivity_w_mk=args.conductivity)
    points = run_parametric(args.thicknesses, repository.scenarios[5], assumptions)
    csv_path, json_path = export_results(points, GENERATED, assumptions)
    repository.write_summary(GENERATED / "arsiv_sonuclari.json")
    print("Hızlı parametrik simülasyon tamamlandı.")
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")
    for point in points:
        print(
            f"{point.thickness_cm:>5g} cm | U={point.wall_u_w_m2k:.3f} W/m²K | "
            f"enerji={point.site_energy_gj:.2f} GJ | tasarruf=%{point.savings_percent:.2f}"
        )


def _cases_from_args(args: argparse.Namespace) -> list[OpenStudioCase]:
    """Senaryo dosyasi verildiyse onu, verilmediyse EPS taramasini kullanir."""
    if args.scenarios:
        payload = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))
        items = payload["scenarios"] if isinstance(payload, dict) else payload
        return [OpenStudioCase(parameters=item) for item in items]
    return [
        OpenStudioCase(
            parameters={
                "eps_thickness_cm": value,
                "eps_conductivity_w_mk": args.conductivity,
            }
        )
        for value in args.thicknesses
    ]


def openstudio_simulation(args: argparse.Namespace) -> None:
    cases = _cases_from_args(args)
    output_root = GENERATED / "openstudio_runs"
    if args.prepare_only:
        workflows = prepare_workflows(cases, ROOT, output_root)
        manifest = {
            "mode": "openstudio_prepare_only",
            "cases": [case.as_dict() for case in cases],
            "workflows": [str(path) for path in workflows],
        }
        (output_root / "prepared_workflows.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("OpenStudio OSW dosyaları hazırlandı:")
        for workflow in workflows:
            print(workflow)
        return
    results = run_cases(
        cases=cases,
        project_root=ROOT,
        output_root=output_root,
        openstudio_exe=Path(args.openstudio_exe) if args.openstudio_exe else None,
        max_workers=args.workers,
    )
    for result in results:
        state = "BAŞARILI" if result["success"] else "HATALI"
        print(f"{state}: {result['case']['label']} -> {result['run_dir']}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if args.mode == "quick":
        quick_simulation(args)
    else:
        openstudio_simulation(args)


if __name__ == "__main__":
    main()
