from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine.parameters import BY_KEY, PARAMETERS, baseline_parameters
from engine.sampling import build_design
from surrogate.dataset import (
    CATEGORICAL_KEYS,
    CONTINUOUS_KEYS,
    TARGETS,
    encode_row,
    feature_names,
    load_dataset,
    minimum_rows_for,
)
from surrogate.models import (
    best_per_target,
    compare,
    cross_validate,
    cvrmse,
    nmbe,
    r_squared,
    score,
)
from surrogate.models import CANDIDATES


def _write_results(path: Path, count: int = 60, include_broken: bool = False) -> Path:
    """Bilinen bir fonksiyondan sentetik sonuc tablosu uretir."""
    rows = []
    window_effect = {
        "penc_std_4mm": 0.0,
        "penc_lowe_4mm": -110.0,
        "penc_lowe_argon_4mm": -160.0,
        "penc_cont_6_4mm": -130.0,
        "penc_triple_lowe_4mm": -180.0,
        "penc_snerji_4mm": -150.0,
        "penc_renk_6mm": -60.0,
    }
    for point in build_design(count=count, seed=11):
        parameters = point.parameters
        energy = (
            1920.0
            - 90.0 * (parameters["chiller_cop"] - 5.5)
            - 45.0 * (parameters["cooling_setpoint_c"] - 24.0)
            + window_effect[str(parameters["window_construction"])]
        )
        row = dict(parameters)
        row["case_id"] = f"case_{point.index:04d}"
        row["site_energy_gj"] = round(energy, 4)
        row["cooling_gj"] = round(energy * 0.58, 4)
        row["heating_gj"] = round(max(energy * 0.024, 1.0), 4)
        row["comfort_violation_hours"] = 118.0
        rows.append(row)

    if include_broken:
        broken = dict(rows[0])
        broken["case_id"] = "case_yarim"
        broken["site_energy_gj"] = 0.0
        rows.append(broken)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


class EncodingTests(unittest.TestCase):
    def test_categorical_variable_is_one_hot_not_ordinal(self) -> None:
        # Cam tipleri arasinda dogal bir siralama yoktur; tek sutuna
        # sikistirmak modele var olmayan bir sira ogretirdi.
        vector = encode_row(baseline_parameters())
        choices = BY_KEY["window_construction"].choices
        tail = vector[len(CONTINUOUS_KEYS) :]
        self.assertEqual(len(tail), len(choices))
        self.assertEqual(sum(tail), 1.0)
        self.assertEqual(tail[choices.index("penc_std_4mm")], 1.0)

    def test_feature_names_match_vector_length(self) -> None:
        self.assertEqual(len(feature_names()), len(encode_row(baseline_parameters())))

    def test_every_parameter_is_represented(self) -> None:
        self.assertEqual(
            len(CONTINUOUS_KEYS) + len(CATEGORICAL_KEYS), len(PARAMETERS)
        )


class DatasetTests(unittest.TestCase):
    def test_dataset_loads_and_shapes_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = _write_results(Path(temp) / "results.csv", count=40)
            dataset = load_dataset(path)
        self.assertEqual(len(dataset), 41)  # referans + 40 ornek
        self.assertEqual(dataset.n_features, len(feature_names()))
        for name in TARGETS:
            self.assertEqual(len(dataset.target(name)), len(dataset))

    def test_zero_energy_rows_are_excluded(self) -> None:
        # Yarida kesilmis bir kosu tabloya sizarsa modeli bozar.
        with tempfile.TemporaryDirectory() as temp:
            path = _write_results(Path(temp) / "results.csv", count=20, include_broken=True)
            dataset = load_dataset(path)
        self.assertNotIn("case_yarim", dataset.case_ids)
        self.assertTrue(all(value > 0 for value in dataset.target("site_energy_gj")))

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_dataset(Path("olmayan_dosya.csv"))

    def test_unknown_target_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = _write_results(Path(temp) / "results.csv", count=20)
            dataset = load_dataset(path)
        with self.assertRaises(KeyError):
            dataset.target("olmayan_hedef")

    def test_minimum_rows_scales_with_feature_count(self) -> None:
        self.assertEqual(minimum_rows_for(17), 51)


class MetricTests(unittest.TestCase):
    def test_perfect_prediction_gives_zero_error(self) -> None:
        actual = np.array([100.0, 200.0, 300.0])
        self.assertAlmostEqual(cvrmse(actual, actual), 0.0)
        self.assertAlmostEqual(nmbe(actual, actual), 0.0)
        self.assertAlmostEqual(r_squared(actual, actual), 1.0)

    def test_cvrmse_is_scale_independent(self) -> None:
        actual = np.array([100.0, 200.0])
        predicted = np.array([110.0, 220.0])
        scaled_actual = actual * 1000
        scaled_predicted = predicted * 1000
        self.assertAlmostEqual(
            cvrmse(actual, predicted), cvrmse(scaled_actual, scaled_predicted), places=9
        )

    def test_nmbe_sign_shows_direction_of_bias(self) -> None:
        actual = np.array([100.0, 100.0])
        self.assertGreater(nmbe(actual, np.array([90.0, 90.0])), 0)
        self.assertLess(nmbe(actual, np.array([110.0, 110.0])), 0)

    def test_gate_threshold_is_ten_percent(self) -> None:
        actual = np.array([100.0, 100.0, 100.0])
        passing = score("m", "t", actual, np.array([105.0, 100.0, 95.0]))
        failing = score("m", "t", actual, np.array([150.0, 100.0, 50.0]))
        self.assertTrue(passing.meets_target)
        self.assertFalse(failing.meets_target)


class TrainingTests(unittest.TestCase):
    def test_cross_validation_returns_one_prediction_per_sample(self) -> None:
        features = np.random.default_rng(3).random((30, 5))
        target = features[:, 0] * 4 + features[:, 1]
        predicted = cross_validate(CANDIDATES["polinom"], features, target, folds=5)
        self.assertEqual(predicted.shape, target.shape)

    def test_cross_validation_rejects_too_few_samples(self) -> None:
        features = np.random.default_rng(3).random((3, 5))
        with self.assertRaises(ValueError):
            cross_validate(CANDIDATES["polinom"], features, features[:, 0], folds=5)

    def test_every_candidate_learns_a_known_linear_function(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = _write_results(Path(temp) / "results.csv", count=80)
            dataset = load_dataset(path)
        scores = compare(
            dataset.features,
            {"site_energy_gj": dataset.target("site_energy_gj")},
            folds=5,
        )
        self.assertEqual({item.model for item in scores}, set(CANDIDATES))
        for item in scores:
            self.assertLess(item.cvrmse, 20.0, f"{item.model} beklenenden kotu")

    def test_best_per_target_picks_lowest_cvrmse(self) -> None:
        actual = np.array([100.0, 100.0])
        good = score("kriging", "site_energy_gj", actual, np.array([101.0, 99.0]))
        bad = score("polinom", "site_energy_gj", actual, np.array([130.0, 70.0]))
        self.assertEqual(best_per_target([bad, good])["site_energy_gj"].model, "kriging")


if __name__ == "__main__":
    unittest.main()
