"""Faz 3-7 ciktilarini arayuz icin okuyan katman.

Bu modul NiceGUI'ye bagimli DEGILDIR; saf Python okuyucularla test edilebilir.
Arayuz katmani (ui_pages/panels.py) yalnizca burayi cagirir.

Her okuyucu, veri henuz uretilmemisken de calisir ve `ready` bayragi ile durumu
bildirir. Parametrik calisma saatler surdugu icin arayuz "veri yok" durumunu
hata olarak degil normal bir asama olarak gostermelidir.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PARAMETRIC_DIR = ROOT / "data/parametric"
ISO_DIR = ROOT / "data/iso50001"
OPTIMIZATION_DIR = ROOT / "data/optimization"
SURROGATE_DIR = ROOT / "data/surrogate"
VALIDATION_DIR = ROOT / "data/validation"
BASELINE_DIR = ROOT / "data/baseline_v1"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


@dataclass(slots=True)
class StudyStatus:
    """Parametrik calismanin ilerleme durumu."""

    planned: int = 0
    completed: int = 0
    unique_results: int = 0
    all_unique: bool = False
    with_severe_errors: list[str] = field(default_factory=list)
    sampler: str = "-"
    seed: int = 0
    site_energy_min_gj: float = 0.0
    site_energy_max_gj: float = 0.0

    @property
    def ready(self) -> bool:
        return self.completed > 0

    @property
    def finished(self) -> bool:
        return self.planned > 0 and self.completed >= self.planned

    @property
    def progress(self) -> float:
        return self.completed / self.planned if self.planned else 0.0

    def summary(self) -> str:
        if not self.planned:
            return "Parametrik calisma henuz baslatilmadi."
        if self.finished:
            return f"{self.completed} kosu tamamlandi."
        return f"{self.completed} / {self.planned} kosu tamamlandi."


def load_study_status() -> StudyStatus:
    design = _read_json(PARAMETRIC_DIR / "design.json") or {}
    report = _read_json(PARAMETRIC_DIR / "uniqueness_report.json") or {}
    rows = _read_csv(PARAMETRIC_DIR / "results.csv")

    return StudyStatus(
        planned=int(design.get("count", 0)),
        completed=len(rows),
        unique_results=int(report.get("unique_result_count", 0)),
        all_unique=bool(report.get("all_unique", False)),
        with_severe_errors=list(report.get("runs_with_severe_errors", [])),
        sampler=str(design.get("sampler", "-")),
        seed=int(design.get("seed", 0)),
        site_energy_min_gj=float(report.get("site_energy_min_gj", 0.0)),
        site_energy_max_gj=float(report.get("site_energy_max_gj", 0.0)),
    )


def load_results() -> list[dict[str, str]]:
    """Parametrik sonuc tablosu."""
    return _read_csv(PARAMETRIC_DIR / "results.csv")


def numeric_column(rows: list[dict[str, str]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row[key]))
        except (KeyError, TypeError, ValueError):
            continue
    return values


@dataclass(slots=True)
class Iso50001View:
    ready: bool = False
    baseline_gj: float = 0.0
    baseline_measured: bool = False
    eui_kwh_m2: float = 0.0
    hdd: float = 0.0
    cdd: float = 0.0
    significant_uses: list[str] = field(default_factory=list)
    uses: list[dict[str, Any]] = field(default_factory=list)
    indicators: list[dict[str, Any]] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    notice: str = ""


def load_iso50001() -> Iso50001View:
    payload = _read_json(ISO_DIR / "iso50001_report.json")
    if not payload:
        return Iso50001View()

    baseline = payload.get("energy_baseline", {})
    climate = payload.get("climate", {})
    seu = payload.get("significant_energy_uses", {})
    indicators = payload.get("baseline_indicators", [])
    eui = next(
        (item["value"] for item in indicators if item.get("key") == "eui_kwh_m2"), 0.0
    )
    return Iso50001View(
        ready=True,
        baseline_gj=float(baseline.get("site_energy_gj", 0.0)),
        baseline_measured=bool(baseline.get("measured", False)),
        eui_kwh_m2=float(eui),
        hdd=float(climate.get("hdd", 0.0)),
        cdd=float(climate.get("cdd", 0.0)),
        significant_uses=list(seu.get("significant_uses", [])),
        uses=list(seu.get("uses", [])),
        indicators=list(indicators),
        scenarios=list(payload.get("scenarios", [])),
        notice=str(baseline.get("notice", "")),
    )


@dataclass(slots=True)
class ParetoView:
    ready: bool = False
    evaluator: str = "unknown"
    usable_in_thesis: bool = False
    solution_count: int = 0
    objective_labels: list[str] = field(default_factory=list)
    solutions: list[dict[str, Any]] = field(default_factory=list)
    convergence: list[dict[str, float]] = field(default_factory=list)

    @property
    def hypervolume_start(self) -> float:
        return self.convergence[0]["hypervolume"] if self.convergence else 0.0

    @property
    def hypervolume_end(self) -> float:
        return self.convergence[-1]["hypervolume"] if self.convergence else 0.0

    def objective_values(self, axis: int) -> list[float]:
        label = self.objective_labels[axis] if axis < len(self.objective_labels) else ""
        return [
            float(item["objectives"][label])
            for item in self.solutions
            if label in item.get("objectives", {})
        ]


def load_pareto() -> ParetoView:
    payload = _read_json(OPTIMIZATION_DIR / "pareto_front.json")
    if not payload:
        return ParetoView()
    return ParetoView(
        ready=True,
        evaluator=str(payload.get("evaluator", "unknown")),
        usable_in_thesis=bool(payload.get("usable_in_thesis", False)),
        solution_count=int(payload.get("solution_count", 0)),
        objective_labels=list(payload.get("objective_labels", [])),
        solutions=list(payload.get("solutions", [])),
        convergence=list(payload.get("convergence", [])),
    )


@dataclass(slots=True)
class SurrogateView:
    ready: bool = False
    rows: int = 0
    features: int = 0
    gate_passed: bool = False
    gate_targets: list[str] = field(default_factory=list)
    test_scores: list[dict[str, Any]] = field(default_factory=list)
    sensitivity: list[dict[str, Any]] = field(default_factory=list)
    speedup_ratio: float = 0.0
    seconds_per_call: float = 0.0

    def test_rows(self) -> list[dict[str, Any]]:
        """Test kumesi tablosunu arayuz icin duzlestirir.

        Hedefe gore olcut degistigi icin (seyrek hedeflerde CVRMSE yaniltir)
        gosterilen hata sutunu da hedefe gore secilir.
        """
        rows = []
        for item in self.test_scores:
            sparse = item.get("metric", "").startswith("NRMSE")
            error = (
                item.get("nrmse_range_percent", 0.0)
                if sparse
                else item.get("cvrmse_percent", 0.0)
            )
            gating = item["target"] in self.gate_targets
            if gating:
                gate = "GECTI" if item.get("meets_target") else "KALDI"
            else:
                gate = "kapi disi"
            rows.append(
                {
                    "target": item["target"],
                    "model": item["model"],
                    "r2": round(float(item.get("r2", 0.0)), 3),
                    "metric": item.get("metric", "-"),
                    "error": f"%{float(error):.2f}",
                    "gate": gate,
                }
            )
        return rows


def load_surrogate() -> SurrogateView:
    payload = _read_json(SURROGATE_DIR / "surrogate_report.json")
    if not payload:
        return SurrogateView()
    dataset = payload.get("dataset", {})
    speedup = payload.get("speedup", {})
    return SurrogateView(
        ready=True,
        rows=int(dataset.get("rows", 0)),
        features=int(dataset.get("features", 0)),
        gate_passed=bool(payload.get("gate_passed", False)),
        gate_targets=list(payload.get("gate_targets", [])),
        test_scores=list(payload.get("test_scores", [])),
        sensitivity=list(payload.get("sensitivity", {}).get("indices", [])),
        speedup_ratio=float(speedup.get("ratio", 0.0)),
        seconds_per_call=float(speedup.get("surrogate_seconds_per_call", 0.0)),
    )


@dataclass(slots=True)
class ValidationView:
    ready: bool = False
    points: list[dict[str, Any]] = field(default_factory=list)
    max_deviation_percent: float = 0.0
    within_tolerance: bool = False


def load_validation(tolerance_percent: float = 5.0) -> ValidationView:
    payload = _read_json(VALIDATION_DIR / "validation_report.json")
    if not payload:
        return ValidationView()
    points = list(payload.get("points", []))
    deviations = [abs(float(item.get("deviation_percent", 0.0))) for item in points]
    worst = max(deviations) if deviations else 0.0
    return ValidationView(
        ready=True,
        points=points,
        max_deviation_percent=worst,
        within_tolerance=worst <= tolerance_percent,
    )


@dataclass(slots=True)
class DiagnosticsView:
    ready: bool = False
    severe_errors: int = 0
    warnings: int = 0
    zone_temperature_range: dict[str, tuple[float, float]] = field(default_factory=dict)


def load_baseline_diagnostics() -> DiagnosticsView:
    error_file = BASELINE_DIR / "eplusout.err"
    if not error_file.is_file():
        return DiagnosticsView()
    text = error_file.read_text(encoding="utf-8", errors="ignore")
    return DiagnosticsView(
        ready=True,
        severe_errors=text.count("** Severe"),
        warnings=text.count("** Warning"),
    )


def phase_overview() -> list[dict[str, Any]]:
    """Arayuzun ust seridinde gosterilecek faz durumu."""
    study = load_study_status()
    surrogate = load_surrogate()
    iso = load_iso50001()
    pareto = load_pareto()
    validation = load_validation()
    diagnostics = load_baseline_diagnostics()

    return [
        {
            "phase": "Faz 1",
            "title": "Model onarimi",
            "ready": diagnostics.ready and diagnostics.severe_errors == 0,
            "detail": (
                f"{diagnostics.severe_errors} Severe, {diagnostics.warnings} uyari"
                if diagnostics.ready
                else "taban kosusu yok"
            ),
        },
        {
            "phase": "Faz 3",
            "title": "Parametrik set",
            "ready": study.finished,
            "detail": study.summary(),
        },
        {
            "phase": "Faz 4",
            "title": "Vekil model",
            "ready": surrogate.ready and surrogate.gate_passed,
            "detail": (
                f"{surrogate.rows} satir, kapi "
                + ("gecildi" if surrogate.gate_passed else "gecilmedi")
                if surrogate.ready
                else "egitilmedi"
            ),
        },
        {
            "phase": "Faz 5",
            "title": "ISO 50001",
            "ready": iso.ready,
            "detail": (
                f"SEU: {', '.join(iso.significant_uses)}" if iso.ready else "rapor yok"
            ),
        },
        {
            "phase": "Faz 6",
            "title": "Pareto",
            # Analitik taslakla uretilmis cephe HAZIR sayilmaz; tezde
            # kullanilamaz ve arayuzde gercek sonuc gibi gorunmemelidir.
            "ready": pareto.ready and pareto.usable_in_thesis,
            "detail": (
                f"{pareto.solution_count} cozum ({pareto.evaluator})"
                if pareto.ready
                else "cephe uretilmedi"
            ),
        },
        {
            "phase": "Faz 7",
            "title": "Dogrulama",
            "ready": validation.ready and validation.within_tolerance,
            "detail": (
                f"en buyuk sapma %{validation.max_deviation_percent:.2f}"
                if validation.ready
                else "dogrulama kosusu yok"
            ),
        },
    ]
