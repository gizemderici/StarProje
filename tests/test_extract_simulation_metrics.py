import unittest

from extract_simulation_metrics import (
    extract_metrics_from_energyplus_table_html,
    extract_metrics_from_csv_rows,
    extract_metrics_from_html_text,
    extract_metrics_from_json_payload,
    extract_metrics_from_mapping,
)


class ExtractSimulationMetricsTests(unittest.TestCase):
    def test_extract_metrics_from_mapping_matches_aliases(self) -> None:
        metrics = extract_metrics_from_mapping(
            {
                "Annual Heating": 1000,
                "annual cooling": 500,
                "ignored_field": "x",
            }
        )

        self.assertEqual(metrics["annual_heating"], 1000)
        self.assertEqual(metrics["annual_cooling"], 500)
        self.assertNotIn("ignored_field", metrics)

    def test_extract_metrics_from_json_payload_finds_nested_metrics_block(self) -> None:
        payload = {
            "report": {
                "summary": {"foo": 1},
                "metrics": {
                    "annual_heating": 900,
                    "annual_cooling": 420,
                    "total_energy": 1320,
                },
            }
        }

        metrics = extract_metrics_from_json_payload(payload)

        self.assertEqual(metrics["annual_heating"], 900)
        self.assertEqual(metrics["annual_cooling"], 420)
        self.assertEqual(metrics["total_energy"], 1320)

    def test_extract_metrics_from_csv_rows_picks_row_with_metric_columns(self) -> None:
        rows = [
            {"name": "beton", "thickness_m": "0.2"},
            {"annual_heating": "1000", "annual_cooling": "550", "total_energy": "1550"},
        ]

        metrics = extract_metrics_from_csv_rows(rows)

        self.assertEqual(metrics["annual_heating"], "1000")
        self.assertEqual(metrics["annual_cooling"], "550")
        self.assertEqual(metrics["total_energy"], "1550")

    def test_extract_metrics_from_html_text_reads_basic_energyplus_style_labels(self) -> None:
        html_text = """
        <html>
          <body>
            <table>
              <tr><td>Annual Heating</td><td>1000.5</td></tr>
              <tr><td>Annual Cooling</td><td>420.0</td></tr>
              <tr><td>Total Energy</td><td>1420.5</td></tr>
              <tr><td>Peak Cooling</td><td>55.2</td></tr>
            </table>
          </body>
        </html>
        """

        metrics = extract_metrics_from_html_text(html_text)

        self.assertEqual(metrics["annual_heating"], "1000.5")
        self.assertEqual(metrics["annual_cooling"], "420.0")
        self.assertEqual(metrics["total_energy"], "1420.5")
        self.assertEqual(metrics["peak_cooling"], "55.2")

    def test_extract_metrics_from_energyplus_table_html_reads_core_metrics(self) -> None:
        html_text = """
        <!-- FullName:Annual Building Utility Performance Summary_Entire Facility_Site and Source Energy-->
        <table>
          <tr><td></td><td>Total Energy [GJ]</td></tr>
          <tr><td>Total Site Energy</td><td>10.0</td></tr>
        </table>
        <!-- FullName:Annual Building Utility Performance Summary_Entire Facility_End Uses-->
        <table>
          <tr><td></td><td>Electricity [GJ]</td><td>Natural Gas [GJ]</td></tr>
          <tr><td>Heating</td><td>1.0</td><td>2.0</td></tr>
          <tr><td>Cooling</td><td>0.5</td><td>0.0</td></tr>
        </table>
        <!-- FullName:Annual Building Utility Performance Summary_Entire Facility_Comfort and Setpoint Not Met Summary-->
        <table>
          <tr><td></td><td>Facility [Hours]</td></tr>
          <tr><td>Time Setpoint Not Met During Occupied Heating</td><td>4.0</td></tr>
          <tr><td>Time Setpoint Not Met During Occupied Cooling</td><td>6.0</td></tr>
        </table>
        <!-- FullName:Demand End Use Components Summary_Entire Facility_End Uses-->
        <table>
          <tr><td></td><td>Electricity [W]</td><td>Natural Gas [W]</td></tr>
          <tr><td>Heating</td><td>1200</td><td>800</td></tr>
          <tr><td>Cooling</td><td>2500</td><td>0</td></tr>
        </table>
        """

        metrics = extract_metrics_from_energyplus_table_html(html_text)

        self.assertAlmostEqual(metrics["total_energy"], 2777.778, places=3)
        self.assertAlmostEqual(metrics["annual_heating"], 833.333, places=3)
        self.assertAlmostEqual(metrics["annual_cooling"], 138.889, places=3)
        self.assertEqual(metrics["unmet_hours"], 10.0)
        self.assertEqual(metrics["peak_heating"], 2.0)
        self.assertEqual(metrics["peak_cooling"], 2.5)


if __name__ == "__main__":
    unittest.main()
