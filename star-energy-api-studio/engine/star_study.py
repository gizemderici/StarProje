from __future__ import annotations

import csv
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class StarScenario:
    scenario: str
    thickness_cm: float | None
    conductivity_w_mk: float | None
    electricity_gj: float
    heating_gj: float
    cooling_gj: float
    exit_code: int
    duplicate: bool = False

    @property
    def hvac_gj(self) -> float:
        return round(self.heating_gj + self.cooling_gj, 3)

    @property
    def site_energy_gj(self) -> float:
        return round(self.electricity_gj + self.heating_gj + self.cooling_gj, 3)

    @property
    def insulation_r_m2k_w(self) -> float | None:
        if self.thickness_cm is None or not self.conductivity_w_mk:
            return None
        return round((self.thickness_cm / 100.0) / self.conductivity_w_mk, 4)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            hvac_gj=self.hvac_gj,
            site_energy_gj=self.site_energy_gj,
            insulation_r_m2k_w=self.insulation_r_m2k_w,
        )
        return payload


class StarStudy:
    """Star.zip içindeki gerçek EnergyPlus parametrik çalışmasının okuyucusu."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.scenarios: list[StarScenario] = []

    def load(self) -> "StarStudy":
        summary = self.root / "summary.csv"
        if not summary.exists():
            raise FileNotFoundError(f"Star parametrik özeti bulunamadı: {summary}")
        seen: set[tuple[float | None, float | None]] = set()
        scenarios: list[StarScenario] = []
        with summary.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                thickness = _optional_float(row.get("thickness_m"))
                if thickness is not None:
                    thickness *= 100.0
                conductivity = _optional_float(row.get("conductivity_w_mk"))
                key = (thickness, conductivity)
                duplicate = key in seen and key != (None, None)
                seen.add(key)
                scenarios.append(
                    StarScenario(
                        scenario=str(row.get("scenario", "")),
                        thickness_cm=round(thickness, 3) if thickness is not None else None,
                        conductivity_w_mk=conductivity,
                        electricity_gj=float(row.get("total_electricity_gj") or 0.0),
                        heating_gj=float(row.get("heating_gj") or 0.0),
                        cooling_gj=float(row.get("cooling_gj") or 0.0),
                        exit_code=int(row.get("exit_code") or 0),
                        duplicate=duplicate,
                    )
                )
        self.scenarios = scenarios
        return self

    @property
    def baseline(self) -> StarScenario:
        return next(item for item in self.scenarios if item.thickness_cm is None)

    @property
    def unique_scenarios(self) -> list[StarScenario]:
        return [item for item in self.scenarios if not item.duplicate]

    @property
    def tested_scenarios(self) -> list[StarScenario]:
        return [item for item in self.unique_scenarios if item.thickness_cm is not None]

    @property
    def best_tested(self) -> StarScenario:
        return min(self.tested_scenarios, key=lambda item: item.hvac_gj)

    @property
    def duplicate_count(self) -> int:
        return sum(item.duplicate for item in self.scenarios)

    @property
    def baseline_beats_all_tested(self) -> bool:
        return self.baseline.hvac_gj < self.best_tested.hvac_gj

    def validate_sql(self) -> dict[str, dict[str, float]]:
        paths = {
            "baseline": self.root / "verified_runs/baseline/eplusout.sql",
            "best_tested": self.root / "verified_runs/best_tested/eplusout.sql",
        }
        return {name: _sql_metrics(path) for name, path in paths.items()}


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _sql_metrics(path: Path) -> dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(f"Doğrulama SQL dosyası bulunamadı: {path}")
    with sqlite3.connect(path) as connection:
        cursor = connection.cursor()

        def tabular(row_name: str, column_name: str, table: str = "End Uses") -> float:
            row = cursor.execute(
                """
                SELECT Value FROM TabularDataWithStrings
                WHERE ReportName='AnnualBuildingUtilityPerformanceSummary'
                  AND TableName=? AND RowName=? AND ColumnName=? LIMIT 1
                """,
                (table, row_name, column_name),
            ).fetchone()
            return float(str(row[0]).strip()) if row and str(row[0]).strip() else 0.0

        return {
            "heating_gj": tabular("Heating", "District Heating Water"),
            "cooling_gj": tabular("Cooling", "District Cooling"),
            "electricity_gj": tabular("Total End Uses", "Electricity"),
            "site_energy_gj": tabular(
                "Total Site Energy", "Total Energy", "Site and Source Energy"
            ),
        }
