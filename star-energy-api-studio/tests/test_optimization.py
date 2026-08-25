from __future__ import annotations

import unittest

from engine.parameters import baseline_parameters
from optimization import estimate, evaluate, wall_u_value, zero_cost_measures
from optimization.cost_model import OPAQUE_WALL_AREA_M2, WINDOW_AREA_M2
from optimization.objectives import TS825_MAX_U, TS825_ZONE, window_u_from_results


def _flat_evaluator(energy_gj: float = 1920.0, comfort: float = 118.0):
    def evaluator(_parameters):
        return energy_gj, comfort

    return evaluator


class WallUValueTests(unittest.TestCase):
    def test_matches_energyplus_for_the_baseline_wall(self) -> None:
        # EnergyPlus taban kosusunda duvr_std_eps icin 0,2901 W/m2K raporluyor.
        self.assertAlmostEqual(wall_u_value(5.0, 0.039), 0.2901, places=4)

    def test_thicker_insulation_lowers_u_value(self) -> None:
        self.assertLess(wall_u_value(15.0, 0.039), wall_u_value(5.0, 0.039))

    def test_zero_conductivity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            wall_u_value(5.0, 0.0)

    def test_baseline_wall_already_satisfies_ts825(self) -> None:
        # Duvar zaten uygun; yalitim kalinligi bu binada kisit belirleyici degil.
        baseline_u = wall_u_value(5.0, 0.039)
        self.assertLess(baseline_u, TS825_MAX_U[TS825_ZONE]["wall"])


class CostModelTests(unittest.TestCase):
    def test_baseline_scenario_costs_nothing(self) -> None:
        self.assertEqual(estimate(baseline_parameters()).total, 0.0)

    def test_window_cost_uses_the_measured_glazing_area(self) -> None:
        cost = estimate({"window_construction": "penc_lowe_argon_4mm"})
        window = next(item for item in cost.items if item.key == "window")
        self.assertAlmostEqual(window.amount, 1150.0 * WINDOW_AREA_M2, places=2)

    def test_eps_cost_uses_opaque_wall_area_not_gross(self) -> None:
        # Opak duvar 443,33 m2; brut duvar 2.072,10 m2. Brut alan kullanilirsa
        # yalitim maliyeti bes kat sisirilir.
        cost = estimate({"eps_thickness_cm": 6.0})
        eps = next(item for item in cost.items if item.key == "eps")
        self.assertAlmostEqual(eps.amount, 1.0 * 95.0 * OPAQUE_WALL_AREA_M2, places=2)

    def test_worse_than_baseline_choices_do_not_create_negative_cost(self) -> None:
        cost = estimate(
            {
                "eps_thickness_cm": 1.0,
                "chiller_cop": 3.0,
                "boiler_efficiency": 0.70,
                "infiltration_multiplier": 1.4,
            }
        )
        for item in cost.items:
            self.assertGreaterEqual(item.amount, 0.0)

    def test_elevator_replacement_is_all_or_nothing(self) -> None:
        replaced = estimate({"elevator_power_w": 1500.0})
        kept = estimate({"elevator_power_w": 6000.0})
        elevator_replaced = next(i for i in replaced.items if i.key == "elevator")
        elevator_kept = next(i for i in kept.items if i.key == "elevator")
        self.assertGreater(elevator_replaced.amount, 0.0)
        self.assertEqual(elevator_kept.amount, 0.0)

    def test_setpoint_changes_are_reported_as_zero_cost(self) -> None:
        # ISO 50001 acisindan en makbul eylem tipi; maliyet modeline girmemeli.
        cost = estimate({"cooling_setpoint_c": 26.0})
        self.assertEqual(cost.total, 0.0)
        self.assertEqual(zero_cost_measures({"cooling_setpoint_c": 26.0}), ["cooling_setpoint_c"])

    def test_estimate_carries_the_assumption_notice(self) -> None:
        self.assertIn("varsayimdir", estimate({}).to_dict()["notice"])


class ObjectiveTests(unittest.TestCase):
    def test_objectives_are_all_minimised_quantities(self) -> None:
        objectives, _, _ = evaluate({}, _flat_evaluator())
        vector = objectives.as_vector()
        self.assertEqual(len(vector), 3)
        self.assertGreater(vector[0], 0)

    def test_enpi_matches_manual_conversion(self) -> None:
        objectives, _, _ = evaluate({}, _flat_evaluator(energy_gj=1920.0))
        expected = 1920.0 * 1000.0 / 3.6 / 4246.18
        self.assertAlmostEqual(objectives.enpi_kwh_m2, expected, places=4)

    def test_budget_violation_is_positive_when_over_limit(self) -> None:
        # Ucu cam + chiller yukseltmesi tek basina butceyi asmiyor; tam kapsamli
        # bir yenileme paketi asiyor.
        expensive = {
            "window_construction": "penc_triple_lowe_4mm",
            "chiller_cop": 8.0,
            "lighting_primary_w_m2": 4.0,
            "lighting_secondary_w_m2": 2.0,
        }
        _, checks, cost = evaluate(expensive, _flat_evaluator())
        self.assertGreater(cost.total, 6_000_000.0)
        self.assertGreater(checks.budget, 0)
        self.assertFalse(checks.feasible)

    def test_moderate_package_stays_within_budget(self) -> None:
        _, checks, _ = evaluate(
            {"window_construction": "penc_lowe_argon_4mm"}, _flat_evaluator()
        )
        self.assertLess(checks.budget, 0)

    def test_comfort_violation_is_positive_when_over_limit(self) -> None:
        _, checks, _ = evaluate({}, _flat_evaluator(comfort=900.0))
        self.assertGreater(checks.comfort, 0)
        self.assertFalse(checks.feasible)

    def test_missing_window_lookup_is_reported_not_silently_passed(self) -> None:
        _, checks, _ = evaluate({}, _flat_evaluator())
        self.assertEqual(checks.window_u, 0.0)
        self.assertTrue(any("TS 825" in note for note in checks.notes))

    def test_window_lookup_enables_the_glazing_constraint(self) -> None:
        # Taban cami olculen U = 2,718; 3. bolge siniri 2,00. Uygun degil.
        lookup = {"penc_std_4mm": 2.718}
        _, checks, _ = evaluate({}, _flat_evaluator(), window_u_lookup=lookup)
        self.assertAlmostEqual(checks.window_u, 2.718 - 2.00, places=3)
        self.assertFalse(checks.feasible)
        self.assertEqual(checks.notes, [])


class WindowLookupTests(unittest.TestCase):
    def test_lookup_is_built_from_run_results(self) -> None:
        rows = [
            {"window_construction": "penc_std_4mm", "glass_u_factor": "2.718"},
            {"window_construction": "penc_lowe_4mm", "glass_u_factor": "1.82"},
            {"window_construction": "penc_std_4mm", "glass_u_factor": "2.718"},
        ]
        lookup = window_u_from_results(rows)
        self.assertEqual(lookup, {"penc_std_4mm": 2.718, "penc_lowe_4mm": 1.82})

    def test_rows_without_a_u_value_are_skipped(self) -> None:
        rows = [
            {"window_construction": "penc_std_4mm", "glass_u_factor": ""},
            {"window_construction": "", "glass_u_factor": "2.0"},
        ]
        self.assertEqual(window_u_from_results(rows), {})


if __name__ == "__main__":
    unittest.main()
