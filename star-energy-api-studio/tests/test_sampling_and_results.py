from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine.parameters import BY_KEY, PARAMETERS
from engine.results import harvest_all, is_complete, uniqueness_report
from engine.sampling import build_design


class SamplingTests(unittest.TestCase):
    def test_design_always_contains_the_baseline_point(self) -> None:
        # Star.zip parametrik calismasinin cokme sebebi izgaranin referansi
        # kapsamamasiydi: 19 senaryonun hepsi referanstan kotu cikti.
        design = build_design(count=8)
        self.assertEqual(design[0].role, "baseline")
        baseline = design[0].parameters
        for spec in PARAMETERS:
            self.assertEqual(baseline[spec.key], spec.baseline)

    def test_every_sampled_value_is_inside_its_bounds(self) -> None:
        for point in build_design(count=64):
            for key, value in point.parameters.items():
                spec = BY_KEY[key]
                if spec.is_categorical:
                    self.assertIn(value, spec.choices)
                else:
                    self.assertGreaterEqual(value, spec.minimum)
                    self.assertLessEqual(value, spec.maximum)

    def test_design_is_reproducible_from_the_seed(self) -> None:
        first = [point.parameters for point in build_design(count=16, seed=7)]
        second = [point.parameters for point in build_design(count=16, seed=7)]
        self.assertEqual(first, second)

    def test_different_seeds_give_different_designs(self) -> None:
        first = [point.parameters for point in build_design(count=16, seed=7)]
        second = [point.parameters for point in build_design(count=16, seed=8)]
        self.assertNotEqual(first, second)

    def test_categorical_axis_reaches_every_choice(self) -> None:
        seen = {point.parameters["window_construction"] for point in build_design(count=96)}
        self.assertEqual(seen, set(BY_KEY["window_construction"].choices))


def _make_case(root: Path, case_id: str, *, completed: bool) -> Path:
    case_dir = root / case_id
    run_dir = case_dir / "run"
    run_dir.mkdir(parents=True)
    (case_dir / "case.json").write_text(
        json.dumps({"case_id": case_id, "label": "test", "parameters": {}}),
        encoding="utf-8",
    )
    connection = sqlite3.connect(run_dir / "eplusout.sql")
    if completed:
        # Tamamlanmis kosuda EnergyPlus sonuc tablosunu birakir.
        connection.execute(
            "CREATE TABLE TabularDataWithStrings "
            "(ReportName TEXT, TableName TEXT, RowName TEXT, ColumnName TEXT, Value TEXT)"
        )
        connection.execute(
            "INSERT INTO TabularDataWithStrings VALUES "
            "('AnnualBuildingUtilityPerformanceSummary', 'Site and Source Energy', "
            "'Total Site Energy', 'Total Energy', '1920.00')"
        )
        connection.commit()
    # Yarida kesilen kosu ise gecerli ama tablosuz bir SQLite dosyasi birakir.
    connection.close()
    if completed:
        (run_dir / "eplusout.end").write_text(
            "EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors",
            encoding="utf-8",
        )
    return case_dir


class HarvestCompletenessTests(unittest.TestCase):
    def test_incomplete_run_is_not_harvested(self) -> None:
        # Yarida kesilen kosu da eplusout.sql birakir; tablolar bos oldugu icin
        # butun metrikler 0.0 okunur ve tabloya sahte bir satir girerdi.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_case(root, "case_bitmis", completed=True)
            _make_case(root, "case_yarim", completed=False)

            outcomes, incomplete = harvest_all(root)

        self.assertEqual([item.case_id for item in outcomes], ["case_bitmis"])
        self.assertEqual(incomplete, ["case_yarim"])

    def test_is_complete_requires_energyplus_success_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run"
            run_dir.mkdir()
            self.assertFalse(is_complete(run_dir))

            (run_dir / "eplusout.end").write_text("EnergyPlus Terminated", encoding="utf-8")
            self.assertFalse(is_complete(run_dir))

            (run_dir / "eplusout.end").write_text(
                "EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors",
                encoding="utf-8",
            )
            self.assertTrue(is_complete(run_dir))


class UniquenessReportTests(unittest.TestCase):
    def test_identical_results_are_reported_as_duplicates(self) -> None:
        # Depodaki 5/10/15 cm arsiv kosulari birebir ayni sonucu veriyordu.
        # Rapor ayni durumu yakalayabilmelidir.
        from engine.results import RunOutcome

        def outcome(case_id: str, energy: float) -> RunOutcome:
            return RunOutcome(
                case_id=case_id,
                label="",
                parameters={},
                site_energy_gj=energy,
                eui_mj_m2=0.0,
                total_area_m2=0.0,
                heating_gj=1.0,
                cooling_gj=2.0,
                lighting_gj=3.0,
                equipment_gj=4.0,
                fans_gj=0.0,
                pumps_gj=0.0,
                unmet_heating_hours=0.0,
                unmet_cooling_hours=0.0,
                ashrae55_discomfort_hours=0.0,
                comfort_violation_hours=0.0,
                severe_errors=0,
                warnings=0,
            )

        same = uniqueness_report([outcome("a", 100.0), outcome("b", 100.0)])
        self.assertFalse(same["all_unique"])
        self.assertEqual(same["unique_result_count"], 1)

        different = uniqueness_report([outcome("a", 100.0), outcome("b", 101.0)])
        self.assertTrue(different["all_unique"])
        self.assertEqual(different["unique_result_count"], 2)



class SamplerSelectionTests(unittest.TestCase):
    def test_sampler_choice_is_recorded_not_silent(self) -> None:
        # Ornekleyici yorumlayiciya gore degisir; hangisinin kullanildigi
        # design.json icine yazilmazsa calisma tekrar uretilemez.
        from engine.sampling import available_sampler, build_design, write_design

        build_design(count=8)
        self.assertIn(build_design.last_sampler, ("sobol", "halton"))
        self.assertEqual(build_design.last_sampler, available_sampler())

        with tempfile.TemporaryDirectory() as temp:
            path = write_design(build_design(count=8), Path(temp) / "design.json", 7)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn(payload["sampler"], ("sobol", "halton"))

    def test_halton_can_be_forced_without_scipy(self) -> None:
        from engine.sampling import build_design

        design = build_design(count=8, sampler="halton")
        self.assertEqual(build_design.last_sampler, "halton")
        self.assertEqual(len(design), 9)

    def test_unknown_sampler_is_rejected(self) -> None:
        from engine.sampling import build_design

        with self.assertRaises(ValueError):
            build_design(count=4, sampler="rastgele")

if __name__ == "__main__":
    unittest.main()
