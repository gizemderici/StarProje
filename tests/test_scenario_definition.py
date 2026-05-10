import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from apply_scenario_definition import apply_scenario_to_rows
from update_csv_fields import get_file_rules


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)


class ScenarioDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / ".tmp_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=self.temp_root))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_supported_files_include_surface_and_construction_datasets(self) -> None:
        cases = {
            "constructions.csv": {"name"},
            "walls.csv": {"construction_name"},
            "roofs.csv": {"construction_name"},
            "floors.csv": {"construction_name"},
            "windows.csv": {"construction_name", "u_factor", "shgc"},
        }

        for file_name, expected_columns in cases.items():
            with self.subTest(file_name=file_name):
                rules = get_file_rules(Path(file_name))
                self.assertEqual(rules["key_columns"], {"name"})
                self.assertEqual(set(rules["editable_columns"]), expected_columns)

    def test_apply_scenario_updates_wall_construction_name(self) -> None:
        input_path = self.root / "walls.csv"
        write_csv(
            input_path,
            [
                [
                    "name",
                    "surface_type",
                    "element_class",
                    "gross_area_m2",
                    "outside_boundary_condition",
                    "azimuth_rad",
                    "space_name",
                    "construction_name",
                ],
                ["Face 50", "Wall", "dis_duvar", "6.0", "Outdoors", "0.0", "kuzey_k1", "disduvar"],
                ["Face 14", "Wall", "dis_duvar", "15.0", "Outdoors", "1.57", "kuzeydogu", "disduvar"],
            ],
        )

        scenario = {
            "scenario_name": "wall_construction_swap",
            "input": str(input_path),
            "output": str(self.root / "walls_updated.csv"),
            "operations": [
                {
                    "name": "swap_wall_construction",
                    "match": {"column": "name", "value": "Face 50"},
                    "updates": {"construction_name": "high_perf_wall"},
                }
            ],
        }

        rows, fieldnames, change_logs, returned_input_path = apply_scenario_to_rows(scenario)

        self.assertEqual(returned_input_path, input_path)
        self.assertIn("construction_name", fieldnames)
        self.assertEqual(len(change_logs), 1)
        self.assertEqual(change_logs[0]["kolon"], "construction_name")
        updated_row = next(row for row in rows if row["name"] == "Face 50")
        untouched_row = next(row for row in rows if row["name"] == "Face 14")
        self.assertEqual(updated_row["construction_name"], "high_perf_wall")
        self.assertEqual(untouched_row["construction_name"], "disduvar")

    def test_apply_scenario_updates_construction_name_record(self) -> None:
        input_path = self.root / "constructions.csv"
        write_csv(
            input_path,
            [
                ["name", "type", "layer_count"],
                ["disduvar", "OS_Construction", "7"],
                ["zemin", "OS_Construction", "4"],
            ],
        )

        scenario = {
            "scenario_name": "construction_rename",
            "input": str(input_path),
            "output": str(self.root / "constructions_updated.csv"),
            "operations": [
                {
                    "name": "rename_construction",
                    "match": {"column": "name", "value": "disduvar"},
                    "updates": {"name": "disduvar_v2"},
                }
            ],
        }

        rows, _, change_logs, _ = apply_scenario_to_rows(scenario)

        self.assertEqual(len(change_logs), 1)
        self.assertEqual(change_logs[0]["eski_deger"], "disduvar")
        self.assertEqual(change_logs[0]["yeni_deger"], "disduvar_v2")
        updated_names = [row["name"] for row in rows]
        self.assertEqual(updated_names, ["disduvar_v2", "zemin"])

    def test_apply_scenario_supports_extra_match_for_composite_row_selection(self) -> None:
        input_path = self.root / "construction_layers.csv"
        write_csv(
            input_path,
            [
                [
                    "construction_name",
                    "construction_type",
                    "layer_index",
                    "name",
                    "type",
                    "thickness_m",
                    "conductivity_w_per_mk",
                ],
                ["disduvar", "OS_Construction", "1", "siva", "OS_Material", "0.01", "0.15"],
                ["disduvar", "OS_Construction", "2", "beton", "OS_Material", "0.20", "1.75"],
                ["icduvar", "OS_Construction", "2", "beton", "OS_Material", "0.10", "1.40"],
            ],
        )

        scenario = {
            "scenario_name": "layer_specific_update",
            "input": str(input_path),
            "output": str(self.root / "construction_layers_updated.csv"),
            "operations": [
                {
                    "name": "update_disduvar_beton_layer",
                    "match": {"column": "name", "value": "beton"},
                    "extra_match": {
                        "construction_name": "disduvar",
                        "layer_index": "2",
                    },
                    "updates": {"conductivity_w_per_mk": "1.90"},
                }
            ],
        }

        rows, _, change_logs, _ = apply_scenario_to_rows(scenario)

        self.assertEqual(len(change_logs), 1)
        updated_row = next(
            row
            for row in rows
            if row["construction_name"] == "disduvar"
            and row["layer_index"] == "2"
            and row["name"] == "beton"
        )
        other_row = next(
            row
            for row in rows
            if row["construction_name"] == "icduvar"
            and row["layer_index"] == "2"
            and row["name"] == "beton"
        )
        self.assertEqual(updated_row["conductivity_w_per_mk"], "1.90")
        self.assertEqual(other_row["conductivity_w_per_mk"], "1.40")


if __name__ == "__main__":
    unittest.main()
