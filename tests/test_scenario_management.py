import unittest

from scenario_management import (
    build_copied_scenario_definition,
    build_multi_scenario_chart_model,
    build_multi_scenario_commentary,
    build_multi_scenario_comparison_rows,
    build_multi_scenario_decision_commentary,
    build_multi_scenario_score_rows,
    build_renamed_scenario_definition,
    build_scenario_diff_rows,
    build_version_history_entries,
    filter_multi_scenario_comparison_rows,
    filter_scenario_diff_rows,
)


def _sample_scenario(name: str = "demo") -> dict[str, object]:
    return {
        "scenario_name": name,
        "description": "demo scenario",
        "input": "csv_output/materials.csv",
        "output": f"simulation_outputs/{name}/{name}__materials.csv",
        "log_output": f"simulation_outputs/{name}/{name}__changes.json",
        "changes": [
            {
                "label": "Material Thickness",
                "record_label": "tugla",
            },
            {
                "label": "Material Conductivity",
                "record_label": "beton",
            },
        ],
        "operations": [{"name": "set_material_thickness"}, {"name": "set_material_conductivity"}],
    }


class ScenarioManagementTests(unittest.TestCase):
    def test_copy_preserves_version_group_and_updates_name_and_paths(self) -> None:
        copied = build_copied_scenario_definition(
            _sample_scenario("base_case"),
            "scenario_definitions/generated/base_case.json",
            "option b",
            timestamp="2026-04-23T10:00:00+00:00",
        )

        self.assertEqual(copied["scenario_name"], "option_b")
        self.assertIn("simulation_outputs/option_b/", str(copied["output"]))
        self.assertEqual(copied["management"]["version_group"], "base_case")
        self.assertEqual(copied["management"]["version_index"], 2)
        history = copied["management"]["history"]
        self.assertEqual(history[-1]["event"], "copied")
        self.assertEqual(history[-1]["source_scenario_name"], "base_case")

    def test_rename_appends_history_and_rewrites_paths(self) -> None:
        renamed = build_renamed_scenario_definition(
            _sample_scenario("draft_one"),
            "scenario_definitions/generated/draft_one.json",
            "draft final",
            timestamp="2026-04-23T10:00:00+00:00",
        )

        self.assertEqual(renamed["scenario_name"], "draft_final")
        self.assertIn("simulation_outputs/draft_final/", str(renamed["output"]))
        self.assertEqual(renamed["management"]["version_group"], "draft_one")
        self.assertEqual(renamed["management"]["history"][-1]["event"], "renamed")
        self.assertEqual(
            renamed["management"]["history"][-1]["previous_scenario_name"],
            "draft_one",
        )

    def test_version_history_groups_related_versions(self) -> None:
        entries = [
            {
                "path": "scenario_definitions/generated/base_case.json",
                "scenario_name": "base_case",
                "management": {"version_group": "base_case", "version_index": 1, "updated_at": "2026-04-22"},
                "mtime_label": "2026-04-22",
            },
            {
                "path": "scenario_definitions/generated/option_a.json",
                "scenario_name": "option_a",
                "management": {"version_group": "base_case", "version_index": 2, "updated_at": "2026-04-23"},
                "mtime_label": "2026-04-23",
            },
            {
                "path": "scenario_definitions/other.json",
                "scenario_name": "other",
                "management": {"version_group": "other", "version_index": 1, "updated_at": "2026-04-20"},
                "mtime_label": "2026-04-20",
            },
        ]

        history = build_version_history_entries(entries, "scenario_definitions/generated/option_a.json")

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["scenario_name"], "option_a")
        self.assertTrue(history[0]["is_selected"])
        self.assertEqual(history[1]["scenario_name"], "base_case")

    def test_scenario_diff_rows_surface_changed_labels_and_records(self) -> None:
        left = _sample_scenario("left_case")
        right = _sample_scenario("right_case")
        right["changes"] = [
            {"label": "Material Thickness", "record_label": "tugla"},
            {"label": "Material Density", "record_label": "hafif_beton"},
        ]
        right["operations"] = [{"name": "set_material_thickness"}]

        diff_rows = build_scenario_diff_rows(left, right)
        by_label = {row["label"]: row for row in diff_rows}

        self.assertEqual(by_label["Degisiklik Sayisi"]["status"], "Ayni")
        self.assertEqual(by_label["Islem Sayisi"]["status"], "Farkli")
        self.assertIn("Material Conductivity", by_label["Sadece Solda"]["left"])
        self.assertIn("Material Density", by_label["Sadece Sagda"]["right"])

    def test_filter_scenario_diff_rows_supports_same_and_changed_filters(self) -> None:
        diff_rows = [
            {"label": "Veri Seti", "left": "a", "right": "a", "status": "Ayni"},
            {"label": "Islem Sayisi", "left": "2", "right": "1", "status": "Farkli"},
        ]

        self.assertEqual(len(filter_scenario_diff_rows(diff_rows, "Tum Satirlar")), 2)
        self.assertEqual(len(filter_scenario_diff_rows(diff_rows, "Sadece Aynilar")), 1)
        self.assertEqual(len(filter_scenario_diff_rows(diff_rows, "Sadece Farklilar")), 1)

    def test_build_multi_scenario_comparison_rows_includes_third_and_parameter_rows(self) -> None:
        left = _sample_scenario("left_case")
        right = _sample_scenario("right_case")
        third = _sample_scenario("third_case")
        third["changes"] = [{"label": "Material Density", "record_label": "hafif_beton"}]

        rows = build_multi_scenario_comparison_rows(left, right, third)
        labels = {row["label"]: row for row in rows}

        self.assertIn("Parametre: Material Density", labels)
        self.assertEqual(labels["Parametre: Material Density"]["third"], "Var")
        self.assertEqual(labels["Parametre: Material Density"]["status"], "Farkli")

    def test_filter_multi_scenario_rows_supports_summary_mode(self) -> None:
        rows = [
            {"label": "Veri Seti", "left": "a", "right": "a", "third": "a", "status": "Ayni"},
            {"label": "Parametre: Density", "left": "Var", "right": "-", "third": "-", "status": "Farkli"},
            {"label": "Parametre: Thickness", "left": "Var", "right": "Var", "third": "-", "status": "Ayni"},
        ]

        summary_rows = filter_multi_scenario_comparison_rows(
            rows,
            selected_filter="Tum Satirlar",
            comparison_mode="Ozet Fark Modu",
        )

        self.assertEqual(len(summary_rows), 1)
        self.assertEqual(summary_rows[0]["label"], "Parametre: Density")

    def test_build_multi_scenario_commentary_describes_lightest_and_broadest(self) -> None:
        left = _sample_scenario("light")
        right = _sample_scenario("broad")
        right["changes"] = right["changes"] + [{"label": "Material Density", "record_label": "beton"}]
        right["operations"] = right["operations"] + [{"name": "set_material_density"}]

        commentary = build_multi_scenario_commentary(
            [("light", left), ("broad", right)]
        )

        self.assertIn("En kontrollu secenek", commentary)
        self.assertIn("En kapsamli senaryo", commentary)

    def test_build_multi_scenario_chart_model_returns_series(self) -> None:
        chart_model = build_multi_scenario_chart_model(
            [("left", _sample_scenario("left")), ("right", _sample_scenario("right"))]
        )

        self.assertEqual(chart_model["labels"], ["left", "right"])
        self.assertEqual(chart_model["change_counts"], [2, 2])
        self.assertTrue(chart_model["has_data"])

    def test_build_multi_scenario_decision_commentary_uses_reports_when_available(self) -> None:
        reports = {
            "left": {
                "metrics": [
                    {"metric_id": "total_energy", "scenario_value": "120"},
                    {"metric_id": "annual_cost", "scenario_value": "2500"},
                ],
                "comparison_model": {"summary": {"most_critical": {"severity_level": "high"}}},
            },
            "right": {
                "metrics": [
                    {"metric_id": "total_energy", "scenario_value": "100"},
                    {"metric_id": "annual_cost", "scenario_value": "2100"},
                ],
                "comparison_model": {"summary": {"most_critical": {"severity_level": "medium"}}},
            },
        }

        commentary = build_multi_scenario_decision_commentary(
            [("left", _sample_scenario("left")), ("right", _sample_scenario("right"))],
            reports_by_name=reports,
        )

        self.assertIn("Enerji tarafinda en iyi gorunen senaryo: **right**", commentary)
        self.assertIn("Maliyet tarafinda en iyi gorunen senaryo: **right**", commentary)
        self.assertIn("Risk acisindan daha guvenli duran secenek: **right**", commentary)

    def test_build_multi_scenario_score_rows_returns_ranked_scores(self) -> None:
        reports = {
            "left": {
                "metrics": [
                    {"metric_id": "total_energy", "scenario_value": "120"},
                    {"metric_id": "annual_cost", "scenario_value": "2500"},
                ],
                "comparison_model": {"summary": {"most_critical": {"severity_level": "high"}}},
            },
            "right": {
                "metrics": [
                    {"metric_id": "total_energy", "scenario_value": "100"},
                    {"metric_id": "annual_cost", "scenario_value": "2100"},
                ],
                "comparison_model": {"summary": {"most_critical": {"severity_level": "medium"}}},
            },
        }

        score_rows = build_multi_scenario_score_rows(
            [("left", _sample_scenario("left")), ("right", _sample_scenario("right"))],
            reports_by_name=reports,
        )

        self.assertEqual(score_rows[0]["scenario_name"], "right")
        self.assertIsNotNone(score_rows[0]["total_score"])
        self.assertGreater(score_rows[0]["total_score"], score_rows[1]["total_score"])


if __name__ == "__main__":
    unittest.main()
