"""Faz 3 sonuc hasadi.

Her kosu klasorunden vekil modelin ihtiyac duydugu hedefleri cikarir ve tek bir
tabloya yazar. engine/sql_results.py eski arsiv gorunumune hizmet eder ve EPS
kalinligina gore anahtarlanmistir; bu modul senaryo kimligine gore calisir.

Sonuclar HTML raporundan degil dogrudan SQLite'tan okunur. Eski
parametric_batch.py yaklasimi (HTML satirini regex ile ayiklayip
`max(heat_nums)` almak) satirdaki en buyuk sayiyi aliyordu, toplami degil; iki
yakitli bir modelde sessizce yanlis sonuc verir.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ANNUAL_REPORT = "AnnualBuildingUtilityPerformanceSummary"

# Konfor bandi. docs/bulgular_faz1.md'deki olcumlerle uyumlu.
COMFORT_MIN_C = 20.0
COMFORT_MAX_C = 26.0

# ZoneHVAC cihazi olmayan bolgeler. Sicakliklari dis havayi izler; konfor
# hedefine dahil edilirlerse optimizasyon yanlis yone gider.
# Bkz. docs/bulgular_faz1.md, "Faz 1'den cikan iki yeni bulgu".
UNCONDITIONED_ZONES = ("TZ_ASNSR", "TZ_MECODA")


@dataclass(slots=True)
class RunOutcome:
    case_id: str
    label: str
    parameters: dict[str, float | str]
    site_energy_gj: float
    eui_mj_m2: float
    total_area_m2: float
    heating_gj: float
    cooling_gj: float
    lighting_gj: float
    equipment_gj: float
    fans_gj: float
    pumps_gj: float
    unmet_heating_hours: float
    unmet_cooling_hours: float
    ashrae55_discomfort_hours: float
    comfort_violation_hours: float
    severe_errors: int
    warnings: int
    glass_u_factor: float = 0.0
    glass_shgc: float = 0.0
    window_area_m2: float = 0.0
    end_uses_gj: dict[str, float] = field(default_factory=dict)

    def to_row(self) -> dict[str, object]:
        row: dict[str, object] = {"case_id": self.case_id, "label": self.label}
        row.update(self.parameters)
        for name in (
            "site_energy_gj",
            "eui_mj_m2",
            "heating_gj",
            "cooling_gj",
            "lighting_gj",
            "equipment_gj",
            "fans_gj",
            "pumps_gj",
            "unmet_heating_hours",
            "unmet_cooling_hours",
            "ashrae55_discomfort_hours",
            "comfort_violation_hours",
            "glass_u_factor",
            "glass_shgc",
            "severe_errors",
            "warnings",
        ):
            row[name] = getattr(self, name)
        return row


def _tabular(cursor: sqlite3.Cursor, table: str, row: str, column: str) -> float:
    cursor.execute(
        """
        SELECT Value FROM TabularDataWithStrings
        WHERE ReportName = ? AND TableName = ? AND RowName = ? AND ColumnName = ?
        LIMIT 1
        """,
        (ANNUAL_REPORT, table, row, column),
    )
    result = cursor.fetchone()
    if not result or result[0] is None:
        return 0.0
    try:
        return float(result[0])
    except ValueError:
        return 0.0


def _end_uses(cursor: sqlite3.Cursor) -> dict[str, float]:
    """Son kullanim tablosunu yakit sutunlari toplanmis halde dondurur.

    `Total End Uses` satiri disarida birakilir; aksi halde toplam iki kez sayilir.
    """
    cursor.execute(
        """
        SELECT RowName, ColumnName, Value FROM TabularDataWithStrings
        WHERE ReportName = ? AND TableName = 'End Uses'
        """,
        (ANNUAL_REPORT,),
    )
    totals: dict[str, float] = {}
    for row_name, column_name, value in cursor.fetchall():
        if row_name == "Total End Uses" or column_name.startswith("Water"):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number:
            totals[row_name] = totals.get(row_name, 0.0) + number
    return totals


def _envelope(cursor: sqlite3.Cursor) -> dict[str, float]:
    """Cam U, SHGC ve alan degerleri.

    EnergyPlus bunlari her kosuda raporlar; boylece TS 825 kisit kontrolu
    varsayima degil kosunun kendi ciktisina dayanir.
    """
    cursor.execute(
        """
        SELECT ColumnName, Value FROM TabularDataWithStrings
        WHERE ReportName = 'EnvelopeSummary'
          AND TableName = 'Exterior Fenestration'
          AND RowName = 'Total or Average'
        """
    )
    values: dict[str, float] = {}
    for column, raw in cursor.fetchall():
        try:
            values[column] = float(raw)
        except (TypeError, ValueError):
            continue
    return {
        "glass_u_factor": values.get("Glass U-Factor", 0.0),
        "glass_shgc": values.get("Glass SHGC", 0.0),
        "window_area_m2": values.get("Area of Multiplied Openings", 0.0),
    }


def _comfort_hours(run_dir: Path) -> float:
    """Iklimlendirilen bolgelerde konfor bandi disinda gecen saat sayisi.

    Bolge basina degil, bolge-saat olarak sayilir; bir saatte iki bolge ihlal
    ediyorsa iki sayilir.
    """
    candidates = list(run_dir.rglob("*Hourly.csv"))
    if not candidates:
        return 0.0
    path = max(candidates, key=lambda item: item.stat().st_size)
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            return 0.0
        columns = [
            index
            for index, name in enumerate(header)
            if "Temperature" in name
            and name.split(":")[0].strip().upper() not in UNCONDITIONED_ZONES
        ]
        if not columns:
            return 0.0
        violations = 0
        for row in reader:
            for index in columns:
                try:
                    value = float(row[index])
                except (IndexError, ValueError):
                    continue
                if value < COMFORT_MIN_C or value > COMFORT_MAX_C:
                    violations += 1
    return float(violations)


def _error_counts(run_dir: Path) -> tuple[int, int]:
    error_file = run_dir / "eplusout.err"
    if not error_file.is_file():
        return 0, 0
    text = error_file.read_text(encoding="utf-8", errors="ignore")
    severe = text.count("** Severe")
    warnings = text.count("** Warning")
    return severe, warnings


def is_complete(run_dir: Path) -> bool:
    """Kosunun gercekten tamamlandigini dogrular.

    Yarida kesilen bir kosu da eplusout.sql birakir; tablolar bos oldugu icin
    tum metrikler 0.0 okunur ve sonuc tablosuna sessizce sahte bir satir girer.
    EnergyPlus'in kendi bitis kaydi tek guvenilir olcuttur.
    """
    end_file = run_dir / "eplusout.end"
    if not end_file.is_file():
        return False
    text = end_file.read_text(encoding="utf-8", errors="ignore")
    return "Completed Successfully" in text


def harvest_run(case_dir: Path) -> RunOutcome | None:
    """Tek bir kosu klasorunu okur. Kosu tamamlanmamissa None doner."""
    run_dir = case_dir / "run"
    sql_path = run_dir / "eplusout.sql"
    case_path = case_dir / "case.json"
    if not sql_path.is_file() or not case_path.is_file():
        return None
    if not is_complete(run_dir):
        return None

    try:
        case_payload = json.loads(case_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    connection = sqlite3.connect(sql_path)
    try:
        cursor = connection.cursor()
        # Bozuk veya eksik bir SQL dosyasi tum hasadi dusurmemeli; o kosu
        # tamamlanmamis sayilir ve tekrar calistirilir.
        end_uses = _end_uses(cursor)
        envelope = _envelope(cursor)
        severe, warnings = _error_counts(run_dir)
        return RunOutcome(
            case_id=case_payload.get("case_id", case_dir.name),
            label=case_payload.get("label", ""),
            parameters=case_payload.get("parameters", {}),
            site_energy_gj=_tabular(
                cursor, "Site and Source Energy", "Total Site Energy", "Total Energy"
            ),
            eui_mj_m2=_tabular(
                cursor,
                "Site and Source Energy",
                "Total Site Energy",
                "Energy Per Total Building Area",
            ),
            total_area_m2=_tabular(cursor, "Building Area", "Total Building Area", "Area"),
            heating_gj=end_uses.get("Heating", 0.0),
            cooling_gj=end_uses.get("Cooling", 0.0),
            lighting_gj=end_uses.get("Interior Lighting", 0.0),
            equipment_gj=end_uses.get("Interior Equipment", 0.0),
            fans_gj=end_uses.get("Fans", 0.0),
            pumps_gj=end_uses.get("Pumps", 0.0),
            unmet_heating_hours=_tabular(
                cursor,
                "Comfort and Setpoint Not Met Summary",
                "Time Setpoint Not Met During Occupied Heating",
                "Facility",
            ),
            unmet_cooling_hours=_tabular(
                cursor,
                "Comfort and Setpoint Not Met Summary",
                "Time Setpoint Not Met During Occupied Cooling",
                "Facility",
            ),
            ashrae55_discomfort_hours=_tabular(
                cursor,
                "Comfort and Setpoint Not Met Summary",
                "Time Not Comfortable Based on Simple ASHRAE 55-2004",
                "Facility",
            ),
            comfort_violation_hours=_comfort_hours(run_dir),
            severe_errors=severe,
            warnings=warnings,
            glass_u_factor=envelope["glass_u_factor"],
            glass_shgc=envelope["glass_shgc"],
            window_area_m2=envelope["window_area_m2"],
            end_uses_gj=end_uses,
        )
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def harvest_all(output_root: Path) -> tuple[list[RunOutcome], list[str]]:
    """Tamamlanmis kosulari ve eksik kalanlarin kimliklerini dondurur."""
    outcomes: list[RunOutcome] = []
    incomplete: list[str] = []
    for case_dir in sorted(output_root.glob("case_*")):
        outcome = harvest_run(case_dir)
        if outcome is not None:
            outcomes.append(outcome)
        elif (case_dir / "case.json").is_file():
            incomplete.append(case_dir.name)
    return outcomes, incomplete


def write_table(outcomes: Iterable[RunOutcome], path: Path) -> Path:
    rows = [outcome.to_row() for outcome in outcomes]
    if not rows:
        raise ValueError("Yazilacak sonuc yok.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def uniqueness_report(outcomes: list[RunOutcome]) -> dict[str, object]:
    """Faz 3.7 saglik kontrolu.

    Deponun 5/10/15 cm arsiv kosulari birebir ayni sonucu veriyordu, cunku eski
    kod yeni konstruksiyonu yuzeylere hic baglamamisti. Ayni hatanin
    tekrarlanmadigini acikca kanitlar.
    """
    signatures: dict[tuple[float, ...], list[str]] = {}
    for outcome in outcomes:
        key = (
            round(outcome.site_energy_gj, 4),
            round(outcome.heating_gj, 4),
            round(outcome.cooling_gj, 4),
            round(outcome.lighting_gj, 4),
            round(outcome.equipment_gj, 4),
        )
        signatures.setdefault(key, []).append(outcome.case_id)

    duplicates = {
        str(key): ids for key, ids in signatures.items() if len(ids) > 1
    }
    energies = [outcome.site_energy_gj for outcome in outcomes]
    return {
        "run_count": len(outcomes),
        "unique_result_count": len(signatures),
        "duplicate_groups": duplicates,
        "all_unique": not duplicates,
        "site_energy_min_gj": min(energies) if energies else 0.0,
        "site_energy_max_gj": max(energies) if energies else 0.0,
        "site_energy_mean_gj": statistics.mean(energies) if energies else 0.0,
        "runs_with_severe_errors": [
            outcome.case_id for outcome in outcomes if outcome.severe_errors
        ],
    }
