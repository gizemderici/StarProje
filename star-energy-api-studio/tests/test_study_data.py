from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ui_pages import study_data


class _Fixture:
    """Gecici bir calisma klasoru kurar ve study_data yollarini oraya baglar."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.patches = [
            mock.patch.object(study_data, "PARAMETRIC_DIR", root / "parametric"),
            mock.patch.object(study_data, "ISO_DIR", root / "iso50001"),
            mock.patch.object(study_data, "OPTIMIZATION_DIR", root / "optimization"),
            mock.patch.object(study_data, "VALIDATION_DIR", root / "validation"),
            mock.patch.object(study_data, "BASELINE_DIR", root / "baseline"),
        ]

    def __enter__(self) -> "_Fixture":
        for patch in self.patches:
            patch.start()
        return self

    def __exit__(self, *args: object) -> None:
        for patch in self.patches:
            patch.stop()

    def write_json(self, relative: str, payload: dict) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def write_text(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class MissingDataTests(unittest.TestCase):
    def test_every_reader_survives_an_empty_project(self) -> None:
        # Parametrik calisma saatler surer; arayuz "veri yok" durumunu hata
        # olarak degil normal bir asama olarak gostermelidir.
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)):
            self.assertFalse(study_data.load_study_status().ready)
            self.assertFalse(study_data.load_iso50001().ready)
            self.assertFalse(study_data.load_pareto().ready)
            self.assertFalse(study_data.load_validation().ready)
            self.assertFalse(study_data.load_baseline_diagnostics().ready)
            self.assertEqual(study_data.load_results(), [])

    def test_phase_overview_reports_all_phases_even_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)):
            phases = study_data.phase_overview()
        self.assertEqual(len(phases), 6)
        self.assertTrue(all(not item["ready"] for item in phases))

    def test_corrupt_json_is_treated_as_missing_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_text("optimization/pareto_front.json", "{bozuk")
            self.assertFalse(study_data.load_pareto().ready)


class StudyStatusTests(unittest.TestCase):
    def test_progress_is_reported_while_the_study_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_json("parametric/design.json", {"count": 151, "seed": 7, "sampler": "sobol"})
            fixture.write_text(
                "parametric/results.csv",
                "case_id,site_energy_gj\ncase_a,1900\ncase_b,1850\n",
            )
            status = study_data.load_study_status()

        self.assertTrue(status.ready)
        self.assertFalse(status.finished)
        self.assertEqual(status.completed, 2)
        self.assertEqual(status.planned, 151)
        self.assertEqual(status.sampler, "sobol")
        self.assertIn("2 / 151", status.summary())

    def test_finished_when_every_point_is_harvested(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_json("parametric/design.json", {"count": 2})
            fixture.write_text(
                "parametric/results.csv",
                "case_id,site_energy_gj\ncase_a,1900\ncase_b,1850\n",
            )
            status = study_data.load_study_status()
        self.assertTrue(status.finished)
        self.assertEqual(status.progress, 1.0)


class ParetoProvenanceTests(unittest.TestCase):
    def test_analytic_front_is_not_presented_as_ready(self) -> None:
        # Analitik taslakla uretilmis cephe tezde kullanilamaz; arayuzde
        # gercek sonuc gibi gorunmemelidir.
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_json(
                "optimization/pareto_front.json",
                {
                    "evaluator": "analytic",
                    "usable_in_thesis": False,
                    "solution_count": 40,
                    "objective_labels": ["EnPI"],
                    "solutions": [],
                    "convergence": [],
                },
            )
            view = study_data.load_pareto()
            pareto_phase = next(
                item for item in study_data.phase_overview() if item["phase"] == "Faz 6"
            )

        self.assertTrue(view.ready)
        self.assertFalse(view.usable_in_thesis)
        self.assertFalse(pareto_phase["ready"])
        self.assertIn("analytic", pareto_phase["detail"])

    def test_surrogate_front_is_presented_as_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_json(
                "optimization/pareto_front.json",
                {
                    "evaluator": "surrogate",
                    "usable_in_thesis": True,
                    "solution_count": 60,
                    "objective_labels": ["EnPI"],
                    "solutions": [],
                    "convergence": [{"generation": 1, "hypervolume": 0.4}],
                },
            )
            pareto_phase = next(
                item for item in study_data.phase_overview() if item["phase"] == "Faz 6"
            )
        self.assertTrue(pareto_phase["ready"])


class DiagnosticsTests(unittest.TestCase):
    def test_severe_errors_block_the_phase_one_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_text("baseline/eplusout.err", "   ** Severe  ** something\n")
            phase = next(
                item for item in study_data.phase_overview() if item["phase"] == "Faz 1"
            )
        self.assertFalse(phase["ready"])

    def test_clean_baseline_marks_phase_one_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            fixture.write_text("baseline/eplusout.err", "   ** Warning ** minor\n")
            phase = next(
                item for item in study_data.phase_overview() if item["phase"] == "Faz 1"
            )
        self.assertTrue(phase["ready"])


class NumericColumnTests(unittest.TestCase):
    def test_non_numeric_cells_are_skipped(self) -> None:
        rows = [{"x": "1.5"}, {"x": ""}, {"y": "3"}, {"x": "2.5"}]
        self.assertEqual(study_data.numeric_column(rows, "x"), [1.5, 2.5])


if __name__ == "__main__":
    unittest.main()
