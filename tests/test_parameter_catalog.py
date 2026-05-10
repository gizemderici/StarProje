import unittest

from parameter_catalog import (
    PARAMETER_CATALOG,
    build_parameter_groups_for_ui,
    build_supported_files,
    get_parameter_definition,
    group_parameters_by_category,
    list_categories,
)


class ParameterCatalogTests(unittest.TestCase):
    def test_example_parameters_exist(self) -> None:
        expected_ids = {
            "material_thickness",
            "material_conductivity",
            "material_density",
            "window_u_factor",
            "window_shgc",
        }
        self.assertTrue(expected_ids.issubset(set(PARAMETER_CATALOG)))

    def test_parameter_definition_contains_required_metadata(self) -> None:
        parameter = get_parameter_definition("material_thickness")

        self.assertIsNotNone(parameter)
        assert parameter is not None
        self.assertEqual(parameter.dataset, "materials.csv")
        self.assertEqual(parameter.field_name, "thickness_m")
        self.assertEqual(parameter.value_type, "float")
        self.assertEqual(parameter.unit, "m")
        self.assertIsNotNone(parameter.description)
        self.assertIsNotNone(parameter.category)
        self.assertTrue(parameter.affected_entities)
        self.assertTrue(parameter.expected_impacts)

    def test_supported_files_are_derived_from_catalog(self) -> None:
        supported_files = build_supported_files()

        self.assertIn("materials.csv", supported_files)
        self.assertIn("thickness_m", supported_files["materials.csv"]["editable_columns"])
        self.assertIn("density_kg_per_m3", supported_files["materials.csv"]["editable_columns"])
        self.assertIn("u_factor", supported_files["windows.csv"]["editable_columns"])
        self.assertEqual(supported_files["construction_layers.csv"]["key_columns"], {"construction_name", "layer_index", "name"})

    def test_categories_follow_requested_ui_order(self) -> None:
        self.assertEqual(
            list_categories(),
            [
                "Materials",
                "Constructions",
                "Walls",
                "Roofs",
                "Floors",
                "Windows",
                "Openings",
                "Thermal Properties",
                "Cost Related",
                "Comfort Related",
            ],
        )

    def test_grouping_includes_all_ui_categories(self) -> None:
        grouped = group_parameters_by_category()

        self.assertEqual(set(grouped), set(list_categories()))
        self.assertGreater(len(grouped["Materials"]), 0)
        self.assertGreater(len(grouped["Constructions"]), 0)
        self.assertEqual(grouped["Openings"], [])

    def test_ui_groups_are_ready_for_category_based_rendering(self) -> None:
        groups = build_parameter_groups_for_ui()

        self.assertEqual(len(groups), len(list_categories()))
        self.assertEqual(groups[0]["category"], "Materials")
        self.assertIn("parameter_count", groups[0])
        self.assertIn("parameters", groups[0])


if __name__ == "__main__":
    unittest.main()
