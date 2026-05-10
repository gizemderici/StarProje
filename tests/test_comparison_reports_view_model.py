import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from view_models.comparison_reports import (
    EXPECTED_COMPARISON_METRIC_IDS,
    build_run_to_run_trend_model,
    read_comparison_report_entries,
    summarize_metric_availability,
)


class ComparisonReportViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = self.temp_root / f"comparison_reports_{uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_summarize_metric_availability_detects_missing_and_null_metrics(self) -> None:
        summary = summarize_metric_availability(
            [
                {"metric_id": "annual_heating", "base_value": 100.0, "scenario_value": 80.0},
                {"metric_id": "annual_cooling", "base_value": None, "scenario_value": None},
            ]
        )

        self.assertIn("annual_heating", summary["available_metric_ids"])
        self.assertIn("annual_cooling", summary["null_metric_ids"])
        self.assertIn("total_energy", summary["missing_metric_ids"])
        self.assertTrue(summary["has_any_metric_data"])

    def test_read_comparison_report_entries_adds_metric_summary(self) -> None:
        comparison_dir = self.root / "scenario_runs" / "demo" / "comparison"
        comparison_dir.mkdir(parents=True, exist_ok=True)
        report_path = comparison_dir / "demo__comparison.json"
        report_path.write_text(
            json.dumps(
                {
                    "metrics": [
                        {"metric_id": "annual_heating", "base_value": 120.0, "scenario_value": 100.0},
                        {"metric_id": "annual_cooling", "base_value": None, "scenario_value": None},
                    ],
                    "metric_source": {
                        "status": "unavailable",
                        "message": "Bu rapor yalnizca CSV farklarini iceriyor.",
                    },
                    "comparison_model": {"summary": {"most_critical": "annual_heating"}},
                }
            ),
            encoding="utf-8",
        )

        entries = read_comparison_report_entries(self.root / "scenario_runs")

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["scenario_name"], "demo")
        self.assertIn("annual_heating", entry["available_metric_ids"])
        self.assertIn("annual_cooling", entry["null_metric_ids"])
        self.assertIn("total_energy", entry["missing_metric_ids"])
        self.assertEqual(entry["metric_source_status"], "unavailable")
        self.assertIn("CSV farklarini", entry["metric_source_message"])
        self.assertEqual(
            set(EXPECTED_COMPARISON_METRIC_IDS) - {"annual_heating", "annual_cooling"},
            set(entry["missing_metric_ids"]),
        )

    def test_build_run_to_run_trend_model_summarizes_improvement_and_worsening(self) -> None:
        trend = build_run_to_run_trend_model(
            [
                {
                    "scenario_name": "s1",
                    "report_mtime": 1,
                    "metrics": [
                        {
                            "metric_id": "total_energy",
                            "label": "Total Energy",
                            "unit": "kWh",
                            "scenario_value": 1200,
                        }
                    ],
                },
                {
                    "scenario_name": "s2",
                    "report_mtime": 2,
                    "metrics": [
                        {
                            "metric_id": "total_energy",
                            "label": "Total Energy",
                            "unit": "kWh",
                            "scenario_value": 1000,
                        }
                    ],
                },
                {
                    "scenario_name": "s3",
                    "report_mtime": 3,
                    "metrics": [
                        {
                            "metric_id": "total_energy",
                            "label": "Total Energy",
                            "unit": "kWh",
                            "scenario_value": 1100,
                        }
                    ],
                },
            ],
            metric_id="total_energy",
        )

        self.assertTrue(trend["has_data"])
        self.assertEqual(trend["labels"], ["s1", "s2", "s3"])
        self.assertEqual(trend["values"], [1200.0, 1000.0, 1100.0])
        self.assertEqual(trend["deltas"], [None, -200.0, 100.0])
        self.assertEqual(trend["improvement_count"], 1)
        self.assertEqual(trend["worsening_count"], 1)


if __name__ == "__main__":
    unittest.main()
