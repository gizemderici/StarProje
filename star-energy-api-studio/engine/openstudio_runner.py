from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class OpenStudioCase:
    thickness_cm: float
    conductivity_w_mk: float = 0.039
    density_kg_m3: float = 16.0
    specific_heat_j_kgk: float = 1250.0
    target_construction: str = "duvr_std_eps"

    @property
    def slug(self) -> str:
        value = f"{self.thickness_cm:g}".replace(".", "_")
        return f"eps_{value}cm"


@dataclass(slots=True)
class RunResult:
    case: OpenStudioCase
    success: bool
    run_dir: Path
    workflow_path: Path
    sql_path: Path | None
    return_code: int
    message: str


def find_openstudio(explicit_path: str | Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    if os.getenv("OPENSTUDIO_EXE"):
        candidates.append(Path(os.environ["OPENSTUDIO_EXE"]).expanduser())
    resolved = shutil.which("openstudio")
    if resolved:
        candidates.append(Path(resolved))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    if program_files.exists():
        candidates.extend(
            sorted(
                program_files.glob("OpenStudio-*/bin/openstudio.exe"),
                reverse=True,
            )
        )
        candidates.append(program_files / "OpenStudio/bin/openstudio.exe")
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def build_workflow(
    case: OpenStudioCase,
    seed_file: Path,
    weather_file: Path,
    measures_root: Path,
    workflow_dir: Path,
) -> Path:
    for required in (seed_file, weather_file, measures_root / "SetEpsThickness"):
        if not required.exists():
            raise FileNotFoundError(f"Gerekli OpenStudio girdisi bulunamadı: {required}")
    workflow_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = workflow_dir / "workflow.osw"
    payload = {
        "seed_file": str(seed_file.resolve()),
        "weather_file": str(weather_file.resolve()),
        "measure_paths": [str(measures_root.resolve())],
        "run_directory": str((workflow_dir / "run").resolve()),
        "steps": [
            {
                "measure_dir_name": "SetEpsThickness",
                "arguments": {
                    "target_construction": case.target_construction,
                    "eps_thickness_cm": case.thickness_cm,
                    "conductivity_w_mk": case.conductivity_w_mk,
                    "density_kg_m3": case.density_kg_m3,
                    "specific_heat_j_kgk": case.specific_heat_j_kgk,
                },
            }
        ],
    }
    workflow_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return workflow_path


def prepare_workflows(
    cases: Iterable[OpenStudioCase],
    project_root: Path,
    output_root: Path,
) -> list[Path]:
    workflows = []
    for case in cases:
        workflows.append(
            build_workflow(
                case=case,
                seed_file=project_root / "data/input/bina_orijinal.osm",
                weather_file=project_root / "data/input/weather.epw",
                measures_root=project_root / "integrations/OpenStudio/Measures",
                workflow_dir=output_root / case.slug,
            )
        )
    return workflows


def run_case(openstudio_exe: Path, workflow_path: Path, case: OpenStudioCase) -> RunResult:
    if not openstudio_exe.is_file():
        raise FileNotFoundError(f"OpenStudio CLI bulunamadı: {openstudio_exe}")
    run_root = workflow_path.parent
    completed = subprocess.run(
        [str(openstudio_exe), "run", "-w", str(workflow_path)],
        cwd=run_root,
        capture_output=True,
        text=True,
        check=False,
    )
    (run_root / "openstudio_stdout.log").write_text(
        completed.stdout, encoding="utf-8", errors="replace"
    )
    (run_root / "openstudio_stderr.log").write_text(
        completed.stderr, encoding="utf-8", errors="replace"
    )
    sql_candidates = [
        run_root / "run/eplusout.sql",
        run_root / "eplusout.sql",
    ]
    sql_path = next((path for path in sql_candidates if path.exists()), None)
    success = completed.returncode == 0 and sql_path is not None
    return RunResult(
        case=case,
        success=success,
        run_dir=run_root,
        workflow_path=workflow_path,
        sql_path=sql_path,
        return_code=completed.returncode,
        message=(
            "OpenStudio koşusu tamamlandı."
            if success
            else "OpenStudio koşusu başarısız; log dosyalarını inceleyin."
        ),
    )


def run_cases(
    cases: list[OpenStudioCase],
    project_root: Path,
    output_root: Path,
    openstudio_exe: Path | None = None,
) -> list[RunResult]:
    executable = find_openstudio(openstudio_exe)
    if executable is None:
        raise FileNotFoundError(
            "OpenStudio CLI bulunamadı. OPENSTUDIO_EXE ortam değişkenini ayarlayın."
        )
    workflows = prepare_workflows(cases, project_root, output_root)
    results = [
        run_case(executable, workflow, case)
        for case, workflow in zip(cases, workflows)
    ]
    manifest = {
        "openstudio_exe": str(executable),
        "runs": [
            {
                "case": asdict(result.case),
                "success": result.success,
                "run_dir": str(result.run_dir),
                "workflow_path": str(result.workflow_path),
                "sql_path": str(result.sql_path) if result.sql_path else None,
                "return_code": result.return_code,
                "message": result.message,
            }
            for result in results
        ],
    }
    (output_root / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results
