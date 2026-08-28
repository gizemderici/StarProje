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
            mock.patch.object(study_data, "SURROGATE_DIR", root / "surrogate"),
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



class NumberFormatTests(unittest.TestCase):
    """Turkce sayi bicimi.

    Python'un varsayilan bicimi ("1,920.50") arayuzun geri kalaniyla
    tutarsizdi; bu binada 1.920 ile 1,920 farkli sayilar gibi okunuyordu.
    """

    def test_thousands_and_decimal_separators_are_swapped(self) -> None:
        from ui_pages.panels import tr

        self.assertEqual(tr(1920.5, 2), "1.920,50")
        self.assertEqual(tr(21872773.0, 0), "21.872.773")
        self.assertEqual(tr(4.5651, 2), "4,57")

    def test_negative_values_keep_their_sign(self) -> None:
        from ui_pages.panels import tr

        self.assertEqual(tr(-1.47, 2), "-1,47")

    def test_zero_digits_drops_the_decimal_part(self) -> None:
        from ui_pages.panels import tr

        self.assertEqual(tr(631.0, 0), "631")

class UnvalidatedFrontTests(unittest.TestCase):
    """Cephe yeniden uretildiginde dogrulama kaydi eskir.

    Arayuz, onceki cepheye ait sapma sayilarini yeni cepheyi doguluyormus
    gibi gostermemelidir.
    """

    def _project(self, fixture, *, validated: bool) -> None:
        fixture.write_json(
            "optimization/pareto_front.json",
            {
                "evaluator": "surrogate",
                "usable_in_thesis": True,
                "validated": validated,
                "validation_status": "guncel cephe icin bekliyor",
                "solution_count": 80,
                "objective_labels": ["EnPI"],
                "solutions": [],
                "convergence": [{"generation": 1, "hypervolume": 0.4}],
            },
        )
        fixture.write_json(
            "validation/validation_report.json",
            {
                "evaluator": "surrogate",
                "usable_in_thesis": True,
                "summary": {
                    "point_count": 8,
                    "tolerance_percent": 5.0,
                    "max_absolute_deviation_percent": 4.57,
                    "mean_absolute_deviation_percent": 1.89,
                    "within_tolerance": True,
                    "failing_points": [],
                },
                "points": [
                    {"case_id": "case_a", "deviation_percent": 4.57},
                    {"case_id": "case_b", "deviation_percent": -1.47},
                ],
            },
        )

    def test_phase_seven_is_not_ready_when_the_front_was_regenerated(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            self._project(fixture, validated=False)
            phase = next(
                item for item in study_data.phase_overview() if item["phase"] == "Faz 7"
            )
            view = study_data.load_pareto()
        self.assertFalse(phase["ready"])
        self.assertIn("bekliyor", phase["detail"])
        self.assertFalse(view.validated)

    def test_phase_seven_is_ready_when_the_front_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp, _Fixture(Path(temp)) as fixture:
            self._project(fixture, validated=True)
            phase = next(
                item for item in study_data.phase_overview() if item["phase"] == "Faz 7"
            )
        self.assertTrue(phase["ready"])
        self.assertIn("4.57", phase["detail"])


if __name__ == "__main__":
    unittest.main()
