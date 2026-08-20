from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


ANNUAL_REPORT = "AnnualBuildingUtilityPerformanceSummary"
VERIFY_REPORT = "InputVerificationandResultsSummary"


@dataclass(slots=True)
class SimulationIssue:
    severity: str
    message: str
    occurrences: int = 1


@dataclass(slots=True)
class ArchivedScenario:
    thickness_cm: int
    sql_path: Path
    run_status: str
    site_energy_gj: float
    source_energy_gj: float
    eui_mj_m2: float
    total_area_m2: float
    conditioned_area_m2: float
    unmet_heating_hours: float
    unmet_cooling_hours: float
    discomfort_hours: float
    end_uses_gj: dict[str, float] = field(default_factory=dict)
    fuels_gj: dict[str, float] = field(default_factory=dict)
    monthly_gj: dict[str, list[float]] = field(default_factory=dict)
    general: dict[str, str] = field(default_factory=dict)
    window_wall_ratio: dict[str, float] = field(default_factory=dict)
    zones: list[dict[str, Any]] = field(default_factory=list)
    issues: list[SimulationIssue] = field(default_factory=list)

    @property
    def warnings(self) -> int:
        return sum(issue.occurrences for issue in self.issues if issue.severity == "Uyarı")

    @property
    def severe_errors(self) -> int:
        return sum(issue.occurrences for issue in self.issues if issue.severity == "Ciddi")

    def comparable_signature(self) -> tuple[Any, ...]:
        return (
            round(self.site_energy_gj, 6),
            round(self.source_energy_gj, 6),
            round(self.eui_mj_m2, 6),
            tuple(sorted((key, round(value, 6)) for key, value in self.end_uses_gj.items())),
            tuple(
                (key, tuple(round(value, 6) for value in values))
                for key, values in sorted(self.monthly_gj.items())
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sql_path"] = str(self.sql_path)
        payload["warnings"] = self.warnings
        payload["severe_errors"] = self.severe_errors
        return payload


class ResultsRepository:
    """EnergyPlus SQLite sonuçlarını tek ve doğrulanabilir bir veri modeline çevirir."""

    def __init__(self, archived_root: Path) -> None:
        self.archived_root = archived_root
        self.scenarios: dict[int, ArchivedScenario] = {}

    def load(self, thicknesses: Iterable[int] = (5, 10, 15)) -> "ResultsRepository":
        self.scenarios = {
            int(thickness): self._load_scenario(int(thickness))
            for thickness in thicknesses
        }
        return self

    def _load_scenario(self, thickness_cm: int) -> ArchivedScenario:
        run_dir = self.archived_root / f"eps_{thickness_cm}cm"
        sql_path = run_dir / "eplusout.sql"
        if not sql_path.exists():
            raise FileNotFoundError(f"EnergyPlus SQL sonucu bulunamadı: {sql_path}")

        with sqlite3.connect(sql_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            scenario = ArchivedScenario(
                thickness_cm=thickness_cm,
                sql_path=sql_path,
                run_status=_run_status(run_dir),
                site_energy_gj=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Site and Source Energy",
                    "Total Site Energy",
                    "Total Energy",
                ),
                source_energy_gj=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Site and Source Energy",
                    "Total Source Energy",
                    "Total Energy",
                ),
                eui_mj_m2=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Site and Source Energy",
                    "Total Site Energy",
                    "Energy Per Total Building Area",
                ),
                total_area_m2=_tabular_float(
                    cursor, ANNUAL_REPORT, "Building Area", "Total Building Area", "Area"
                ),
                conditioned_area_m2=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Building Area",
                    "Net Conditioned Building Area",
                    "Area",
                ),
                unmet_heating_hours=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Comfort and Setpoint Not Met Summary",
                    "Time Setpoint Not Met During Occupied Heating",
                    "Facility",
                ),
                unmet_cooling_hours=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Comfort and Setpoint Not Met Summary",
                    "Time Setpoint Not Met During Occupied Cooling",
                    "Facility",
                ),
                discomfort_hours=_tabular_float(
                    cursor,
                    ANNUAL_REPORT,
                    "Comfort and Setpoint Not Met Summary",
                    "Time Not Comfortable Based on Simple ASHRAE 55-2004",
                    "Facility",
                ),
                end_uses_gj=_end_uses(cursor),
                fuels_gj=_fuels(cursor),
                monthly_gj=_monthly_energy(cursor),
                general=_general(cursor),
                window_wall_ratio=_wwr(cursor),
                zones=_zones(cursor),
                issues=_issues(cursor),
            )
        return scenario

    @property
    def archived_runs_are_identical(self) -> bool:
        signatures = {scenario.comparable_signature() for scenario in self.scenarios.values()}
        return len(signatures) == 1 and len(self.scenarios) > 1

    def summary(self) -> dict[str, Any]:
        return {
            "archived_runs_are_identical": self.archived_runs_are_identical,
            "scenarios": {
                str(key): value.to_dict() for key, value in self.scenarios.items()
            },
        }

    def write_summary(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.summary(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return output_path

    def hashes(self) -> dict[int, str]:
        return {
            thickness: hashlib.sha256(scenario.sql_path.read_bytes()).hexdigest()
            for thickness, scenario in self.scenarios.items()
        }


def _tabular_float(
    cursor: sqlite3.Cursor,
    report: str,
    table: str,
    row: str,
    column: str,
) -> float:
    found = cursor.execute(
        """
        SELECT Value
        FROM TabularDataWithStrings
        WHERE ReportName=? AND TableName=? AND RowName=? AND ColumnName=?
        LIMIT 1
        """,
        (report, table, row, column),
    ).fetchone()
    if not found or found[0] in (None, ""):
        return 0.0
    try:
        return float(str(found[0]).strip())
    except ValueError:
        return 0.0


def _end_uses(cursor: sqlite3.Cursor) -> dict[str, float]:
    rows = cursor.execute(
        """
        SELECT RowName, SUM(CAST(Value AS REAL)) AS total
        FROM TabularDataWithStrings
        WHERE ReportName=? AND TableName='End Uses' AND Units='GJ'
          AND RowName NOT IN ('', 'Total End Uses')
        GROUP BY RowName
        HAVING ABS(total) > 0.0001
        ORDER BY total DESC
        """,
        (ANNUAL_REPORT,),
    )
    return {str(row[0]): round(float(row[1]), 4) for row in rows}


def _fuels(cursor: sqlite3.Cursor) -> dict[str, float]:
    rows = cursor.execute(
        """
        SELECT ColumnName, CAST(Value AS REAL)
        FROM TabularDataWithStrings
        WHERE ReportName=? AND TableName='End Uses'
          AND RowName='Total End Uses' AND Units='GJ'
          AND ABS(CAST(Value AS REAL)) > 0.0001
        ORDER BY CAST(Value AS REAL) DESC
        """,
        (ANNUAL_REPORT,),
    )
    return {str(row[0]): round(float(row[1]), 4) for row in rows}


def _monthly_energy(cursor: sqlite3.Cursor) -> dict[str, list[float]]:
    result = {
        "Electricity:Facility": [0.0] * 12,
        "NaturalGas:Facility": [0.0] * 12,
    }
    rows = cursor.execute(
        """
        SELECT t.Month, d.Name, SUM(r.Value) / 1000000000.0 AS gj
        FROM ReportData AS r
        JOIN ReportDataDictionary AS d
          ON d.ReportDataDictionaryIndex=r.ReportDataDictionaryIndex
        JOIN Time AS t ON t.TimeIndex=r.TimeIndex
        JOIN EnvironmentPeriods AS e
          ON e.EnvironmentPeriodIndex=t.EnvironmentPeriodIndex
        WHERE d.ReportingFrequency='Daily'
          AND d.Name IN ('Electricity:Facility', 'NaturalGas:Facility')
          AND t.WarmupFlag=0 AND e.EnvironmentType=3
        GROUP BY t.Month, d.Name
        ORDER BY t.Month, d.Name
        """
    )
    for month, name, value in rows:
        if month and name in result:
            result[str(name)][int(month) - 1] = round(float(value or 0.0), 4)
    return result


def _general(cursor: sqlite3.Cursor) -> dict[str, str]:
    rows = cursor.execute(
        """
        SELECT RowName, TRIM(Value), Units
        FROM TabularDataWithStrings
        WHERE ReportName=? AND TableName='General'
        ORDER BY RowName
        """,
        (VERIFY_REPORT,),
    )
    return {
        str(row_name): f"{value} {units}".strip()
        for row_name, value, units in rows
    }


def _wwr(cursor: sqlite3.Cursor) -> dict[str, float]:
    rows = cursor.execute(
        """
        SELECT ColumnName, CAST(Value AS REAL)
        FROM TabularDataWithStrings
        WHERE ReportName=? AND TableName='Window-Wall Ratio'
          AND RowName='Above Ground Window-Wall Ratio'
        """,
        (VERIFY_REPORT,),
    )
    return {str(row[0]): round(float(row[1]), 2) for row in rows}


def _zones(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    rows = cursor.execute(
        """
        SELECT RowName, ColumnName, TRIM(Value), Units
        FROM TabularDataWithStrings
        WHERE ReportName=? AND TableName='Zone Summary'
          AND RowName NOT IN ('Total', 'Conditioned Total', 'Unconditioned Total',
                              'Not Part of Total')
        ORDER BY RowName, ColumnName
        """,
        (VERIFY_REPORT,),
    )
    grouped: dict[str, dict[str, Any]] = {}
    column_map = {
        "Area": "area_m2",
        "Volume": "volume_m3",
        "Conditioned (Y/N)": "conditioned",
        "Window Glass Area": "window_area_m2",
        "Lighting": "lighting_w_m2",
        "People": "area_per_person_m2",
        "Plug and Process": "equipment_w_m2",
    }
    for row_name, column_name, raw_value, _units in rows:
        if column_name not in column_map:
            continue
        value: Any = raw_value
        try:
            value = round(float(raw_value), 2)
        except (TypeError, ValueError):
            pass
        grouped.setdefault(str(row_name), {"zone": str(row_name)})[
            column_map[str(column_name)]
        ] = value
    return list(grouped.values())


def _issues(cursor: sqlite3.Cursor) -> list[SimulationIssue]:
    severity_names = {-1: "Bilgi", 0: "Uyarı", 1: "Ciddi", 2: "Ölümcül"}
    rows = cursor.execute(
        """
        SELECT ErrorType, ErrorMessage,
               CASE WHEN Count > 0 THEN Count ELSE 1 END AS occurrences
        FROM Errors
        WHERE ErrorType >= 0
        ORDER BY ErrorType DESC, ErrorIndex
        """
    )
    return [
        SimulationIssue(
            severity=severity_names.get(int(row[0]), "Bilinmiyor"),
            message=" ".join(str(row[1]).split()),
            occurrences=int(row[2]),
        )
        for row in rows
    ]


def _run_status(run_dir: Path) -> str:
    osw_path = run_dir / "out.osw"
    if osw_path.exists():
        try:
            status = json.loads(osw_path.read_text(encoding="utf-8-sig")).get(
                "completed_status"
            )
            if status:
                return str(status)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    end_path = run_dir / "eplusout.end"
    if end_path.exists() and "Completed Successfully" in end_path.read_text(
        encoding="utf-8", errors="ignore"
    ):
        return "Success"
    return "Unknown"
