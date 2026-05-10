import unittest

from apply_scenario_definition import apply_scenario_to_rows
from parameter_catalog import get_parameter_definition
from scenario_builder import (
    SelectedParameterChange,
    build_apply_scenario_definition_payload,
    build_scenario_from_selected_changes,
    generate_scenario_name,
    sanitize_scenario_name,
)


class ScenarioBuilderTests(unittest.TestCase):
    def test_generate_scenario_name_uses_dataset_and_parameter_ids(self) -> None:
        result = generate_scenario_name(
            "materials.csv",
            ["material_thickness", "material_conductivity"],
        )
        self.assertEqual(result, "materials_material_thickness_material_conductivity")

    def test_sanitize_scenario_name_normalizes_text(self) -> None:
        self.assertEqual(
            sanitize_scenario_name(" Facade Upgrade Option A "),
            "Facade_Upgrade_Option_A",
        )

    def test_builder_creates_change_list_and_operations(self) -> None:
        parameter = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        selected_changes = [
            SelectedParameterChange(
                parameter=parameter,
                current_value="0.50",
                new_value="0.35",
                record_label="tugla",
                record_choice={
                    "match_column": "name",
                    "match_value": "tugla",
                    "extra_matches": {},
                },
            )
        ]

        draft, change_list, errors = build_scenario_from_selected_changes(
            selected_changes,
            scenario_name="materials_upgrade",
            description="Material conductivity update",
        )

        self.assertEqual(errors, [])
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft["scenario_name"], "materials_upgrade")
        self.assertEqual(draft["description"], "Material conductivity update")
        self.assertEqual(draft["input"], "csv_output/materials.csv")
        self.assertEqual(len(change_list), 1)
        self.assertEqual(change_list[0]["old_value"], "0.50")
        self.assertEqual(change_list[0]["new_value"], "0.35")
        self.assertEqual(change_list[0]["record_label"], "tugla")
        self.assertEqual(len(draft["operations"]), 1)
        self.assertEqual(draft["operations"][0]["match"]["column"], "name")
        self.assertEqual(draft["operations"][0]["match"]["value"], "tugla")
        self.assertEqual(
            draft["operations"][0]["updates"]["conductivity_w_per_mk"],
            "0.35",
        )

    def test_builder_rejects_mixed_datasets(self) -> None:
        material = get_parameter_definition("material_conductivity")
        wall = get_parameter_definition("wall_construction_name")
        self.assertIsNotNone(material)
        self.assertIsNotNone(wall)
        assert material is not None
        assert wall is not None

        selected_changes = [
            SelectedParameterChange(
                parameter=material,
                current_value="0.50",
                new_value="0.35",
                record_label="tugla",
                record_choice={"match_column": "name", "match_value": "tugla", "extra_matches": {}},
            ),
            SelectedParameterChange(
                parameter=wall,
                current_value="disduvar",
                new_value="high_perf_wall",
                record_label="Face 50",
                record_choice={"match_column": "name", "match_value": "Face 50", "extra_matches": {}},
            ),
        ]

        draft, change_list, errors = build_scenario_from_selected_changes(selected_changes)

        self.assertIsNone(draft)
        self.assertEqual(change_list, [])
        self.assertEqual(len(errors), 1)

    def test_builder_rejects_no_op_change(self) -> None:
        parameter = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        selected_changes = [
            SelectedParameterChange(
                parameter=parameter,
                current_value="0.50",
                new_value="0.50",
                record_label="tugla",
                record_choice={
                    "match_column": "name",
                    "match_value": "tugla",
                    "extra_matches": {},
                },
            )
        ]

        draft, change_list, errors = build_scenario_from_selected_changes(selected_changes)

        self.assertIsNone(draft)
        self.assertEqual(change_list, [])
        self.assertTrue(any("mevcut deger ile ayni" in error for error in errors))

    def test_builder_rejects_duplicate_target_updates(self) -> None:
        parameter = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        selected_changes = [
            SelectedParameterChange(
                parameter=parameter,
                current_value="0.50",
                new_value="0.35",
                record_label="tugla",
                record_choice={
                    "match_column": "name",
                    "match_value": "tugla",
                    "extra_matches": {},
                },
            ),
            SelectedParameterChange(
                parameter=parameter,
                current_value="0.50",
                new_value="0.30",
                record_label="tugla",
                record_choice={
                    "match_column": "name",
                    "match_value": "tugla",
                    "extra_matches": {},
                },
            ),
        ]

        draft, change_list, errors = build_scenario_from_selected_changes(selected_changes)

        self.assertIsNone(draft)
        self.assertEqual(len(change_list), 1)
        self.assertTrue(any("birden fazla kez secildi" in error for error in errors))

    def test_builder_rejects_overly_long_scenario_name(self) -> None:
        parameter = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        selected_changes = [
            SelectedParameterChange(
                parameter=parameter,
                current_value="0.50",
                new_value="0.35",
                record_label="tugla",
                record_choice={
                    "match_column": "name",
                    "match_value": "tugla",
                    "extra_matches": {},
                },
            )
        ]

        draft, change_list, errors = build_scenario_from_selected_changes(
            selected_changes,
            scenario_name="a" * 120,
        )

        self.assertIsNone(draft)
        self.assertEqual(len(change_list), 1)
        self.assertTrue(any("Senaryo adi cok uzun" in error for error in errors))

    def test_builder_output_can_be_adapted_to_apply_scenario_definition_format(self) -> None:
        import csv
        import shutil
        from pathlib import Path
        from uuid import uuid4

        parameter = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        root = Path(__file__).resolve().parents[1] / ".pytest_tmp" / f"scenario_builder_{uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        try:
            input_path = root / "materials.csv"
            with input_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerows(
                    [
                        ["name", "type", "thickness_m", "conductivity_w_per_mk", "thermal_resistance_m2k_per_w"],
                        ["tugla", "OS_Material", "0.19", "0.50", ""],
                        ["beton", "OS_Material", "0.20", "1.75", ""],
                    ]
                )

            selected_changes = [
                SelectedParameterChange(
                    parameter=parameter,
                    current_value="0.50",
                    new_value="0.35",
                    record_label="tugla",
                    record_choice={
                        "match_column": "name",
                        "match_value": "tugla",
                        "extra_matches": {},
                    },
                )
            ]

            draft, _, errors = build_scenario_from_selected_changes(
                selected_changes,
                scenario_name="materials_upgrade",
                description="Compatibility test",
            )
            self.assertEqual(errors, [])
            self.assertIsNotNone(draft)
            assert draft is not None
            draft["input"] = str(input_path)
            draft["output"] = str(root / "materials_updated.csv")
            draft["log_output"] = str(root / "materials_updated_changes.json")

            compatible = build_apply_scenario_definition_payload(draft)
            rows, _, change_logs, _ = apply_scenario_to_rows(compatible)

            self.assertEqual(len(change_logs), 1)
            updated_row = next(row for row in rows if row["name"] == "tugla")
            self.assertEqual(updated_row["conductivity_w_per_mk"], "0.35")
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
