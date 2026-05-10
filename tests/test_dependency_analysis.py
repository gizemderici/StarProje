import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from analyze_csv_dependencies import (
    CsvRepository,
    analyze_row_dependency,
    build_impact_analysis_from_changes,
    detect_state_changes,
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


class DependencyAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))
        self.old_root = self.root / "old"
        self.new_root = self.root / "new"
        write_dataset(self.old_root)
        write_dataset(self.new_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_analyze_row_dependency_separates_direct_and_indirect_impacts(self) -> None:
        repo = CsvRepository(self.old_root)

        report = analyze_row_dependency(
            repo,
            "materials.csv",
            "name",
            "beton",
            "conductivity_w_per_mk",
        )

        self.assertEqual(report["dataset"], "materials.csv")
        self.assertEqual(report["matched_row_count"], 1)
        impacts = report["reports"][0]["impacts"]
        direct_datasets = {impact["dataset"] for impact in impacts if impact["impact_type"] == "direct"}
        indirect_datasets = {impact["dataset"] for impact in impacts if impact["impact_type"] == "indirect"}
        self.assertIn("construction_layers.csv", direct_datasets)
        self.assertIn("constructions.csv", indirect_datasets)
        self.assertIn("walls.csv", indirect_datasets)
        self.assertIn("floors.csv", indirect_datasets)
        self.assertIn("roofs.csv", indirect_datasets)

    def test_detect_state_changes_finds_updated_cells(self) -> None:
        new_materials = self.new_root / "materials.csv"
        text = new_materials.read_text(encoding="utf-8-sig")
        text = text.replace("beton,OS_Material,0.2,1.75,", "beton,OS_Material,0.2,2.10,")
        new_materials.write_text(text, encoding="utf-8-sig")

        old_repo = CsvRepository(self.old_root)
        new_repo = CsvRepository(self.new_root)
        detected_changes = detect_state_changes(old_repo, new_repo, limit=10)

        self.assertEqual(detected_changes["total_change_count"], 1)
        self.assertEqual(detected_changes["processed_change_count"], 1)
        first_change = detected_changes["changes"][0]
        self.assertEqual(first_change["dataset"], "materials.csv")
        self.assertEqual(first_change["column"], "conductivity_w_per_mk")
        self.assertEqual(first_change["old_value"], "1.75")
        self.assertEqual(first_change["new_value"], "2.10")

    def test_build_impact_analysis_from_changes_returns_summary(self) -> None:
        new_materials = self.new_root / "materials.csv"
        text = new_materials.read_text(encoding="utf-8-sig")
        text = text.replace("beton,OS_Material,0.2,1.75,", "beton,OS_Material,0.2,2.10,")
        new_materials.write_text(text, encoding="utf-8-sig")

        old_repo = CsvRepository(self.old_root)
        new_repo = CsvRepository(self.new_root)
        detected_changes = detect_state_changes(old_repo, new_repo, limit=10)
        detected_changes["old_root"] = self.old_root.as_posix()
        detected_changes["new_root"] = self.new_root.as_posix()

        report = build_impact_analysis_from_changes(new_repo, detected_changes)

        self.assertEqual(report["trigger_mode"], "state_diff")
        self.assertEqual(report["total_change_count"], 1)
        result = report["results"][0]
        self.assertEqual(result["status"], "analyzed")
        self.assertGreater(result["impact_summary"]["direct_count"], 0)
        self.assertGreater(result["impact_summary"]["indirect_count"], 0)


if __name__ == "__main__":
    unittest.main()
