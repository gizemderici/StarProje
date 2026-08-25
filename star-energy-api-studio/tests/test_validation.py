from __future__ import annotations

import unittest

import numpy as np

from optimization.problem import extreme_indices, topsis
from validation.selection import deviation, select_points, summarise

LABELS = ["EnPI", "Maliyet", "Konfor"]


def _solutions(front: list[list[float]]) -> list[dict]:
    return [
        {
            "parameters": {"chiller_cop": 4.0 + index * 0.1, "window_construction": "penc_std_4mm"},
            "objectives": dict(zip(LABELS, values)),
        }
        for index, values in enumerate(front)
    ]


class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        # Uc amacli, on cozumlu yapay cephe.
        self.front = np.array(
            [
                [10.0, 900.0, 90.0],
                [90.0, 100.0, 80.0],
                [80.0, 800.0, 10.0],
                [50.0, 500.0, 50.0],
                [30.0, 700.0, 60.0],
                [70.0, 300.0, 40.0],
                [40.0, 600.0, 55.0],
                [60.0, 400.0, 45.0],
                [20.0, 850.0, 75.0],
                [85.0, 200.0, 30.0],
            ]
        )
        self.solutions = _solutions(self.front.tolist())

    def test_every_extreme_is_selected(self) -> None:
        # Vekil model cephenin kenarlarinda en cok zorlanir; uc noktalar sart.
        points = select_points(
            self.solutions, LABELS, topsis(self.front), extreme_indices(self.front), total=6
        )
        selected = {point.index for point in points}
        for index in extreme_indices(self.front).values():
            self.assertIn(index, selected)

    def test_compromise_solution_is_selected(self) -> None:
        compromise = topsis(self.front)
        points = select_points(
            self.solutions, LABELS, compromise, extreme_indices(self.front), total=6
        )
        chosen = next(point for point in points if point.index == compromise)
        self.assertIn("TOPSIS", chosen.reason)

    def test_requested_count_is_respected(self) -> None:
        for total in (4, 6, 8):
            points = select_points(
                self.solutions, LABELS, topsis(self.front), extreme_indices(self.front), total=total
            )
            self.assertLessEqual(len(points), total)
            self.assertGreaterEqual(len(points), min(total, 4))

    def test_points_are_unique(self) -> None:
        points = select_points(
            self.solutions, LABELS, topsis(self.front), extreme_indices(self.front), total=8
        )
        indices = [point.index for point in points]
        self.assertEqual(len(indices), len(set(indices)))

    def test_training_points_are_excluded_by_default(self) -> None:
        # Varsayilan davranis dislamadir; isaretleme yalnizca
        # exclude_training=False verildiginde kullanilir.
        training = [self.solutions[0]["parameters"]]
        points = select_points(
            self.solutions,
            LABELS,
            topsis(self.front),
            extreme_indices(self.front),
            total=6,
            training_parameters=training,
        )
        self.assertNotIn(0, [point.index for point in points])
        self.assertFalse(any("egitim kumesinde" in point.reason for point in points))

    def test_empty_front_returns_no_points(self) -> None:
        self.assertEqual(select_points([], LABELS, 0, {}, total=5), [])


class DeviationTests(unittest.TestCase):
    def test_overprediction_is_positive(self) -> None:
        self.assertAlmostEqual(deviation(110.0, 100.0), 10.0)

    def test_underprediction_is_negative(self) -> None:
        self.assertAlmostEqual(deviation(90.0, 100.0), -10.0)

    def test_zero_actual_does_not_divide_by_zero(self) -> None:
        self.assertEqual(deviation(5.0, 0.0), 0.0)


class SummaryTests(unittest.TestCase):
    def test_gate_passes_when_every_point_is_within_tolerance(self) -> None:
        rows = [
            {"case_id": "a", "deviation_percent": 2.0},
            {"case_id": "b", "deviation_percent": -3.5},
        ]
        summary = summarise(rows, tolerance_percent=5.0)
        self.assertTrue(summary["within_tolerance"])
        self.assertEqual(summary["failing_points"], [])
        self.assertAlmostEqual(summary["max_absolute_deviation_percent"], 3.5)

    def test_gate_fails_and_names_the_offending_points(self) -> None:
        rows = [
            {"case_id": "a", "deviation_percent": 2.0},
            {"case_id": "b", "deviation_percent": 9.1},
        ]
        summary = summarise(rows, tolerance_percent=5.0)
        self.assertFalse(summary["within_tolerance"])
        self.assertEqual(summary["failing_points"], ["b"])

    def test_empty_input_is_handled(self) -> None:
        summary = summarise([], tolerance_percent=5.0)
        self.assertEqual(summary["point_count"], 0)
        self.assertTrue(summary["within_tolerance"])



class AdaptiveSamplingTests(unittest.TestCase):
    """Adaptif ornekleme turlerinde dairesel dogrulamaya karsi koruma."""

    def setUp(self) -> None:
        self.front = np.array(
            [[10.0, 900.0, 90.0], [90.0, 100.0, 80.0], [80.0, 800.0, 10.0],
             [50.0, 500.0, 50.0], [30.0, 700.0, 60.0], [70.0, 300.0, 40.0]]
        )
        self.solutions = _solutions(self.front.tolist())

    def test_training_points_are_excluded_by_default(self) -> None:
        # Onceki turun dogrulama noktalari egitim kumesine eklenir; yeniden
        # secilirlerse dogrulama modelin ezberini olcer.
        training = [self.solutions[0]["parameters"], self.solutions[1]["parameters"]]
        points = select_points(
            self.solutions, LABELS, topsis(self.front), extreme_indices(self.front),
            total=6, training_parameters=training,
        )
        self.assertNotIn(0, [p.index for p in points])
        self.assertNotIn(1, [p.index for p in points])

    def test_flagging_mode_still_available(self) -> None:
        training = [self.solutions[0]["parameters"]]
        points = select_points(
            self.solutions, LABELS, topsis(self.front), extreme_indices(self.front),
            total=6, training_parameters=training, exclude_training=False,
        )
        flagged = [p for p in points if "egitim kumesinde" in p.reason]
        self.assertEqual(len(flagged), 1)

    def test_all_points_trained_returns_empty(self) -> None:
        training = [s["parameters"] for s in self.solutions]
        points = select_points(
            self.solutions, LABELS, topsis(self.front), extreme_indices(self.front),
            total=6, training_parameters=training,
        )
        self.assertEqual(points, [])

if __name__ == "__main__":
    unittest.main()
