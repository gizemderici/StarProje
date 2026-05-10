import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analyze_csv_dependencies import CsvRepository
from dependency_analysis_service import (
    build_dependency_service_model,
    build_dependency_service_model_for_row,
)
from nicegui_csv_viewer import (
    build_combined_impact_summary,
    build_cost_comparison_chart_model,
    build_energy_performance_chart_model,
    build_layer_impact_chart_model,
    build_monthly_energy_chart_model,
    build_parameter_change_chart_model,
    build_zone_temperature_chart_model,
    filter_parameter_definitions,
    parse_selected_parameter_state,
    serialize_selected_parameter_state,
    validate_parameter_new_value,
)
from parameter_catalog import get_parameter_definition, list_parameter_definitions
from scenario_builder import SelectedParameterChange, build_scenario_from_selected_changes
from simulation_runner import run_comparative_simulation


DATASET_CONTENT = {
    "materials.csv": [
        ["name", "type", "thickness_m", "conductivity_w_per_mk", "thermal_resistance_m2k_per_w"],
        ["beton", "OS_Material", "0.2", "1.75", ""],
        ["tugla", "OS_Material", "0.19", "0.5", ""],
    ],
    "construction_layers.csv": [
        ["construction_name", "construction_type", "layer_index", "name", "type", "thickness_m", "conductivity_w_per_mk"],
        ["disduvar", "OS_Construction", "1", "beton", "OS_Material", "0.2", "1.75"],
        ["disduvar", "OS_Construction", "2", "tugla", "OS_Material", "0.19", "0.5"],
    ],
    "constructions.csv": [
        ["name", "type", "layer_count"],
        ["disduvar", "OS_Construction", "2"],
    ],
    "walls.csv": [
        ["name", "surface_type", "element_class", "gross_area_m2", "outside_boundary_condition", "azimuth_rad", "space_name", "construction_name"],
        ["Wall 1", "Wall", "dis_duvar", "10", "Outdoors", "0", "Salon", "disduvar"],
    ],
    "floors.csv": [
        ["name", "surface_type", "element_class", "gross_area_m2", "outside_boundary_condition", "azimuth_rad", "space_name", "construction_name"],
        ["Floor 1", "Floor", "zemin_dosemesi", "12", "Ground", "0", "Salon", "disduvar"],
    ],
    "roofs.csv": [
        ["name", "surface_type", "element_class", "gross_area_m2", "outside_boundary_condition", "azimuth_rad", "space_name", "construction_name"],
        ["Roof 1", "RoofCeiling", "cati", "12", "Outdoors", "0", "Salon", "disduvar"],
    ],
    "windows.csv": [
        ["name", "sub_surface_type", "element_class", "gross_area_m2", "host_surface_name", "construction_name"],
        ["Window 1", "FixedWindow", "dis_pencere", "2", "Wall 1", "window_const"],
    ],
    "openings.csv": [
        ["name", "sub_surface_type", "element_class", "gross_area_m2", "host_surface_name", "construction_name"],
        ["Opening 1", "Door", "dis_kapi", "1", "Wall 1", "door_const"],
    ],
    "spaces.csv": [
        ["name", "floor_area_m2", "volume_m3", "thermal_zone_name"],
        ["Salon", "20", "60", "TZ_1"],
    ],
    "zones.csv": [
        ["name", "space_count", "space_names", "floor_area_m2", "volume_m3"],
        ["TZ_1", "1", "Salon", "20", "60"],
    ],
}


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)


def write_dataset(root: Path) -> None:
    for file_name, rows in DATASET_CONTENT.items():
        write_csv(root / file_name, rows)


def read_value_by_name(csv_path: Path, name: str, field_name: str) -> str:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if str(row.get("name", "")).strip() == name:
                return str(row.get(field_name, "")).strip()
    return ""


class Backlog11SingleParameterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))
        write_dataset(self.root)
        self.base_model_path = self.root / "building.osm"
        self.base_model_path.write_text("BASE MODEL CONTENT", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_backlog_11_1_single_thickness_change_end_to_end(self) -> None:
        scenario = {
            "scenario_name": "single_thickness",
            "input": str(self.root / "materials.csv"),
            "output": str(self.root / "output.csv"),
            "log_output": str(self.root / "changes.json"),
            "operations": [
                {
                    "name": "set_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                }
            ],
        }

        result = run_comparative_simulation(
            scenario=scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        new_value = read_value_by_name(result.scenario_output, "beton", "thickness_m")
        self.assertEqual(new_value, "0.25")

        dependency_model = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="thickness_m",
        )
        self.assertTrue(dependency_model["affected_layers"])

        repo = CsvRepository(self.root)
        layer_row = repo.find_rows("construction_layers.csv", "name", "beton")[0]
        layer_model = build_dependency_service_model_for_row(
            repo=repo,
            dataset_name="construction_layers.csv",
            row=layer_row,
            changed_column="thickness_m",
        )
        changed_layers = [
            item for item in layer_model["affected_layers"] if item.get("badge") == "Degisen Layer"
        ]
        self.assertTrue(changed_layers)
        self.assertIn("disduvar", changed_layers[0]["construction_names"])

        comparison = json.loads(result.comparison_report.read_text(encoding="utf-8"))
        metric_ids = {row["metric_id"] for row in comparison.get("metrics", [])}
        self.assertIn("annual_heating", metric_ids)
        self.assertIn("annual_cooling", metric_ids)


class Backlog11DualParameterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))
        write_dataset(self.root)
        self.base_model_path = self.root / "building.osm"
        self.base_model_path.write_text("BASE MODEL CONTENT", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_backlog_11_2_thickness_and_conductivity_change(self) -> None:
        scenario = {
            "scenario_name": "dual_material_change",
            "input": str(self.root / "materials.csv"),
            "output": str(self.root / "output.csv"),
            "log_output": str(self.root / "changes.json"),
            "operations": [
                {
                    "name": "set_thickness",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"thickness_m": "0.25"},
                },
                {
                    "name": "set_conductivity",
                    "match": {"column": "name", "value": "beton"},
                    "updates": {"conductivity_w_per_mk": "1.25"},
                },
            ],
        }

        result = run_comparative_simulation(
            scenario=scenario,
            base_model_path=self.base_model_path,
            runs_root=self.root / "scenario_runs",
        )

        comparison = json.loads(result.comparison_report.read_text(encoding="utf-8"))
        changed_columns = {item.get("column") for item in comparison.get("changed_cells", [])}
        self.assertIn("thickness_m", changed_columns)
        self.assertIn("conductivity_w_per_mk", changed_columns)

        model_thickness = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="thickness_m",
        )
        model_conductivity = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="conductivity_w_per_mk",
        )

        layer_impact_rows = []
        for changed_field, model in [
            ("thickness_m", model_thickness),
            ("conductivity_w_per_mk", model_conductivity),
        ]:
            for item in model.get("affected_layers", []):
                layer_impact_rows.append(
                    {
                        "construction_names": ", ".join(item.get("construction_names", [])) or "-",
                        "changed_field": changed_field,
                    }
                )

        combined_summary = build_combined_impact_summary(
            {
                "layer_impact_rows": layer_impact_rows,
                "surface_impact_rows": [],
            }
        )
        self.assertGreaterEqual(int(combined_summary["changed_field_count"]), 2)
        self.assertGreaterEqual(int(combined_summary["overlapping_group_count"]), 1)


class Backlog11EdgeValueTests(unittest.TestCase):
    def test_backlog_11_3_edge_values_produce_validation_warnings(self) -> None:
        thickness = get_parameter_definition("material_thickness")
        conductivity = get_parameter_definition("material_conductivity")
        self.assertIsNotNone(thickness)
        self.assertIsNotNone(conductivity)
        assert thickness is not None
        assert conductivity is not None

        too_small = validate_parameter_new_value(thickness, current_value="0.2", new_value="0.0001")
        too_large = validate_parameter_new_value(conductivity, current_value="1.0", new_value="99")
        negative = validate_parameter_new_value(thickness, current_value="0.2", new_value="-0.2")
        invalid = validate_parameter_new_value(thickness, current_value="0.2", new_value="abc")

        self.assertTrue(any("minimum" in warning for warning in too_small))
        self.assertTrue(any("maksimum" in warning for warning in too_large))
        self.assertTrue(any("Negatif" in warning for warning in negative))
        self.assertTrue(any("Sayisal" in warning for warning in invalid))

    def test_backlog_11_3_invalid_value_blocks_scenario_build(self) -> None:
        parameter = get_parameter_definition("material_thickness")
        self.assertIsNotNone(parameter)
        assert parameter is not None

        selected_changes = [
            SelectedParameterChange(
                parameter=parameter,
                current_value="0.2",
                new_value="invalid",
                record_label="beton",
                record_choice={
                    "match_column": "name",
                    "match_value": "beton",
                    "extra_matches": {},
                },
            )
        ]

        draft, _, errors = build_scenario_from_selected_changes(selected_changes)

        self.assertIsNone(draft)
        self.assertTrue(errors)


class Backlog11UiSmokeTests(unittest.TestCase):
    def test_backlog_11_4_ui_view_models_smoke(self) -> None:
        parameters = list_parameter_definitions()

        filtered = filter_parameter_definitions(
            parameters,
            category="Materials",
            query="thickness",
        )
        self.assertTrue(filtered)
        self.assertTrue(any(item.field_name == "thickness_m" for item in filtered))

        serialized = serialize_selected_parameter_state(
            {
                "material_thickness": {
                    "record_label": "beton",
                    "new_value": "0.25",
                }
            }
        )
        parsed = parse_selected_parameter_state(serialized)
        self.assertIn("material_thickness", parsed)

        parameter_change_chart = build_parameter_change_chart_model(
            {
                "material_thickness": {
                    "definition": filtered[0],
                    "current_value": "0.2",
                    "new_value": "0.25",
                }
            }
        )
        self.assertTrue(parameter_change_chart["has_data"])

        energy_chart = build_energy_performance_chart_model(
            [
                {"metric_id": "annual_heating", "unit": "kWh", "base_value": 1000, "scenario_value": 900},
                {"metric_id": "annual_cooling", "unit": "kWh", "base_value": 800, "scenario_value": 760},
                {"metric_id": "total_energy", "unit": "kWh", "base_value": 1800, "scenario_value": 1660},
            ]
        )
        self.assertTrue(energy_chart["has_data"])

        monthly_chart = build_monthly_energy_chart_model(
            [
                {
                    "metric_id": "monthly_heating_cooling",
                    "base_value": '{"heating": [100, 90], "cooling": [20, 25]}',
                    "scenario_value": '{"heating": [95, 85], "cooling": [18, 23]}',
                }
            ]
        )
        self.assertTrue(monthly_chart["has_data"])

        zone_chart = build_zone_temperature_chart_model(
            [
                {
                    "metric_id": "zone_temperatures",
                    "base_value": '{"zones": {"Zone A": {"timestamps": ["t1", "t2"], "values": [21, 22]}}}',
                    "scenario_value": '{"zones": {"Zone A": {"timestamps": ["t1", "t2"], "values": [20.5, 21.5]}}}',
                }
            ]
        )
        self.assertTrue(zone_chart["has_data"])

        layer_chart = build_layer_impact_chart_model(
            [
                {"construction_names": "disduvar", "badge": "Degisen Layer"},
                {"construction_names": "disduvar", "badge": "Etkilenen Layer"},
            ]
        )
        self.assertTrue(layer_chart["has_data"])

        cost_chart = build_cost_comparison_chart_model(
            {
                "base_cost": 1200,
                "scenario_cost": 900,
            }
        )
        self.assertTrue(cost_chart["has_data"])


if __name__ == "__main__":
    unittest.main()
