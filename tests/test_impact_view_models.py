import unittest

from nicegui_csv_viewer import (
    build_impact_chart_model,
    build_impact_summary,
    filter_impact_rows,
    format_delta,
)


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


if __name__ == "__main__":
    unittest.main()
