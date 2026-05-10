import shutil
import tempfile
import unittest
import csv
from pathlib import Path

from analyze_csv_dependencies import CsvRepository
from dependency_analysis_service import (
    analyze_specific_row,
    build_dependency_service_model,
    build_dependency_service_model_for_row,
    get_affected_layer_items,
    get_affected_surface_items,
    get_direct_affected_tables,
    get_indirect_affected_items,
    get_layer_relationships,
)


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


def write_dataset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for file_name, rows in DATASET_CONTENT.items():
        with (root / file_name).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(rows)


class DependencyAnalysisServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))
        write_dataset(self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_service_model_returns_direct_indirect_and_layer_views(self) -> None:
        model = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="conductivity_w_per_mk",
        )

        direct_datasets = {item["dataset"] for item in model["direct_affected_tables"]}
        indirect_datasets = {item["dataset"] for item in model["indirect_affected_items"]}
        layer_targets = {item["target_dataset"] for item in model["layer_relationships"]}

        self.assertIn("construction_layers.csv", direct_datasets)
        self.assertIn("walls.csv", indirect_datasets)
        self.assertIn("construction_layers.csv", layer_targets)

    def test_direct_tables_aggregate_rows_by_dataset(self) -> None:
        model = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="conductivity_w_per_mk",
        )

        construction_layer_item = next(
            item
            for item in model["direct_affected_tables"]
            if item["dataset"] == "construction_layers.csv"
        )
        self.assertGreaterEqual(construction_layer_item["affected_row_count"], 1)
        self.assertTrue(construction_layer_item["reasons"])

    def test_analyze_specific_row_adds_matched_row_metadata(self) -> None:
        repo = CsvRepository(self.root)
        row = repo.find_rows("construction_layers.csv", "name", "beton")[0]

        report = analyze_specific_row(
            repo,
            "construction_layers.csv",
            row,
            "thickness_m",
        )

        self.assertIn("matched_row", report)
        self.assertIn("construction_name=disduvar", report["matched_row"]["row_key"])
        self.assertEqual(report["matched_row"]["preview"]["thickness_m"], "0.2")

    def test_view_helpers_can_be_used_independently(self) -> None:
        model = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="conductivity_w_per_mk",
        )
        raw_report = model["raw_report"]

        self.assertTrue(get_direct_affected_tables(raw_report))
        self.assertTrue(get_indirect_affected_items(raw_report))
        self.assertTrue(get_layer_relationships(raw_report))
        self.assertTrue(get_affected_layer_items(raw_report))
        self.assertTrue(get_affected_surface_items(raw_report))

    def test_service_model_for_row_uses_exact_selected_row(self) -> None:
        repo = CsvRepository(self.root)
        row = repo.find_rows("construction_layers.csv", "name", "beton")[0]

        model = build_dependency_service_model_for_row(
            repo=repo,
            dataset_name="construction_layers.csv",
            row=row,
            changed_column="thickness_m",
        )

        self.assertTrue(model["direct_affected_tables"])
        self.assertTrue(model["layer_relationships"])
        self.assertTrue(model["affected_layers"])

    def test_affected_layers_marks_changed_layer_with_badge(self) -> None:
        repo = CsvRepository(self.root)
        row = repo.find_rows("construction_layers.csv", "name", "beton")[0]

        model = build_dependency_service_model_for_row(
            repo=repo,
            dataset_name="construction_layers.csv",
            row=row,
            changed_column="thickness_m",
        )

        changed_layer = next(
            item for item in model["affected_layers"] if item["badge"] == "Degisen Layer"
        )
        self.assertEqual(changed_layer["material_name"], "beton")
        self.assertIn("disduvar", changed_layer["construction_names"])

    def test_affected_surfaces_include_wall_roof_and_floor_reason(self) -> None:
        model = build_dependency_service_model(
            csv_root=self.root,
            dataset_name="materials.csv",
            match_column="name",
            match_value="beton",
            changed_column="conductivity_w_per_mk",
        )

        surface_items = model["affected_surfaces"]
        surface_datasets = {item["dataset"] for item in surface_items}

        self.assertIn("walls.csv", surface_datasets)
        self.assertIn("roofs.csv", surface_datasets)
        self.assertIn("floors.csv", surface_datasets)
        wall_item = next(item for item in surface_items if item["dataset"] == "walls.csv")
        self.assertEqual(wall_item["surface_name"], "Wall 1")
        self.assertEqual(wall_item["construction_name"], "disduvar")
        self.assertTrue(wall_item["reason"])


if __name__ == "__main__":
    unittest.main()
