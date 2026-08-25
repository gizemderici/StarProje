"""OSW uretimi ve OpenStudio CLI ile kosu yonetimi.

Faz 2 oncesinde bu modul yalnizca EPS kalinligini tasiyordu ve kosu klasorlerini
"eps_10cm" gibi adlandiriyordu. Artik senaryolar engine.parameters icindeki
kayittan beslenir; yeni bir karar degiskeni eklemek icin bu dosyayi degistirmek
gerekmez.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from engine.parameters import (
    BY_KEY,
    MEASURE_ORDER,
    REPORTING_MEASURES,
    baseline_parameters,
    validate_parameters,
)

DEFAULT_SEED = "data/input/gsf_fng_6mayis_onarilmis.osm"
DEFAULT_WEATHER = "data/input/weather_tmyx.epw"


@dataclass(frozen=True)
class OpenStudioCase:
    """Tek bir simulasyon senaryosu.

    parameters yalnizca referanstan sapan degerleri icerebilir; eksik kalanlar
    OSW uretilirken referans degerle doldurulur.
    """

    parameters: Mapping[str, float | str] = field(default_factory=dict)
    case_id: str = ""

    def __post_init__(self) -> None:
        validated = validate_parameters(self.parameters)
        object.__setattr__(self, "parameters", validated)
        if not self.case_id:
            object.__setattr__(self, "case_id", self._derive_id(self.resolved()))

    @staticmethod
    def _derive_id(resolved: Mapping[str, float | str]) -> str:
        """Parametrelerden turetilen kararli kimlik.

        Ayni parametre kumesi her zaman ayni klasore yazar; boylece kesintiye
        ugrayan bir toplu kosu kaldigi yerden devam edebilir.
        """
        canonical = json.dumps(dict(sorted(resolved.items())), sort_keys=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        return "case_" + digest

    def resolved(self) -> dict[str, float | str]:
        """Eksik parametreler referans degerle tamamlanmis tam kume."""
        values = baseline_parameters()
        values.update(self.parameters)
        return values

    def changes_from_baseline(self) -> dict[str, float | str]:
        baseline = baseline_parameters()
        return {
            key: value
            for key, value in self.resolved().items()
            if value != baseline[key]
        }

    def label(self) -> str:
        """Insan tarafindan okunabilir kisa ozet."""
        changes = self.changes_from_baseline()
        if not changes:
            return "referans"
        parts = []
        for key, value in sorted(changes.items()):
            spec = BY_KEY[key]
            text = value if isinstance(value, str) else format(value, "g")
            parts.append(spec.label + "=" + text + spec.unit)
        return " | ".join(parts)

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "label": self.label(),
            "parameters": self.resolved(),
            "changes": self.changes_from_baseline(),
        }


@dataclass(frozen=True, slots=True)
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
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    if program_files.exists():
        # Kurulum klasoru "OpenStudio-3.11.0" veya "openstudio-3.11.0" olabilir.
        patterns = (
            "OpenStudio-*/bin/openstudio.exe",
            "openstudio-*/bin/openstudio.exe",
        )
        for pattern in patterns:
            candidates.extend(sorted(program_files.glob(pattern), reverse=True))
        candidates.append(program_files / "OpenStudio/bin/openstudio.exe")
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def seed_fingerprint(seed_file: Path) -> str:
    """Tohum modelin icerik ozeti.

    case_id yalnizca parametrelerden turer. Tohum model degistiginde eski kosu
    klasorleri sessizce gecerli gorunur ve skip_completed onlari atlar. Parmak
    izi case.json icine yazilir ve devam kontrolunde karsilastirilir.
    """
    digest = hashlib.sha256()
    with seed_file.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def build_steps(case: OpenStudioCase) -> list[dict[str, object]]:
    """Senaryoyu OSW adimlarina cevirir.

    Tum measure'lar her kosuda calisir; belirtilmeyen parametreler referans
    degerle doldurulur. Boylece sonuc, tohum modelin o anki durumuna degil
    yalnizca senaryo tanimina baglidir.
    """
    values = case.resolved()
    grouped: dict[str, dict[str, object]] = {}
    for spec in BY_KEY.values():
        grouped.setdefault(spec.measure, {})[spec.argument] = values[spec.key]

    steps: list[dict[str, object]] = [
        {"measure_dir_name": name, "arguments": grouped[name]}
        for name in MEASURE_ORDER
        if name in grouped
    ]
    steps.extend(
        {"measure_dir_name": name, "arguments": {}} for name in REPORTING_MEASURES
    )
    return steps


def build_workflow(
    case: OpenStudioCase,
    seed_file: Path,
    weather_file: Path,
    measures_root: Path,
    workflow_dir: Path,
) -> Path:
    required = [seed_file, weather_file]
    required += [measures_root / name for name in MEASURE_ORDER]
    required += [measures_root / name for name in REPORTING_MEASURES]
    for item in required:
        if not item.exists():
            raise FileNotFoundError("Gerekli OpenStudio girdisi bulunamadi: " + str(item))

    workflow_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = workflow_dir / "workflow.osw"
    payload = {
        "seed_file": str(seed_file.resolve()),
        "weather_file": str(weather_file.resolve()),
        "measure_paths": [str(measures_root.resolve())],
        "run_directory": str((workflow_dir / "run").resolve()),
        "steps": build_steps(case),
    }
    workflow_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload_case = case.as_dict()
    payload_case["seed_fingerprint"] = seed_fingerprint(seed_file)
    payload_case["seed_file"] = seed_file.name
    (workflow_dir / "case.json").write_text(
        json.dumps(payload_case, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return workflow_path


def prepare_workflows(
    cases: Iterable[OpenStudioCase],
    project_root: Path,
    output_root: Path,
    seed_file: Path | None = None,
    weather_file: Path | None = None,
) -> list[Path]:
    return [
        build_workflow(
            case=case,
            seed_file=seed_file or project_root / DEFAULT_SEED,
            weather_file=weather_file or project_root / DEFAULT_WEATHER,
            measures_root=project_root / "integrations/OpenStudio/Measures",
            workflow_dir=output_root / case.case_id,
        )
        for case in cases
    ]


def run_case(
    openstudio_exe: Path, workflow_path: Path, case: OpenStudioCase
) -> RunResult:
    if not openstudio_exe.is_file():
        raise FileNotFoundError("OpenStudio CLI bulunamadi: " + str(openstudio_exe))
    run_root = workflow_path.parent
    options: dict[str, object] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    completed = subprocess.run(
        [str(openstudio_exe), "run", "-w", str(workflow_path)],
        cwd=run_root,
        capture_output=True,
        text=True,
        check=False,
        **options,
    )
    (run_root / "openstudio_stdout.log").write_text(
        completed.stdout, encoding="utf-8", errors="replace"
    )
    (run_root / "openstudio_stderr.log").write_text(
        completed.stderr, encoding="utf-8", errors="replace"
    )
    sql_path = next(
        (
            path
            for path in (run_root / "run/eplusout.sql", run_root / "eplusout.sql")
            if path.exists()
        ),
        None,
    )
    success = completed.returncode == 0 and sql_path is not None
    return RunResult(
        case=case,
        success=success,
        run_dir=run_root,
        workflow_path=workflow_path,
        sql_path=sql_path,
        return_code=completed.returncode,
        message=(
            "OpenStudio kosusu tamamlandi."
            if success
            else "OpenStudio kosusu basarisiz; log dosyalarini inceleyin."
        ),
    )


def _run_completed(run_dir: Path) -> bool:
    """EnergyPlus kosusunun basariyla bittigini dogrular."""
    end_file = run_dir / "eplusout.end"
    if not end_file.is_file():
        return False
    return "Completed Successfully" in end_file.read_text(
        encoding="utf-8", errors="ignore"
    )


def _recorded_seeds(output_root: Path) -> dict[str, str]:
    """Mevcut kosularin hangi tohumla uretildigini case.json'dan okur.

    Parmak izi kosu aninda kaydedilir; sonradan yoldan yeniden hesaplanamaz,
    cunku tohum dosya o yolda degismis olabilir. Bu okuma prepare_workflows
    case.json'i yeniden yazmadan ONCE yapilmalidir.
    """
    recorded: dict[str, str] = {}
    for case_path in output_root.glob("case_*/case.json"):
        try:
            payload = json.loads(case_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        fingerprint = payload.get("seed_fingerprint")
        if fingerprint:
            recorded[case_path.parent.name] = str(fingerprint)
    return recorded


def _run_one(payload: tuple[str, str, dict]) -> dict:
    """ProcessPoolExecutor icin ust duzey sarmalayici; pickle edilebilir olmali."""
    exe, workflow, case_payload = payload
    case = OpenStudioCase(
        parameters=case_payload["parameters"], case_id=case_payload["case_id"]
    )
    result = run_case(Path(exe), Path(workflow), case)
    return {
        "case": case.as_dict(),
        "success": result.success,
        "run_dir": str(result.run_dir),
        "workflow_path": str(result.workflow_path),
        "sql_path": str(result.sql_path) if result.sql_path else None,
        "return_code": result.return_code,
        "message": result.message,
    }


def run_cases(
    cases: list[OpenStudioCase],
    project_root: Path,
    output_root: Path,
    openstudio_exe: Path | None = None,
    seed_file: Path | None = None,
    weather_file: Path | None = None,
    max_workers: int | None = None,
    skip_completed: bool = True,
) -> list[dict]:
    """Senaryolari paralel calistirir ve manifest yazar.

    skip_completed acikken SQL ciktisi zaten olusmus senaryolar atlanir; boylece
    kesintiye ugrayan toplu kosu kaldigi yerden devam eder.
    """
    executable = find_openstudio(openstudio_exe)
    if executable is None:
        raise FileNotFoundError(
            "OpenStudio CLI bulunamadi. OPENSTUDIO_EXE ortam degiskenini ayarlayin."
        )
    active_seed = seed_fingerprint(seed_file or project_root / DEFAULT_SEED)
    # prepare_workflows case.json'i yeniden yazar; onceki parmak izlerini
    # kaybetmemek icin once okuyoruz.
    previous_seeds = _recorded_seeds(output_root) if output_root.is_dir() else {}

    workflows = prepare_workflows(
        cases, project_root, output_root, seed_file, weather_file
    )

    pending: list[tuple[str, str, dict]] = []
    results: list[dict] = []
    stale = 0
    for case, workflow in zip(cases, workflows):
        existing = workflow.parent / "run/eplusout.sql"
        # SQL'in VARLIGI yetmez: yarida kesilen bir kosu da eplusout.sql birakir.
        # Tamamlanma olcutu EnergyPlus'in kendi bitis kaydidir.
        if skip_completed and existing.exists() and _run_completed(workflow.parent / "run"):
            # Parmak izi eslesmiyorsa ya da hic kaydedilmemisse kosu eskimistir.
            produced_with = previous_seeds.get(workflow.parent.name)
            if produced_with is None or produced_with != active_seed:
                stale += 1
                shutil.rmtree(workflow.parent / "run", ignore_errors=True)
                pending.append((str(executable), str(workflow), case.as_dict()))
                continue
            results.append(
                {
                    "case": case.as_dict(),
                    "success": True,
                    "run_dir": str(workflow.parent),
                    "workflow_path": str(workflow),
                    "sql_path": str(existing),
                    "return_code": 0,
                    "message": "Onceki kosu bulundu, atlandi.",
                }
            )
            continue
        pending.append((str(executable), str(workflow), case.as_dict()))

    if stale:
        print(f"{stale} kosu farkli bir tohum modelle uretilmis; yeniden calisacak.")

    if pending:
        workers = max_workers or max(1, (os.cpu_count() or 2) - 1)
        if workers == 1 or len(pending) == 1:
            results.extend(_run_one(item) for item in pending)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results.extend(pool.map(_run_one, pending))

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "run_manifest.json").write_text(
        json.dumps(
            {"openstudio_exe": str(executable), "runs": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results
