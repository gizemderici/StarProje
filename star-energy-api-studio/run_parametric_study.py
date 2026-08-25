"""Faz 3 toplu parametrik kosu.

Tasarim matrisini uretir, kosulari paralel calistirir ve sonuclari tek bir
tabloya hasat eder. Kesinti halinde ayni komut kaldigi yerden devam eder:
senaryo kimligi parametrelerden turetildigi icin tamamlanmis kosular atlanir.

Kullanim:
    python run_parametric_study.py --count 150 --workers 6
    python run_parametric_study.py --count 150 --harvest-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from engine.openstudio_runner import OpenStudioCase, find_openstudio, run_cases
from engine.results import harvest_all, uniqueness_report, write_table
from engine.sampling import build_design, write_design

ROOT = Path(__file__).resolve().parent
STUDY_ROOT = ROOT / "data/parametric"
RUNS_ROOT = STUDY_ROOT / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Faz 3 parametrik calisma.")
    parser.add_argument("--count", type=int, default=150, help="Ornek nokta sayisi.")
    parser.add_argument("--seed", type=int, default=20260825, help="Tasarim tohumu.")
    parser.add_argument("--workers", type=int, default=None, help="Paralel kosu sayisi.")
    parser.add_argument(
        "--harvest-only",
        action="store_true",
        help="Yeni kosu baslatma; yalnizca mevcut sonuclari topla.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Yalnizca ilk N noktayi calistir (pilot kosu icin).",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    design = build_design(count=args.count, seed=args.seed)
    if args.limit:
        design = design[: args.limit]
    design_path = write_design(design, STUDY_ROOT / "design.json", args.seed)
    print(f"Tasarim yazildi: {design_path}  ({len(design)} nokta)")

    cases = [OpenStudioCase(parameters=point.parameters) for point in design]
    unique_ids = {case.case_id for case in cases}
    if len(unique_ids) != len(cases):
        print(f"UYARI: {len(cases) - len(unique_ids)} nokta ayni parametrelere sahip.")

    if not args.harvest_only:
        executable = find_openstudio()
        if executable is None:
            raise SystemExit(
                "OpenStudio CLI bulunamadi. OPENSTUDIO_EXE ortam degiskenini ayarlayin."
            )
        print(f"OpenStudio: {executable}")
        print(f"Kosu klasoru: {RUNS_ROOT}")
        started = time.time()
        results = run_cases(
            cases=cases,
            project_root=ROOT,
            output_root=RUNS_ROOT,
            max_workers=args.workers,
        )
        elapsed = time.time() - started
        skipped = sum(1 for item in results if "atlandi" in item["message"])
        failed = [item for item in results if not item["success"]]
        print(
            f"Bitti: {len(results)} senaryo, {skipped} atlandi, "
            f"{len(failed)} basarisiz, {elapsed / 60:.1f} dakika"
        )
        for item in failed[:10]:
            print(f"  BASARISIZ {item['case']['case_id']}: {item['message']}")

    outcomes, incomplete = harvest_all(RUNS_ROOT)
    if incomplete:
        print()
        print(f"{len(incomplete)} kosu tamamlanmamis, tabloya alinmadi:")
        for case_id in incomplete[:10]:
            print(f"  {case_id}")
        print("  Ayni komutu tekrar calistirin; eksik kalanlar yeniden kosar.")
    if not outcomes:
        print("Hasat edilecek tamamlanmis sonuc bulunamadi.")
        return

    table_path = write_table(outcomes, STUDY_ROOT / "results.csv")
    report = uniqueness_report(outcomes)
    (STUDY_ROOT / "uniqueness_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nSonuc tablosu: {table_path}  ({len(outcomes)} satir)")
    print(f"  benzersiz sonuc : {report['unique_result_count']} / {report['run_count']}")
    print(f"  hepsi farkli mi : {report['all_unique']}")
    print(
        f"  saha enerjisi   : {report['site_energy_min_gj']:.2f} – "
        f"{report['site_energy_max_gj']:.2f} GJ "
        f"(ortalama {report['site_energy_mean_gj']:.2f})"
    )
    if report["runs_with_severe_errors"]:
        print(f"  SEVERE HATALI   : {report['runs_with_severe_errors']}")
    if report["duplicate_groups"]:
        print("  TEKRARLAYAN SONUC GRUPLARI:")
        for signature, ids in list(report["duplicate_groups"].items())[:5]:
            print(f"    {signature}: {ids}")


if __name__ == "__main__":
    main()
