from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path
from threading import Lock
from typing import Iterable

from engine.openstudio_runner import (
    OpenStudioCase,
    build_workflow,
    find_openstudio,
    run_cases,
)
from model_store import ModelRecord


class OpenStudioUnavailable(RuntimeError):
    pass


class OpenStudioService:
    """Use the installed OpenStudio SDK/CLI behind a narrow service boundary."""

    def __init__(
        self,
        project_root: Path,
        openstudio_exe: Path | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.openstudio_exe = find_openstudio(openstudio_exe)
        self.worker_path = self.project_root / "integrations/OpenStudio/model_api_worker.py"
        self.measures_root = self.project_root / "integrations/OpenStudio/Measures"
        self.output_root = self.project_root / "data/generated/openstudio_runs"
        self.cache_root = cache_root or self.project_root / "data/generated/model_api_cache"
        self._lock = Lock()
        self._version: str | None = None
        self.energyplus_exe = (
            self.openstudio_exe.parent.parent / "EnergyPlus/energyplus.exe"
            if self.openstudio_exe
            else None
        )

    @staticmethod
    def _subprocess_options() -> dict[str, object]:
        options: dict[str, object] = {}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        return options

    def _require_executable(self) -> Path:
        if self.openstudio_exe is None:
            raise OpenStudioUnavailable(
                "OpenStudio CLI bulunamadı. OPENSTUDIO_EXE ortam değişkenini ayarlayın."
            )
        return self.openstudio_exe

    def version(self) -> str | None:
        if self.openstudio_exe is None:
            return None
        if self._version is None:
            completed = subprocess.run(
                [str(self.openstudio_exe), "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                **self._subprocess_options(),
            )
            if completed.returncode == 0:
                self._version = completed.stdout.strip()
        return self._version

    def status(self) -> dict[str, object]:
        version = self.version()
        return {
            "installed": self.openstudio_exe is not None,
            "executable": str(self.openstudio_exe) if self.openstudio_exe else None,
            "version": version,
            "adapter": "OpenStudio CLI embedded Python API" if version else None,
            "energyplus_executable": str(self.energyplus_exe)
            if self.energyplus_exe and self.energyplus_exe.is_file()
            else None,
        }

    def inspect_model(self, record: ModelRecord, refresh: bool = False) -> dict[str, object]:
        executable = self._require_executable()
        source_stat = record.osm_path.stat()
        fingerprint = {
            "source_mtime_ns": source_stat.st_mtime_ns,
            "source_size": source_stat.st_size,
            "worker_mtime_ns": self.worker_path.stat().st_mtime_ns,
            "openstudio_version": self.version(),
        }
        cache_path = self.cache_root / f"{record.model_id}.json"

        with self._lock:
            if cache_path.is_file() and not refresh:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("cache_fingerprint") == fingerprint:
                    return self._with_public_model(cached, record)

            self.cache_root.mkdir(parents=True, exist_ok=True)
            temporary_path = cache_path.with_suffix(".tmp.json")
            command = [
                str(executable),
                "--loglevel",
                "Error",
                "execute_python_script",
                str(self.worker_path),
                "--osm",
                str(record.osm_path),
                "--output",
                str(temporary_path),
            ]
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
                **self._subprocess_options(),
            )
            if completed.returncode != 0 or not temporary_path.is_file():
                details = (completed.stderr or completed.stdout).strip()
                raise RuntimeError(f"OpenStudio model API çağrısı başarısız: {details}")
            payload = json.loads(temporary_path.read_text(encoding="utf-8"))
            payload["cache_fingerprint"] = fingerprint
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary_path.replace(cache_path)
            return self._with_public_model(payload, record)

    @staticmethod
    def _with_public_model(
        payload: dict[str, object], record: ModelRecord
    ) -> dict[str, object]:
        response = dict(payload)
        response.pop("cache_fingerprint", None)
        response["model"] = record.public_dict()
        return response

    def prepare_workflows(
        self, record: ModelRecord, cases: Iterable[OpenStudioCase]
    ) -> list[dict[str, object]]:
        if record.weather_path is None:
            raise ValueError(f"{record.model_id} için hava dosyası tanımlı değil.")
        prepared = []
        for case in cases:
            workflow_path = build_workflow(
                case=case,
                seed_file=record.osm_path,
                weather_file=record.weather_path,
                measures_root=self.measures_root,
                workflow_dir=self.output_root / record.model_id / case.case_id,
            )
            prepared.append(
                {
                    "case": case.as_dict(),
                    "status": "prepared",
                    "workflow_id": f"{record.model_id}/{case.case_id}",
                    "workflow_file": workflow_path.name,
                }
            )
        return prepared

    def run_simulations(
        self, record: ModelRecord, cases: list[OpenStudioCase]
    ) -> list[dict[str, object]]:
        """Senaryolari OSW + measure yolundan calistirir.

        Faz 2.3 oncesinde burada ikinci bir uygulama vardi: model
        execute_python_script ile ForwardTranslator'dan gecirilip energyplus.exe
        dogrudan cagriliyordu. Ayni isi yapan iki yol, her yeni measure'in iki kez
        yazilmasini gerektiriyordu. Artik tek yol var: engine.openstudio_runner.
        """
        self._require_executable()
        if record.weather_path is None:
            raise ValueError(f"{record.model_id} için hava dosyası tanımlı değil.")

        results = run_cases(
            cases=list(cases),
            project_root=self.project_root,
            output_root=self.output_root / record.model_id,
            openstudio_exe=self.openstudio_exe,
            seed_file=record.osm_path,
            weather_file=record.weather_path,
        )

        enriched: list[dict[str, object]] = []
        for item in results:
            sql_path = item.get("sql_path")
            enriched.append(
                {
                    "case": item["case"],
                    "status": "completed" if item["success"] else "failed",
                    "success": item["success"],
                    "return_code": item["return_code"],
                    "message": item["message"],
                    "sql_available": bool(sql_path),
                    "summary": self._energy_summary(Path(sql_path)) if sql_path else None,
                }
            )
        return enriched

    def list_simulation_results(self, record: ModelRecord) -> list[dict[str, object]]:
        model_root = self.output_root / record.model_id
        if not model_root.is_dir():
            return []
        results = []
        # Klasor adlari artik parametrelerden turetilen kararli kimliklerdir;
        # onceki "eps_*cm" deseni yalnizca tek degiskenli kosulari bulabiliyordu.
        for case_root in sorted(model_root.glob("case_*")):
            sql_path = case_root / "run/eplusout.sql"
            if not sql_path.is_file():
                continue
            case_path = case_root / "case.json"
            case_payload = (
                json.loads(case_path.read_text(encoding="utf-8"))
                if case_path.is_file()
                else {"case_id": case_root.name}
            )
            end_path = case_root / "run/eplusout.end"
            success = end_path.is_file() and "Completed Successfully" in end_path.read_text(
                encoding="utf-8", errors="replace"
            )
            results.append(
                {
                    "case": case_payload,
                    "status": "completed" if success else "failed",
                    "success": success,
                    "message": "Kayıtlı OpenStudio + EnergyPlus sonucu.",
                    "sql_available": True,
                    "summary": self._energy_summary(sql_path),
                }
            )
        return results

    @staticmethod
    def _energy_summary(sql_path: Path) -> dict[str, float]:
        query = """
            SELECT Value
            FROM TabularDataWithStrings
            WHERE ReportName = 'AnnualBuildingUtilityPerformanceSummary'
              AND TableName = ?
              AND RowName = ?
              AND ColumnName = ?
            LIMIT 1
        """

        def value(cursor: sqlite3.Cursor, table: str, row: str, column: str) -> float:
            cursor.execute(query, (table, row, column))
            result = cursor.fetchone()
            return round(float(result[0]), 4) if result and result[0] else 0.0

        with sqlite3.connect(sql_path) as connection:
            cursor = connection.cursor()
            return {
                "site_energy_gj": value(
                    cursor, "Site and Source Energy", "Total Site Energy", "Total Energy"
                ),
                "source_energy_gj": value(
                    cursor,
                    "Site and Source Energy",
                    "Total Source Energy",
                    "Total Energy",
                ),
                "eui_mj_m2": value(
                    cursor,
                    "Site and Source Energy",
                    "Total Site Energy",
                    "Energy Per Total Building Area",
                ),
                "total_area_m2": value(
                    cursor, "Building Area", "Total Building Area", "Area"
                ),
            }
