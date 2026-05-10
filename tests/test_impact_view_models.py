import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from nicegui_csv_viewer import (
    build_absolute_parameter_page_url,
    build_combined_impact_summary,
    get_cost_profile_options,
    load_cost_profiles,
    normalize_cost_profiles,
    build_runner_status_view_model,
    build_parameter_page_url,
    build_share_qr_service_url,
    build_impact_chart_model,
    build_impact_summary,
    build_structural_impact_view_model,
    filter_structural_impact_rows,
    filter_impact_rows,
    format_delta,
    group_layer_impact_rows_by_construction,
    parse_parameter_page_query,
    resolve_cost_profile,
    parse_selected_parameter_state,
    serialize_selected_parameter_state,
    summarize_structural_impact_cards,
    build_parameter_change_chart_model,
    build_parameter_delta_summary,
    build_parameter_impact_map_model,
    build_parameter_impact_summary_cards,
    build_parameter_overlay_series,
    build_parameter_overlay_tooltip_formatter,
    build_energy_performance_chart_model,
    build_delta_summary_text,
    build_monthly_energy_overlay_model,
    build_monthly_energy_chart_model,
    build_overlay_explanation,
    build_overlay_legend_labels,
    build_overlay_tooltip_formatter,
    build_scenario_visual_registry,
    build_scenario_visual_profile,
    build_zone_temperature_overlay_model,
    build_zone_temperature_chart_model,
    build_zone_temperature_comfort_summary,
    build_zone_last_known_point_model,
    build_zone_portfolio_analysis,
    build_zone_heatmap_model,
    build_parameter_waterfall_chart_model,
    build_peak_load_analysis,
    build_seasonal_energy_analysis,
    build_layer_impact_chart_model,
    build_cost_comparison_chart_model,
    build_parameter_recommended_range_text,
    build_parameter_recommended_range_style,
    validate_parameter_new_value,
)
from parameter_catalog import list_parameter_definitions
from simulation_runner import RunnerStatusEvent


SAMPLE_IMPACT_ROWS = [
    {
        "id": "beton-direct",
        "degisen_alan": "conductivity_w_per_mk",
        "eski_deger": "1.75",
        "yeni_deger": "2.10",
        "degisim_miktari": "0.35",
        "degisim_numeric": 0.35,
        "yon": "Artis",
        "etki_tipi": "Dogrudan",
        "etkilenen_veri": "construction_layers.csv",
        "etkilenen_satir": 4,
        "kaynak": "name=beton",
        "neden": "Dogrudan bagli katmanlar etkilendi.",
    },
    {
        "id": "beton-indirect",
        "degisen_alan": "conductivity_w_per_mk",
        "eski_deger": "1.75",
        "yeni_deger": "2.10",
        "degisim_miktari": "0.35",
        "degisim_numeric": 0.35,
        "yon": "Artis",
        "etki_tipi": "Dolayli",
        "etkilenen_veri": "walls.csv",
        "etkilenen_satir": 17,
        "kaynak": "name=beton",
        "neden": "Bagli duvarlar etkilendi.",
    },
    {
        "id": "tugla-direct",
        "degisen_alan": "thickness_m",
        "eski_deger": "0.19",
        "yeni_deger": "0.22",
        "degisim_miktari": "0.03",
        "degisim_numeric": 0.03,
        "yon": "Artis",
        "etki_tipi": "Dogrudan",
        "etkilenen_veri": "construction_layers.csv",
        "etkilenen_satir": 2,
        "kaynak": "name=tugla",
        "neden": "Dogrudan bagli katmanlar etkilendi.",
    },
]


class ImpactViewModelTests(unittest.TestCase):
    def test_normalize_cost_profiles_returns_default_for_invalid_payload(self) -> None:
        normalized = normalize_cost_profiles(["invalid"])  # type: ignore[arg-type]

        self.assertIn("custom", normalized)
        self.assertIn("tr_electricity_residential", normalized)

    def test_load_cost_profiles_reads_json_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "cost_profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profiles": {
                            "demo_tariff": {
                                "label": "Demo Tarife",
                                "unit_cost": 1.75,
                                "currency": "TRY",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            loaded = load_cost_profiles(config_path)

        self.assertIn("demo_tariff", loaded)
        self.assertIn("custom", loaded)
        self.assertEqual(float(loaded["demo_tariff"]["unit_cost"]), 1.75)

    def test_cost_profile_options_contains_common_presets(self) -> None:
        options = get_cost_profile_options()

        self.assertIn("tr_electricity_residential", options)
        self.assertIn("eu_electricity_average", options)
        self.assertIn("us_electricity_average", options)
        self.assertIn("custom", options)

    def test_resolve_cost_profile_falls_back_to_custom(self) -> None:
        profile = resolve_cost_profile("unknown_profile")

        self.assertEqual(profile["id"], "custom")
        self.assertEqual(profile["currency"], "TRY")
        self.assertGreater(float(profile["unit_cost"]), 0)

    def test_build_absolute_parameter_page_url_combines_origin_and_path(self) -> None:
        self.assertEqual(
            build_absolute_parameter_page_url("http://localhost:8080/", "/parameters?a=1"),
            "http://localhost:8080/parameters?a=1",
        )
        self.assertEqual(
            build_absolute_parameter_page_url("", "/parameters?a=1"),
            "/parameters?a=1",
        )

    def test_build_parameter_page_url_preserves_dataset_filter(self) -> None:
        self.assertEqual(build_parameter_page_url(), "/parameters")
        self.assertEqual(build_parameter_page_url("Tum Veri Setleri"), "/parameters")
        self.assertEqual(
            build_parameter_page_url("construction_layers.csv"),
            "/parameters?impact_dataset=construction_layers.csv",
        )
        self.assertEqual(
            build_parameter_page_url(
                dataset_filter="walls.csv",
                category="Windows",
                search_query="u factor",
                scenario_name="facade_upgrade_option_a",
                scenario_description="short note",
                selected_parameter_ids=["window_u_factor", "window_shgc"],
                selected_parameter_state={
                    "window_u_factor": {
                        "record_label": "Window 1",
                        "new_value": "1.8",
                    }
                },
            ),
            "/parameters?impact_dataset=walls.csv&category=Windows&search=u+factor&scenario_name=facade_upgrade_option_a&scenario_description=short+note&selected=window_u_factor%2Cwindow_shgc&selection_state=%7B%22window_u_factor%22%3A%7B%22record_label%22%3A%22Window+1%22%2C%22new_value%22%3A%221.8%22%7D%7D",
        )

    def test_parse_parameter_page_query_restores_filter_search_and_selection(self) -> None:
        parsed = parse_parameter_page_query(
            {
                "impact_dataset": "walls.csv",
                "category": "Windows",
                "search": "u factor",
                "scenario_name": "facade_upgrade_option_a",
                "scenario_description": "short note",
                "selected": "window_u_factor,window_shgc",
                "selection_state": '{"window_u_factor":{"record_label":"Window 1","new_value":"1.8"}}',
            }
        )

        self.assertEqual(parsed["impact_dataset"], "walls.csv")
        self.assertEqual(parsed["category"], "Windows")
        self.assertEqual(parsed["search"], "u factor")
        self.assertEqual(parsed["scenario_name"], "facade_upgrade_option_a")
        self.assertEqual(parsed["scenario_description"], "short note")
        self.assertEqual(
            parsed["selected_parameter_ids"],
            ["window_u_factor", "window_shgc"],
        )
        self.assertEqual(
            parsed["selected_parameter_state"]["window_u_factor"]["record_label"],
            "Window 1",
        )
        self.assertEqual(
            parsed["selected_parameter_state"]["window_u_factor"]["new_value"],
            "1.8",
        )

    def test_build_share_qr_service_url_encodes_absolute_url(self) -> None:
        qr_url = build_share_qr_service_url("http://localhost:8080/parameters?a=1", size=120)
        self.assertIn("size=120x120", qr_url)
        self.assertIn("http%3A%2F%2Flocalhost%3A8080%2Fparameters%3Fa%3D1", qr_url)

    def test_selected_parameter_state_serialization_round_trip(self) -> None:
        raw = serialize_selected_parameter_state(
            {
                "window_u_factor": {
                    "record_label": "Window 1",
                    "new_value": "1.8",
                    "current_value": "2.4",
                },
                "window_shgc": {
                    "record_label": "",
                    "new_value": "",
                },
            }
        )
        parsed = parse_selected_parameter_state(raw)

        self.assertEqual(
            parsed,
            {
                "window_u_factor": {
                    "record_label": "Window 1",
                    "new_value": "1.8",
                }
            },
        )

    def test_format_delta_handles_numbers_and_invalid_values(self) -> None:
        self.assertEqual(format_delta("1.75", "2.10"), ("0.35", "Artis"))
        self.assertEqual(format_delta("2.10", "1.75"), ("-0.35", "Azalis"))
        self.assertEqual(format_delta("", "abc"), ("-", "Degisim"))

    def test_filter_impact_rows_filters_by_type_and_sort(self) -> None:
        filtered_rows = filter_impact_rows(
            SAMPLE_IMPACT_ROWS,
            query="walls",
            impact_type="Sadece Dolayli",
            sort_mode="En Fazla Etki",
        )

        self.assertEqual(len(filtered_rows), 1)
        self.assertEqual(filtered_rows[0]["etkilenen_veri"], "walls.csv")
        self.assertEqual(filtered_rows[0]["etki_tipi"], "Dolayli")

    def test_build_impact_summary_returns_counts_and_critical_message(self) -> None:
        summary = build_impact_summary(SAMPLE_IMPACT_ROWS)

        self.assertEqual(summary["changed_fields"], "conductivity_w_per_mk, thickness_m")
        self.assertEqual(summary["direct_rows"], 6)
        self.assertEqual(summary["indirect_rows"], 17)
        self.assertEqual(summary["total_rows"], 23)
        self.assertEqual(summary["critical_tone"], "critical")

    def test_build_impact_chart_model_produces_comparison_distribution_and_relations(self) -> None:
        chart_model = build_impact_chart_model(SAMPLE_IMPACT_ROWS)

        self.assertEqual(len(chart_model["comparison"]["labels"]), 2)
        self.assertEqual(len(chart_model["distribution"]["labels"]), 2)
        self.assertTrue(chart_model["relations"]["nodes"])
        self.assertTrue(chart_model["relations"]["links"])
        self.assertEqual(
            [category["name"] for category in chart_model["relations"]["categories"]],
            ["Ana Degisim", "Dogrudan Etki", "Dolayli Etki"],
        )

    def test_empty_inputs_are_safe(self) -> None:
        self.assertEqual(filter_impact_rows([], query="beton"), [])
        summary = build_impact_summary([])
        self.assertEqual(summary["total_rows"], 0)
        chart_model = build_impact_chart_model([])
        self.assertEqual(chart_model["comparison"]["labels"], [])
        self.assertEqual(chart_model["relations"]["nodes"], [])

    def test_build_parameter_change_chart_model_filters_non_numeric_values(self) -> None:
        selected_state = {
            "thickness": {
                "definition": SimpleNamespace(label="Thickness", unit="m"),
                "current_value": "1",
                "new_value": "2",
            },
            "conductivity": {
                "definition": SimpleNamespace(label="Conductivity", unit="W/mK"),
                "current_value": "0.4",
                "new_value": "0.6",
            },
            "material_name": {
                "definition": SimpleNamespace(label="Material Name", unit=""),
                "current_value": "beton",
                "new_value": "beton-a",
            },
        }

        chart_model = build_parameter_change_chart_model(selected_state)

        self.assertEqual(chart_model["labels"], ["Thickness", "Conductivity"])
        self.assertEqual(chart_model["base_values"], [1.0, 0.4])
        self.assertEqual(chart_model["updated_values"], [2.0, 0.6])
        self.assertTrue(chart_model["is_normalized"])
        self.assertAlmostEqual(chart_model["before_values"][0], 0.5, places=6)
        self.assertAlmostEqual(chart_model["before_values"][1], 2.0 / 3.0, places=6)
        self.assertAlmostEqual(chart_model["after_values"][0], 1.0, places=6)
        self.assertAlmostEqual(chart_model["after_values"][1], 1.0, places=6)
        self.assertAlmostEqual(chart_model["delta_values"][0], 1.0, places=6)
        self.assertAlmostEqual(chart_model["delta_values"][1], 0.2, places=6)
        self.assertEqual(chart_model["skipped_count"], 1)
        self.assertEqual(chart_model["skipped_labels"], ["Material Name"])

    def test_build_parameter_change_chart_model_keeps_base_when_updated_missing(self) -> None:
        selected_state = {
            "thickness": {
                "definition": SimpleNamespace(label="Thickness", unit="m"),
                "current_value": "0.19",
                "new_value": "",
            },
            "conductivity": {
                "definition": SimpleNamespace(label="Conductivity", unit="m"),
                "current_value": "0.40",
                "new_value": "0.60",
            },
        }

        chart_model = build_parameter_change_chart_model(selected_state)

        self.assertFalse(chart_model["is_normalized"])
        self.assertEqual(chart_model["before_values"], [0.19, 0.4])
        self.assertEqual(chart_model["after_values"], [None, 0.6])
        self.assertEqual(chart_model["missing_updated_labels"], ["Thickness"])
        self.assertEqual(chart_model["delta_values"], [None, 0.19999999999999996])

    def test_build_parameter_overlay_tooltip_formatter_uses_real_values(self) -> None:
        formatter = build_parameter_overlay_tooltip_formatter(
            {
                "labels": ["Thickness"],
                "base_values": [0.19],
                "updated_values": [0.25],
                "units": ["m"],
            }
        )

        self.assertIn("Parametre:", formatter)
        self.assertIn("Base:", formatter)
        self.assertIn("Updated:", formatter)
        self.assertIn("Δ:", formatter)
        self.assertIn("%Δ:", formatter)
        self.assertIn('"Thickness"', formatter)

    def test_build_parameter_delta_summary_reports_base_updated_and_percent(self) -> None:
        summary = build_parameter_delta_summary(
            {
                "labels": ["Thickness"],
                "base_values": [12000],
                "updated_values": [9500],
                "units": ["kWh"],
            },
            0,
        )

        self.assertIn("Thickness", summary)
        self.assertIn("Base: 12000 kWh", summary)
        self.assertIn("Updated: 9500 kWh", summary)
        self.assertIn("Δ: -2500 kWh", summary)
        self.assertIn("%Δ: -20.83%", summary)

    def test_build_parameter_impact_map_model_summarizes_selected_parameters(self) -> None:
        selected_state = {
            "material_thickness": {
                "definition": SimpleNamespace(
                    label="Material Thickness",
                    expected_impacts=("u_value", "thermal_mass", "assembly_thickness"),
                )
            },
            "material_conductivity": {
                "definition": SimpleNamespace(
                    label="Material Conductivity",
                    expected_impacts=("heat_transfer", "envelope_performance"),
                )
            },
        }

        impact_map = build_parameter_impact_map_model(selected_state)

        self.assertTrue(impact_map["has_data"])
        self.assertEqual(len(impact_map["rows"]), 2)
        thickness_row = impact_map["rows"][0]
        conductivity_row = impact_map["rows"][1]

        self.assertEqual(thickness_row["parameter_label"], "Material Thickness")
        self.assertEqual(thickness_row["heating"]["label"], "guclu")
        self.assertEqual(thickness_row["cost"]["label"], "guclu")
        self.assertEqual(thickness_row["comfort"]["label"], "guclu")
        self.assertEqual(thickness_row["cooling"]["label"], "orta")

        self.assertEqual(conductivity_row["parameter_label"], "Material Conductivity")
        self.assertEqual(conductivity_row["cooling"]["label"], "guclu")
        self.assertEqual(conductivity_row["cost"]["label"], "orta")
        self.assertIn("heat_transfer", conductivity_row["matched_impacts"])

    def test_build_parameter_impact_summary_cards_highlights_top_dimensions(self) -> None:
        impact_map = {
            "rows": [
                {
                    "parameter_label": "Material Thickness",
                    "heating": {"score": 4, "text": "guclu", "emoji": "🟢", "classes": "a"},
                    "cooling": {"score": 2, "text": "orta", "emoji": "🟡", "classes": "b"},
                    "cost": {"score": 4, "text": "guclu", "emoji": "🟢", "classes": "c"},
                    "comfort": {"score": 5, "text": "guclu", "emoji": "🟢", "classes": "d"},
                },
                {
                    "parameter_label": "Material Conductivity",
                    "heating": {"score": 2, "text": "orta", "emoji": "🟡", "classes": "e"},
                    "cooling": {"score": 4, "text": "guclu", "emoji": "🟢", "classes": "f"},
                    "cost": {"score": 2, "text": "orta", "emoji": "🟡", "classes": "g"},
                    "comfort": {"score": 2, "text": "orta", "emoji": "🟡", "classes": "h"},
                },
            ]
        }

        cards = build_parameter_impact_summary_cards(impact_map)

        self.assertEqual(len(cards), 4)
        by_dimension = {card["dimension"]: card for card in cards}
        self.assertEqual(by_dimension["heating"]["parameter_label"], "Material Thickness")
        self.assertEqual(by_dimension["cooling"]["parameter_label"], "Material Conductivity")
        self.assertEqual(by_dimension["cost"]["parameter_label"], "Material Thickness")
        self.assertEqual(by_dimension["comfort"]["parameter_label"], "Material Thickness")

    def test_build_parameter_overlay_series_creates_base_steps_and_final_line(self) -> None:
        series = build_parameter_overlay_series(
            labels=["Thickness", "Conductivity", "Density"],
            before_values=[1.0, 0.4, 800.0],
            after_values=[2.0, 0.6, 800.0],
        )

        self.assertGreaterEqual(len(series), 4)
        self.assertEqual(series[0]["name"], "Base Scenario")
        self.assertEqual(series[0]["data"], [1.0, 0.4, 800.0])
        self.assertEqual(series[1]["name"], "Degisim 1: Thickness")
        self.assertEqual(series[1]["data"], [2.0, 0.4, 800.0])
        self.assertEqual(series[2]["name"], "Degisim 2: Conductivity")
        self.assertEqual(series[2]["data"], [2.0, 0.6, 800.0])
        self.assertEqual(series[-1]["name"], "Scenario (Final)")
        self.assertEqual(series[-1]["data"], [2.0, 0.6, 800.0])

    def test_build_energy_performance_chart_model_maps_old_new_values(self) -> None:
        metrics_rows = [
            {
                "metric_id": "annual_heating",
                "unit": "kWh",
                "base_value": 1000,
                "scenario_value": 850,
            },
            {
                "metric_id": "annual_cooling",
                "unit": "kWh",
                "base_value": 500,
                "scenario_value": 530,
            },
            {
                "metric_id": "total_energy",
                "unit": "kWh",
                "base_value": 1500,
                "scenario_value": 1380,
            },
        ]

        chart_model = build_energy_performance_chart_model(metrics_rows)

        self.assertEqual(
            chart_model["labels"],
            ["Annual Heating", "Annual Cooling", "Total Energy"],
        )
        self.assertEqual(chart_model["before_values"], [1000.0, 500.0, 1500.0])
        self.assertEqual(chart_model["after_values"], [850.0, 530.0, 1380.0])
        self.assertEqual(chart_model["missing_count"], 0)
        self.assertTrue(chart_model["has_data"])

    def test_build_energy_performance_chart_model_marks_missing_metrics(self) -> None:
        metrics_rows = [
            {
                "metric_id": "annual_heating",
                "unit": "kWh",
                "base_value": 1000,
                "scenario_value": 900,
            }
        ]

        chart_model = build_energy_performance_chart_model(metrics_rows)

        self.assertEqual(chart_model["before_values"], [1000.0, None, None])
        self.assertEqual(chart_model["after_values"], [900.0, None, None])
        self.assertEqual(chart_model["missing_count"], 2)
        self.assertEqual(chart_model["missing_labels"], ["Annual Cooling", "Total Energy"])
        self.assertTrue(chart_model["has_data"])

    def test_build_monthly_energy_chart_model_parses_json_heating_and_cooling(self) -> None:
        metrics_rows = [
            {
                "metric_id": "monthly_heating_cooling",
                "base_value": '{"heating": [100, 90, 80, 70, 60, 50, 40, 40, 50, 70, 85, 95], "cooling": [20, 25, 35, 45, 60, 75, 90, 85, 65, 45, 30, 25]}',
                "scenario_value": '{"heating": [95, 85, 75, 65, 55, 45, 35, 35, 45, 65, 80, 90], "cooling": [18, 22, 32, 42, 57, 71, 86, 81, 61, 41, 27, 22]}',
            }
        ]

        chart_model = build_monthly_energy_chart_model(
            metrics_rows,
            scenario_name="Thickness Updated",
            scenario_order=1,
        )

        self.assertTrue(chart_model["has_data"])
        self.assertEqual(len(chart_model["months"]), 12)
        self.assertEqual(chart_model["base_heating"][0], 100.0)
        self.assertEqual(chart_model["scenario_heating"][0], 95.0)
        self.assertEqual(chart_model["base_cooling"][6], 90.0)
        self.assertEqual(chart_model["scenario_cooling"][6], 86.0)
        self.assertEqual(chart_model["missing_series"], [])
        self.assertEqual(chart_model["base_series_profile"]["legend_name"], "Base Scenario")
        self.assertEqual(chart_model["scenario_series_profile"]["legend_name"], "Thickness Updated")
        self.assertEqual(chart_model["scenario_series_profile"]["line_type"], "dotted")
        self.assertEqual(chart_model["scenario_series_profile"]["marker"], "triangle")

    def test_build_monthly_energy_chart_model_handles_missing_metric(self) -> None:
        chart_model = build_monthly_energy_chart_model([])

        self.assertFalse(chart_model["has_data"])
        self.assertEqual(chart_model["missing_series"], ["Heating", "Cooling"])
        self.assertEqual(len(chart_model["base_heating"]), 12)
        self.assertEqual(len(chart_model["scenario_cooling"]), 12)

    def test_build_zone_temperature_chart_model_parses_zone_series(self) -> None:
        metrics_rows = [
            {
                "metric_id": "zone_temperatures",
                "base_value": json.dumps(
                    {
                        "zones": {
                            "Zone A": {
                                "timestamps": ["00:00", "01:00", "02:00"],
                                "values": [21.0, 20.5, 20.0],
                            }
                        }
                    }
                ),
                "scenario_value": json.dumps(
                    {
                        "zones": {
                            "Zone A": {
                                "timestamps": ["00:00", "01:00", "02:00"],
                                "values": [20.8, 20.2, 19.8],
                            }
                        }
                    }
                ),
            }
        ]

        chart_model = build_zone_temperature_chart_model(
            metrics_rows,
            scenario_name="Multi Insulation Scenario",
            scenario_order=2,
        )

        self.assertTrue(chart_model["has_data"])
        self.assertEqual(chart_model["zone_options"], ["Zone A"])
        self.assertEqual(chart_model["selected_zone"], "Zone A")
        self.assertEqual(chart_model["time_labels"], ["00:00", "01:00", "02:00"])
        self.assertEqual(chart_model["base_values"], [21.0, 20.5, 20.0])
        self.assertEqual(chart_model["scenario_values"], [20.8, 20.2, 19.8])
        self.assertEqual(chart_model["scenario_series_profile"]["legend_name"], "Multi Insulation Scenario")
        self.assertEqual(chart_model["scenario_series_profile"]["line_type"], "dashed")
        self.assertEqual(chart_model["scenario_series_profile"]["marker"], "rect")

    def test_build_zone_temperature_chart_model_respects_selected_zone(self) -> None:
        metrics_rows = [
            {
                "metric_id": "zone_temperatures",
                "base_value": {
                    "zones": {
                        "Zone A": {"values": [21, 22]},
                        "Zone B": {"values": [23, 24]},
                    }
                },
                "scenario_value": {
                    "zones": {
                        "Zone A": {"values": [20.5, 21.5]},
                        "Zone B": {"values": [22.2, 23.1]},
                    }
                },
            }
        ]

        chart_model = build_zone_temperature_chart_model(metrics_rows, selected_zone="Zone B")

        self.assertEqual(chart_model["selected_zone"], "Zone B")
        self.assertEqual(chart_model["base_values"], [23.0, 24.0])
        self.assertEqual(chart_model["scenario_values"], [22.2, 23.1])

    def test_build_zone_temperature_chart_model_handles_missing_metric(self) -> None:
        chart_model = build_zone_temperature_chart_model([])

        self.assertFalse(chart_model["has_data"])
        self.assertEqual(chart_model["zone_options"], [])
        self.assertEqual(chart_model["time_labels"], [])

    def test_build_scenario_visual_profile_assigns_distinct_styles_by_order(self) -> None:
        first = build_scenario_visual_profile("Thickness Updated", scenario_order=0)
        second = build_scenario_visual_profile("Thickness + Conductivity", scenario_order=1)

        self.assertEqual(first["legend_name"], "Thickness Updated")
        self.assertEqual(first["order"], 1)
        self.assertEqual(first["line_type"], "dashed")
        self.assertEqual(first["marker"], "diamond")
        self.assertEqual(second["legend_name"], "Thickness + Conductivity")
        self.assertEqual(second["order"], 2)
        self.assertEqual(second["line_type"], "dotted")
        self.assertEqual(second["marker"], "triangle")

    def test_build_scenario_visual_registry_keeps_input_order(self) -> None:
        registry = build_scenario_visual_registry(
            [
                "Base",
                "Thickness Updated",
                "Thickness + Conductivity",
                "Multi Insulation Scenario",
            ]
        )

        self.assertEqual(registry["Base"]["order"], 1)
        self.assertEqual(registry["Thickness Updated"]["order"], 2)
        self.assertEqual(registry["Thickness Updated"]["marker"], "triangle")
        self.assertEqual(registry["Thickness + Conductivity"]["marker"], "rect")
        self.assertEqual(registry["Multi Insulation Scenario"]["line_type"], "dotted")

    def test_build_overlay_legend_labels_prefixes_updated_scenario_name(self) -> None:
        base_profile = {"legend_name": "Base Scenario"}
        scenario_profile = {"legend_name": "Scenario A"}

        labels = build_overlay_legend_labels(base_profile, scenario_profile, prefix="Heating")

        self.assertEqual(labels, ["Heating Base Scenario", "Heating Updated Scenario - Scenario A"])

    def test_build_overlay_explanation_mentions_zone_and_line_styles(self) -> None:
        base_profile = {
            "legend_name": "Base Scenario",
            "line_type": "solid",
            "marker": "circle",
        }
        scenario_profile = {
            "legend_name": "Thickness Updated",
            "line_type": "dashed",
            "marker": "diamond",
        }

        explanation = build_overlay_explanation(
            subject="zone temperature",
            base_profile=base_profile,
            scenario_profile=scenario_profile,
            zone_name="Zone A",
        )

        self.assertIn("zone temperature", explanation)
        self.assertIn("Secilen zone: Zone A.", explanation)
        self.assertIn("Base Scenario duz cizgi", explanation)
        self.assertIn("Updated Scenario - Thickness Updated", explanation)
        self.assertIn("kesikli cizgi", explanation)

    def test_build_overlay_tooltip_formatter_includes_delta_logic(self) -> None:
        formatter = build_overlay_tooltip_formatter("Ay", "kWh")

        self.assertIn("Delta:", formatter)
        self.assertIn("Base Scenario", formatter)
        self.assertIn("Ay:", formatter)
        self.assertIn("kWh", formatter)

    def test_build_monthly_energy_overlay_model_keeps_base_and_updated_aligned(self) -> None:
        comparison_entries = [
            {
                "scenario_name": "Thickness Only",
                "metrics": [
                    {
                        "metric_id": "monthly_heating_cooling",
                        "base_value": json.dumps(
                            {
                                "heating": [100, 90, 80, 70, 60, 50, 40, 30, 20, 30, 60, 90],
                                "cooling": [10, 12, 15, 20, 35, 50, 65, 60, 40, 25, 15, 12],
                            }
                        ),
                        "scenario_value": json.dumps(
                            {
                                "heating": [95, 85, 75, 65, 55, 45, 35, 25, 18, 28, 55, 85],
                                "cooling": [9, 10, 13, 18, 32, 48, 61, 58, 36, 22, 13, 10],
                            }
                        ),
                    }
                ],
            }
        ]

        overlay_model = build_monthly_energy_overlay_model(comparison_entries, ["Thickness Only"])

        self.assertEqual(overlay_model["selected_scenarios"], ["Thickness Only"])
        self.assertEqual(len(overlay_model["months"]), 12)
        self.assertEqual(len(overlay_model["heating_series"]), 2)
        self.assertEqual(overlay_model["heating_series"][0]["values"][0], 100.0)
        self.assertEqual(overlay_model["heating_series"][1]["values"][0], 95.0)
        self.assertEqual(overlay_model["cooling_series"][0]["values"][6], 65.0)
        self.assertEqual(overlay_model["cooling_series"][1]["values"][6], 61.0)
        self.assertEqual(overlay_model["heating_series"][0]["name"], "Heating Base Scenario")
        self.assertEqual(
            overlay_model["heating_series"][1]["name"],
            "Heating Updated Scenario - Thickness Only",
        )

    def test_build_zone_temperature_overlay_model_supports_single_overlay(self) -> None:
        comparison_entries = [
            {
                "scenario_name": "Thickness Only",
                "metrics": [
                    {
                        "metric_id": "zone_temperatures",
                        "base_value": json.dumps(
                            {
                                "zones": {
                                    "Zone A": {
                                        "timestamps": ["00:00", "01:00", "02:00"],
                                        "values": [21.0, 20.5, 20.0],
                                    }
                                }
                            }
                        ),
                        "scenario_value": json.dumps(
                            {
                                "zones": {
                                    "Zone A": {
                                        "timestamps": ["00:00", "01:00", "02:00"],
                                        "values": [20.8, 20.2, 19.8],
                                    }
                                }
                            }
                        ),
                    }
                ],
            }
        ]

        overlay_model = build_zone_temperature_overlay_model(
            comparison_entries,
            ["Thickness Only"],
            selected_zone="Zone A",
        )

        self.assertEqual(overlay_model["selected_zone"], "Zone A")
        self.assertEqual(overlay_model["time_labels"], ["00:00", "01:00", "02:00"])
        self.assertEqual(overlay_model["base_series"]["values"], [21.0, 20.5, 20.0])
        self.assertEqual(len(overlay_model["scenario_series"]), 1)
        self.assertEqual(overlay_model["scenario_series"][0]["values"], [20.8, 20.2, 19.8])
        self.assertEqual(
            overlay_model["scenario_series"][0]["name"],
            "Updated Scenario - Thickness Only",
        )

    def test_build_monthly_energy_overlay_model_supports_three_scenarios(self) -> None:
        base_monthly = json.dumps(
            {
                "heating": [100, 90, 80, 70, 60, 50, 40, 30, 20, 30, 60, 90],
                "cooling": [10, 12, 15, 20, 35, 50, 65, 60, 40, 25, 15, 12],
            }
        )
        comparison_entries = [
            {
                "scenario_name": "Thickness Only",
                "metrics": [
                    {
                        "metric_id": "monthly_heating_cooling",
                        "base_value": base_monthly,
                        "scenario_value": json.dumps({"heating": [95] * 12, "cooling": [9] * 12}),
                    }
                ],
            },
            {
                "scenario_name": "Conductivity Only",
                "metrics": [
                    {
                        "metric_id": "monthly_heating_cooling",
                        "base_value": base_monthly,
                        "scenario_value": json.dumps({"heating": [92] * 12, "cooling": [11] * 12}),
                    }
                ],
            },
            {
                "scenario_name": "Thickness + Conductivity",
                "metrics": [
                    {
                        "metric_id": "monthly_heating_cooling",
                        "base_value": base_monthly,
                        "scenario_value": json.dumps({"heating": [88] * 12, "cooling": [8] * 12}),
                    }
                ],
            },
        ]

        overlay_model = build_monthly_energy_overlay_model(
            comparison_entries,
            ["Thickness Only", "Conductivity Only", "Thickness + Conductivity"],
        )

        self.assertEqual(
            overlay_model["selected_scenarios"],
            ["Thickness Only", "Conductivity Only", "Thickness + Conductivity"],
        )
        self.assertEqual(len(overlay_model["heating_series"]), 4)
        self.assertEqual(len(overlay_model["cooling_series"]), 4)
        self.assertEqual(
            [series["name"] for series in overlay_model["heating_series"]],
            [
                "Heating Base Scenario",
                "Heating Updated Scenario - Thickness Only",
                "Heating Updated Scenario - Conductivity Only",
                "Heating Updated Scenario - Thickness + Conductivity",
            ],
        )
        self.assertNotEqual(
            overlay_model["heating_series"][1]["profile"]["marker"],
            overlay_model["heating_series"][2]["profile"]["marker"],
        )

    def test_build_zone_temperature_overlay_model_supports_three_scenarios(self) -> None:
        def zone_metric(values: list[float]) -> dict[str, object]:
            return {
                "metric_id": "zone_temperatures",
                "base_value": json.dumps(
                    {
                        "zones": {
                            "Zone A": {
                                "timestamps": ["00:00", "01:00", "02:00"],
                                "values": [21.0, 20.5, 20.0],
                            }
                        }
                    }
                ),
                "scenario_value": json.dumps(
                    {
                        "zones": {
                            "Zone A": {
                                "timestamps": ["00:00", "01:00", "02:00"],
                                "values": values,
                            }
                        }
                    }
                ),
            }

        comparison_entries = [
            {"scenario_name": "Thickness Only", "metrics": [zone_metric([20.8, 20.2, 19.8])]},
            {"scenario_name": "Conductivity Only", "metrics": [zone_metric([20.6, 20.0, 19.7])]},
            {"scenario_name": "Thickness + Conductivity", "metrics": [zone_metric([20.4, 19.9, 19.5])]},
        ]

        overlay_model = build_zone_temperature_overlay_model(
            comparison_entries,
            ["Thickness Only", "Conductivity Only", "Thickness + Conductivity"],
            selected_zone="Zone A",
        )

        self.assertEqual(overlay_model["selected_zone"], "Zone A")
        self.assertEqual(len(overlay_model["scenario_series"]), 3)
        self.assertEqual(overlay_model["base_series"]["name"], "Base Scenario")
        self.assertEqual(
            [series["name"] for series in overlay_model["scenario_series"]],
            [
                "Updated Scenario - Thickness Only",
                "Updated Scenario - Conductivity Only",
                "Updated Scenario - Thickness + Conductivity",
            ],
        )

    def test_build_delta_summary_text_reports_max_difference_point(self) -> None:
        summary = build_delta_summary_text(
            "Heating overlay",
            {
                "label": "Ocak",
                "delta": -22.0,
                "series_name": "Heating Updated Scenario - Thickness Only",
            },
            "kWh",
        )

        self.assertIn("Ocak", summary)
        self.assertIn("22.00 kWh", summary)
        self.assertIn("daha dusuk", summary)

    def test_build_zone_temperature_comfort_summary_counts_out_of_band_and_peaks(self) -> None:
        summary = build_zone_temperature_comfort_summary(
            base_values=[19.0, 21.0, 27.5, 24.0, None],
            scenario_values=[20.5, 22.0, 25.0, 26.5, None],
            comfort_min_c=20.0,
            comfort_max_c=26.0,
        )

        self.assertEqual(summary["base_out_of_band"], 2)
        self.assertEqual(summary["scenario_out_of_band"], 1)
        self.assertEqual(summary["base_peak"], 27.5)
        self.assertEqual(summary["scenario_peak"], 26.5)
        self.assertAlmostEqual(float(summary["base_range"]), 8.5, places=6)
        self.assertAlmostEqual(float(summary["scenario_range"]), 6.0, places=6)

    def test_build_zone_portfolio_analysis_returns_zone_highlights(self) -> None:
        metrics_rows = [
            {
                "metric_id": "zone_temperatures",
                "base_value": {
                    "zones": {
                        "Salon": {"values": [22.0, 22.5, 23.0, 23.5]},
                        "Oda": {"values": [21.0, 20.5, 20.0, 19.5]},
                    }
                },
                "scenario_value": {
                    "zones": {
                        "Salon": {"values": [24.0, 26.5, 27.0, 26.8]},
                        "Oda": {"values": [19.5, 19.0, 18.5, 18.0]},
                    }
                },
            }
        ]

        model = build_zone_portfolio_analysis(metrics_rows)

        self.assertTrue(model["has_data"])
        self.assertEqual(len(model["zones"]), 2)
        self.assertEqual(model["most_heat_loss_zone"]["zone"], "Oda")
        self.assertEqual(model["most_overheating_zone"]["zone"], "Salon")

    def test_build_zone_heatmap_model_supports_metric_mode_pairs(self) -> None:
        zone_model = {
            "zones": [
                {
                    "zone": "Salon",
                    "avg_delta": 1.5,
                    "scenario_in_band_hours": 220,
                    "scenario_hot_hours": 45,
                    "scenario_cold_hours": 8,
                    "scenario_stability_std": 0.7,
                    "scenario_peak": 28.2,
                },
                {
                    "zone": "Oda",
                    "avg_delta": -0.8,
                    "scenario_in_band_hours": 240,
                    "scenario_hot_hours": 20,
                    "scenario_cold_hours": 15,
                    "scenario_stability_std": 0.4,
                    "scenario_peak": 26.1,
                },
            ]
        }

        model = build_zone_heatmap_model(zone_model, metric_mode="overheat_vs_cold")

        self.assertTrue(model["has_data"])
        self.assertEqual(model["x_labels"], ["Salon", "Oda"])
        self.assertEqual(model["y_labels"], ["Hot Hours", "Cold Hours"])
        self.assertIn("Asiri isinma", model["summary"])

    def test_build_zone_heatmap_model_keeps_available_rows_when_one_metric_missing(self) -> None:
        zone_model = {
            "zones": [
                {
                    "zone": "Salon",
                    "avg_delta": 1.2,
                    "scenario_in_band_hours": 200,
                    "scenario_hot_hours": 12,
                    "scenario_cold_hours": None,
                },
                {
                    "zone": "Oda",
                    "avg_delta": 0.4,
                    "scenario_in_band_hours": 210,
                    "scenario_hot_hours": 8,
                    "scenario_cold_hours": None,
                },
            ]
        }

        model = build_zone_heatmap_model(zone_model, metric_mode="overheat_vs_cold")

        self.assertTrue(model["has_data"])
        self.assertEqual(model["y_labels"], ["Hot Hours"])
        self.assertIn("Eksik metrik: Cold Hours", model["summary"])

    def test_build_zone_last_known_point_model_returns_single_point_from_zone_averages(self) -> None:
        metrics_rows = [
            {
                "metric_id": "zone_temperatures",
                "base_value": {
                    "zones": {
                        "Salon": {"values": [22.0, 23.0]},
                        "Oda": {"values": [20.0, 21.0]},
                    }
                },
                "scenario_value": {
                    "zones": {
                        "Salon": {"values": [24.0, 25.0]},
                        "Oda": {"values": [19.0, 19.5]},
                    }
                },
            }
        ]

        point_model = build_zone_last_known_point_model(metrics_rows, selected_zone="Oda")

        self.assertTrue(point_model["has_data"])
        self.assertEqual(point_model["zone"], "Oda")
        self.assertAlmostEqual(float(point_model["base_value"]), 20.5, places=6)
        self.assertAlmostEqual(float(point_model["scenario_value"]), 19.25, places=6)
        self.assertEqual(point_model["label"], "Last Known")

    def test_build_parameter_waterfall_chart_model_sorts_by_absolute_delta(self) -> None:
        change_chart_model = {
            "labels": ["A", "B", "C"],
            "delta_values": [1.0, -5.0, 2.5],
            "units": ["kWh", "kWh", "kWh"],
        }

        model = build_parameter_waterfall_chart_model(change_chart_model)

        self.assertTrue(model["has_data"])
        self.assertEqual(model["labels"][:3], ["B", "C", "A"])
        self.assertEqual(model["labels"][-1], "Net Total")
        self.assertAlmostEqual(float(model["running_values"][-1]), -1.5, places=6)

    def test_build_peak_load_analysis_reads_peak_metrics(self) -> None:
        metrics_rows = [
            {"metric_id": "peak_heating", "base_value": 12.2, "scenario_value": 10.8},
            {"metric_id": "peak_cooling", "base_value": 8.4, "scenario_value": 9.1},
        ]

        model = build_peak_load_analysis(metrics_rows)

        self.assertTrue(model["has_data"])
        self.assertAlmostEqual(float(model["peak_heating_base"]), 12.2, places=6)
        self.assertAlmostEqual(float(model["peak_cooling_scenario"]), 9.1, places=6)

    def test_build_seasonal_energy_analysis_groups_monthly_data(self) -> None:
        monthly_model = {
            "months": [
                "Ocak",
                "Subat",
                "Mart",
                "Nisan",
                "Mayis",
                "Haziran",
                "Temmuz",
                "Agustos",
                "Eylul",
                "Ekim",
                "Kasim",
                "Aralik",
            ],
            "base_heating": [100, 90, 80, 70, 60, 50, 40, 30, 20, 30, 60, 90],
            "scenario_heating": [95, 85, 75, 65, 55, 45, 35, 25, 18, 28, 55, 85],
            "base_cooling": [10, 12, 15, 20, 35, 50, 65, 60, 40, 25, 15, 12],
            "scenario_cooling": [9, 10, 13, 18, 32, 48, 61, 58, 36, 22, 13, 10],
            "has_data": True,
            "unit": "kWh",
        }

        model = build_seasonal_energy_analysis(monthly_model)

        self.assertTrue(model["has_data"])
        season_map = {item["season"]: item for item in model["seasons"]}
        self.assertIn("kis", season_map)
        self.assertIn("yaz", season_map)
        self.assertIn("gecis", season_map)
        self.assertGreater(float(season_map["kis"]["base_total"]), 0.0)

    def test_build_structural_impact_view_model_returns_cards_and_graph(self) -> None:
        model = build_structural_impact_view_model(
            {
                "direct_rows": [
                    {
                        "trigger": "Material Conductivity",
                        "dataset": "construction_layers.csv",
                        "affected_row_count": 2,
                    }
                ],
                "indirect_rows": [
                    {
                        "trigger": "Material Conductivity",
                        "dataset": "walls.csv",
                    }
                ],
                "layer_rows": [
                    {
                        "source_row_key": "construction_name=disduvar | layer_index=1 | name=beton",
                        "target_dataset": "construction_layers.csv",
                    }
                ],
            }
        )

        self.assertEqual(model["summary_cards"]["direct_dataset_count"], 1)
        self.assertEqual(model["summary_cards"]["indirect_dataset_count"], 1)
        self.assertEqual(model["summary_cards"]["layer_dataset_count"], 1)
        self.assertEqual(model["summary_cards"]["total_direct_rows"], 2)
        self.assertTrue(model["graph"]["series"][0]["data"])
        dataset_filter_values = {
            node.get("dataset_filter", "")
            for node in model["graph"]["series"][0]["data"]
        }
        self.assertIn("construction_layers.csv", dataset_filter_values)
        self.assertIn("walls.csv", dataset_filter_values)

    def test_filter_structural_impact_rows_filters_by_dataset(self) -> None:
        filtered = filter_structural_impact_rows(
            {
                "direct_rows": [
                    {"dataset": "construction_layers.csv", "affected_row_count": 2},
                    {"dataset": "walls.csv", "affected_row_count": 1},
                ],
                "indirect_rows": [
                    {"dataset": "walls.csv", "row_key": "name=Wall 1"},
                ],
                "layer_rows": [
                    {"target_dataset": "construction_layers.csv", "target_row_key": "x"},
                    {"target_dataset": "walls.csv", "target_row_key": "y"},
                ],
                "surface_impact_rows": [
                    {"dataset": "walls.csv", "surface_name": "Wall 1"},
                    {"dataset": "roofs.csv", "surface_name": "Roof 1"},
                ],
            },
            dataset_filter="walls.csv",
        )

        self.assertEqual(len(filtered["direct_rows"]), 1)
        self.assertEqual(filtered["direct_rows"][0]["dataset"], "walls.csv")
        self.assertEqual(len(filtered["indirect_rows"]), 1)
        self.assertEqual(len(filtered["layer_rows"]), 1)
        self.assertEqual(len(filtered["surface_impact_rows"]), 1)

    def test_summarize_structural_impact_cards_returns_filtered_and_total_counts(self) -> None:
        structural_impact_model = {
            "direct_rows": [
                {"dataset": "construction_layers.csv", "affected_row_count": 2},
                {"dataset": "walls.csv", "affected_row_count": 1},
            ],
            "indirect_rows": [
                {"dataset": "walls.csv", "row_key": "name=Wall 1"},
                {"dataset": "roofs.csv", "row_key": "name=Roof 1"},
            ],
            "layer_rows": [
                {"target_dataset": "construction_layers.csv", "target_row_key": "x"},
                {"target_dataset": "walls.csv", "target_row_key": "y"},
            ],
        }
        filtered_rows = filter_structural_impact_rows(
            structural_impact_model,
            dataset_filter="walls.csv",
        )

        summary = summarize_structural_impact_cards(structural_impact_model, filtered_rows)

        self.assertEqual(summary["direct_dataset_count"]["current"], 1)
        self.assertEqual(summary["direct_dataset_count"]["total"], 2)
        self.assertEqual(summary["indirect_dataset_count"]["current"], 1)
        self.assertEqual(summary["indirect_dataset_count"]["total"], 2)
        self.assertEqual(summary["layer_dataset_count"]["current"], 1)
        self.assertEqual(summary["layer_dataset_count"]["total"], 2)
        self.assertEqual(summary["total_direct_rows"]["current"], 1)
        self.assertEqual(summary["total_direct_rows"]["total"], 3)

    def test_group_layer_impact_rows_by_construction_groups_and_counts(self) -> None:
        groups = group_layer_impact_rows_by_construction(
            [
                {
                    "construction_names": "disduvar",
                    "badge": "Degisen Layer",
                    "layer_name": "disduvar | 1",
                },
                {
                    "construction_names": "disduvar",
                    "badge": "Etkilenen Layer",
                    "layer_name": "disduvar | 2",
                },
                {
                    "construction_names": "icduvar",
                    "badge": "Etkilenen Layer",
                    "layer_name": "icduvar | 1",
                },
            ]
        )

        self.assertEqual(len(groups), 2)
        first_group = next(group for group in groups if group["construction_label"] == "disduvar")
        self.assertEqual(first_group["row_count"], 2)
        self.assertEqual(first_group["changed_count"], 1)
        self.assertEqual(first_group["impacted_count"], 1)
        self.assertEqual(groups[0]["construction_label"], "disduvar")

    def test_build_layer_impact_chart_model_builds_changed_unchanged_and_level(self) -> None:
        chart_model = build_layer_impact_chart_model(
            [
                {
                    "construction_names": "disduvar",
                    "badge": "Degisen Layer",
                    "layer_name": "disduvar | 1",
                },
                {
                    "construction_names": "disduvar",
                    "badge": "Etkilenen Layer",
                    "layer_name": "disduvar | 2",
                },
                {
                    "construction_names": "icduvar",
                    "badge": "Etkilenen Layer",
                    "layer_name": "icduvar | 1",
                },
            ]
        )

        self.assertTrue(chart_model["has_data"])
        self.assertEqual(chart_model["labels"], ["disduvar", "icduvar"])
        self.assertEqual(chart_model["changed_values"], [1, 0])
        self.assertEqual(chart_model["unchanged_values"], [1, 1])
        self.assertEqual(chart_model["impact_levels"], ["Yuksek", "Dusuk"])

    def test_build_cost_comparison_chart_model_old_new_and_savings(self) -> None:
        chart_model = build_cost_comparison_chart_model(
            {
                "base_cost": 1200.0,
                "scenario_cost": 900.0,
            }
        )

        self.assertTrue(chart_model["has_data"])
        self.assertEqual(
            chart_model["labels"],
            ["Old Annual Cost", "New Annual Cost", "Savings"],
        )
        self.assertEqual(chart_model["savings"], 300.0)
        self.assertEqual(chart_model["values"][0]["value"], 1200.0)
        self.assertEqual(chart_model["values"][1]["value"], 900.0)
        self.assertEqual(chart_model["values"][2]["value"], 300.0)

    def test_build_cost_comparison_chart_model_handles_missing_values(self) -> None:
        chart_model = build_cost_comparison_chart_model({"base_cost": None, "scenario_cost": 900.0})

        self.assertFalse(chart_model["has_data"])
        self.assertIsNone(chart_model["savings"])

    def test_build_parameter_recommended_range_text_uses_catalog_min_max(self) -> None:
        parameter = next(
            item for item in list_parameter_definitions() if item.field_name == "thickness_m"
        )

        text = build_parameter_recommended_range_text(parameter)

        self.assertIn("Onerilen aralik", text)
        self.assertIn("0.001", text)
        self.assertIn("1.0", text)

    def test_validate_parameter_new_value_warns_when_out_of_catalog_range(self) -> None:
        parameter = next(
            item for item in list_parameter_definitions() if item.field_name == "thickness_m"
        )

        warnings = validate_parameter_new_value(
            parameter=parameter,
            current_value="0.1",
            new_value="2.5",
        )

        self.assertTrue(any("maksimum" in warning for warning in warnings))

    def test_build_parameter_recommended_range_style_is_green_within_range(self) -> None:
        parameter = next(
            item for item in list_parameter_definitions() if item.field_name == "thickness_m"
        )

        style = build_parameter_recommended_range_style(parameter, "0.2")

        self.assertIn("text-emerald-700", style)

    def test_build_parameter_recommended_range_style_is_red_out_of_range(self) -> None:
        parameter = next(
            item for item in list_parameter_definitions() if item.field_name == "thickness_m"
        )

        style = build_parameter_recommended_range_style(parameter, "2.5")

        self.assertIn("text-rose-700", style)

    def test_build_combined_impact_summary_detects_overlaps(self) -> None:
        summary = build_combined_impact_summary(
            {
                "layer_impact_rows": [
                    {
                        "construction_names": "disduvar",
                        "changed_field": "thickness_m",
                    },
                    {
                        "construction_names": "disduvar",
                        "changed_field": "conductivity_w_per_mk",
                    },
                ],
                "surface_impact_rows": [
                    {
                        "surface_kind": "Wall",
                        "surface_name": "Wall 1",
                        "construction_name": "disduvar",
                        "changed_field": "thickness_m",
                    },
                    {
                        "surface_kind": "Wall",
                        "surface_name": "Wall 1",
                        "construction_name": "disduvar",
                        "changed_field": "conductivity_w_per_mk",
                    },
                ],
            }
        )

        self.assertEqual(summary["changed_field_count"], 2)
        self.assertGreaterEqual(summary["overlapping_group_count"], 2)
        self.assertEqual(summary["tone"], "warning")
        self.assertEqual(summary["overlapping_constructions"][0]["construction_name"], "disduvar")
        self.assertEqual(summary["overlapping_surfaces"][0]["surface_name"], "Wall 1")

    def test_build_runner_status_view_model_marks_progress_and_error(self) -> None:
        rows = build_runner_status_view_model(
            [
                RunnerStatusEvent("hazir", "Hazir", "Beklemede"),
                RunnerStatusEvent("dogrulaniyor", "Dogrulaniyor", "Kontrol"),
                RunnerStatusEvent("senaryo_hazirlaniyor", "Senaryo Hazirlaniyor", "Workspace"),
            ]
        )
        row_by_status = {row["status"]: row for row in rows}
        self.assertEqual(row_by_status["hazir"]["badge"], "Tamam")
        self.assertEqual(row_by_status["dogrulaniyor"]["badge"], "Tamam")
        self.assertEqual(row_by_status["senaryo_hazirlaniyor"]["badge"], "Aktif")
        self.assertEqual(row_by_status["model_guncelleniyor"]["badge"], "Bekliyor")

        error_rows = build_runner_status_view_model(
            [
                {"status": "hazir", "label": "Hazir", "detail": "Baslangic"},
                {"status": "hata", "label": "Hata", "detail": "Beklenmeyen durum"},
            ]
        )
        error_by_status = {row["status"]: row for row in error_rows}
        self.assertEqual(error_by_status["hata"]["tone"], "negative")
        self.assertEqual(error_by_status["hata"]["badge"], "Hata")


if __name__ == "__main__":
    unittest.main()
