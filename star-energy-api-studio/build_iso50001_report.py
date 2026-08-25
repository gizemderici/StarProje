"""Faz 5: ISO 50001 kapsam ve gosterge raporu.

Taban kosusundan SEU, enerji taban cizgisi ve EnPI degerlerini uretir. Parametrik
sonuc tablosu varsa her senaryo icin taban cizgisine gore iyilesme de hesaplanir.

Kullanim:
    python build_iso50001_report.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from engine.results import _end_uses, _tabular
from iso50001 import EnergyBaseline, degree_days, indicators, scenario_report, summary

ROOT = Path(__file__).resolve().parent
BASELINE_SQL = ROOT / "data/baseline_v1/eplusout.sql"
WEATHER = ROOT / "data/input/weather_tmyx.epw"
RESULTS_CSV = ROOT / "data/parametric/results.csv"
OUTPUT = ROOT / "data/iso50001"

# Modelden okunan doluluk. OS:People nesneleri 0,05383 kisi/m2 kullaniyor.
# Kaynak: data/input/gsf_fng_6mayis_onarilmis.osm
OCCUPANT_COUNT = 201.74


def read_baseline(sql_path: Path) -> tuple[float, float, dict[str, float]]:
    connection = sqlite3.connect(sql_path)
    try:
        cursor = connection.cursor()
        site = _tabular(
            cursor, "Site and Source Energy", "Total Site Energy", "Total Energy"
        )
        area = _tabular(cursor, "Building Area", "Total Building Area", "Area")
        return site, area, _end_uses(cursor)
    finally:
        connection.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not BASELINE_SQL.is_file():
        raise SystemExit(f"Taban kosusu bulunamadi: {BASELINE_SQL}")

    site_energy, area, end_uses = read_baseline(BASELINE_SQL)
    climate = degree_days(WEATHER)

    baseline = EnergyBaseline(
        source="data/baseline_v1 (Faz 1 onarimi sonrasi taban kosusu)",
        site_energy_gj=site_energy,
        total_area_m2=area,
        occupant_count=OCCUPANT_COUNT,
        hdd=climate.hdd,
        cdd=climate.cdd,
        measured=False,
    )
    seu = summary(end_uses)

    payload: dict[str, object] = {
        "energy_baseline": baseline.to_dict(),
        "significant_energy_uses": seu,
        "climate": climate.to_dict(),
        "baseline_indicators": [item.to_dict() for item in indicators(site_energy, baseline)],
    }

    # Parametrik sonuclar hazirsa her senaryoyu taban cizgisine gore degerlendir.
    if RESULTS_CSV.is_file():
        import csv

        scenarios = []
        with RESULTS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    energy = float(row["site_energy_gj"])
                except (KeyError, ValueError):
                    continue
                # Sifir enerji gecerli bir sonuc degildir; yarida kesilmis bir
                # kosunun tabloya sizmasi halinde %100 "tasarruf" gorunurdu.
                if energy <= 0:
                    continue
                scenarios.append(
                    {
                        "case_id": row.get("case_id", ""),
                        "label": row.get("label", ""),
                        **scenario_report(energy, baseline),
                    }
                )
        scenarios.sort(key=lambda item: item["improvement"]["percent"], reverse=True)
        payload["scenarios"] = scenarios
        payload["scenario_count"] = len(scenarios)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "iso50001_report.json"
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=== ENERJI TABAN CIZGISI (EnB) ===")
    print(f"  kaynak        : {baseline.source}")
    print(f"  olculmus mu   : HAYIR (simulasyon tabanli)")
    print(f"  saha enerjisi : {baseline.site_energy_gj:.2f} GJ/yil")
    print(f"  alan          : {baseline.total_area_m2:.2f} m2")
    print(f"  doluluk       : {baseline.occupant_count:.1f} kisi")
    print()
    print("=== IKLIM (Mugla TMYx 2009-2023) ===")
    print(f"  HDD{climate.heating_base_c:g} : {climate.hdd:8.1f}")
    print(f"  CDD{climate.cooling_base_c:g} : {climate.cdd:8.1f}")
    print()
    print(f"=== ONEMLI ENERJI KULLANIMI (esik %{seu['threshold_percent']:g}) ===")
    print(f"  {'son kullanim':<18}{'GJ/yil':>10}{'pay':>8}{'kumulatif':>11}  SEU")
    for use in seu["uses"]:
        mark = "EVET" if use["significant"] else ""
        print(
            f"  {use['label']:<18}{use['energy_gj']:>10.2f}"
            f"{use['share_percent']:>7.1f}%{use['cumulative_percent']:>10.1f}%  {mark}"
        )
    print(f"\n  SEU kapsami: {', '.join(seu['significant_uses'])}")
    print(f"  kapsanan pay: %{seu['significant_share_percent']:.1f}")
    print()
    print("=== TABAN CIZGISI GOSTERGELERI (EnPI) ===")
    for item in indicators(site_energy, baseline):
        print(f"  {item.label:<38}{item.value:>10.3f} {item.unit}")

    if "scenarios" in payload:
        print(f"\n=== SENARYOLAR ({payload['scenario_count']}) ===")
        for item in payload["scenarios"][:5]:
            print(
                f"  {item['improvement']['percent']:>7.2f}%  "
                f"{item['site_energy_gj']:>9.2f} GJ  {item['label'][:60]}"
            )

    print(f"\nRapor: {report_path}")


if __name__ == "__main__":
    main()
