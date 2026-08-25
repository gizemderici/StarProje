from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from iso50001 import EnergyBaseline, classify, degree_days, improvement, indicators, summary

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "data/input/weather_tmyx.epw"


class DegreeDayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.climate = degree_days(WEATHER)

    def test_uses_every_hour_of_the_year(self) -> None:
        self.assertEqual(self.climate.hours_used, 8760)

    def test_monthly_values_sum_to_the_annual_total(self) -> None:
        self.assertAlmostEqual(sum(self.climate.monthly_hdd), self.climate.hdd, places=6)
        self.assertAlmostEqual(sum(self.climate.monthly_cdd), self.climate.cdd, places=6)

    def test_mugla_is_heating_dominated_by_climate(self) -> None:
        # Bina sogutma agirlikli olmasina ragmen iklim isitma agirliklidir;
        # docs/iso50001_kapsam.md bu celiskiyi tartisir.
        self.assertGreater(self.climate.hdd, self.climate.cdd)
        self.assertGreater(self.climate.hdd, 1000)

    def test_summer_months_have_no_heating_demand(self) -> None:
        july = self.climate.monthly_hdd[6]
        self.assertLess(july, 1.0)
        self.assertGreater(self.climate.monthly_cdd[6], 100.0)

    def test_higher_base_temperature_increases_heating_degree_days(self) -> None:
        warmer = degree_days(WEATHER, heating_base_c=20.0)
        self.assertGreater(warmer.hdd, self.climate.hdd)

    def test_missing_temperature_marker_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.epw"
            header = "\n".join(f"HEADER {index}" for index in range(8))
            good = "2013,1,1,1,0,src,10.0," + ",".join(["0"] * 20)
            missing = "2013,1,1,2,0,src,99.9," + ",".join(["0"] * 20)
            path.write_text(f"{header}\n{good}\n{missing}\n", encoding="utf-8")

            climate = degree_days(path)
        self.assertEqual(climate.hours_used, 1)


class SeuTests(unittest.TestCase):
    def test_significant_uses_cover_the_threshold(self) -> None:
        uses = classify({"Cooling": 60.0, "Fans": 25.0, "Heating": 10.0, "Pumps": 5.0})
        significant = [use.name for use in uses if use.is_significant]
        self.assertEqual(significant, ["Cooling", "Fans"])

    def test_uses_are_ordered_by_energy(self) -> None:
        uses = classify({"Pumps": 5.0, "Cooling": 60.0, "Fans": 25.0})
        self.assertEqual([use.name for use in uses], ["Cooling", "Fans", "Pumps"])

    def test_shares_sum_to_one(self) -> None:
        uses = classify({"Cooling": 60.0, "Fans": 25.0, "Heating": 15.0})
        self.assertAlmostEqual(sum(use.share for use in uses), 1.0, places=9)

    def test_zero_and_negative_uses_are_dropped(self) -> None:
        uses = classify({"Cooling": 60.0, "Exterior Lighting": 0.0})
        self.assertEqual([use.name for use in uses], ["Cooling"])

    def test_empty_input_returns_empty_summary(self) -> None:
        self.assertEqual(summary({})["uses"], [])


class EnpiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = EnergyBaseline(
            source="test",
            site_energy_gj=1920.0,
            total_area_m2=4246.18,
            occupant_count=201.74,
            hdd=1782.5,
            cdd=557.5,
        )

    def test_baseline_is_flagged_as_not_measured(self) -> None:
        # Tezin sinirlilik beyani buna dayanir; sessizce olculmus gorunmemeli.
        self.assertFalse(self.baseline.measured)
        self.assertIn("kalibre edilmemistir", self.baseline.to_dict()["notice"])

    def test_energy_use_intensity_matches_manual_calculation(self) -> None:
        eui = next(item for item in indicators(1920.0, self.baseline) if item.key == "eui_kwh_m2")
        expected = (1920.0 * 1000.0 / 3.6) / 4246.18
        self.assertAlmostEqual(eui.value, expected, places=3)

    def test_lower_consumption_is_reported_as_positive_saving(self) -> None:
        result = improvement(1820.0, self.baseline)
        self.assertAlmostEqual(result["absolute_gj"], 100.0, places=2)
        self.assertGreater(result["percent"], 0)

    def test_higher_consumption_is_reported_as_negative_saving(self) -> None:
        self.assertLess(improvement(2000.0, self.baseline)["percent"], 0)

    def test_baseline_itself_shows_no_improvement(self) -> None:
        self.assertEqual(improvement(1920.0, self.baseline)["percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
