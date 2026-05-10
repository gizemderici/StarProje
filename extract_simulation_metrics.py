from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
import re
from typing import Any, Mapping

from simulation_results_parser import METRIC_SPECS


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _metric_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for spec in METRIC_SPECS:
        for alias in spec.aliases:
            alias_map[_normalize_key(alias)] = spec.metric_id
    return alias_map


ALIAS_TO_METRIC_ID = _metric_alias_map()

IGNORED_JSON_FILENAMES = {
    "run_metadata.json",
    "scenario_definition.json",
}

IGNORED_JSON_SUFFIXES = (
    "__changes.json",
    "__manifest.json",
    "__comparison.json",
)


def extract_metrics_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, value in mapping.items():
        metric_id = ALIAS_TO_METRIC_ID.get(_normalize_key(str(key)))
        if metric_id:
            metrics[metric_id] = value
    return metrics


def _collect_mapping_candidates(payload: Any) -> list[Mapping[str, Any]]:
    candidates: list[Mapping[str, Any]] = []
    if isinstance(payload, Mapping):
        candidates.append(payload)
        for value in payload.values():
            candidates.extend(_collect_mapping_candidates(value))
    elif isinstance(payload, list):
        for item in payload:
            candidates.extend(_collect_mapping_candidates(item))
    return candidates


def extract_metrics_from_json_payload(payload: Any) -> dict[str, Any]:
    best_metrics: dict[str, Any] = {}
    for candidate in _collect_mapping_candidates(payload):
        extracted = extract_metrics_from_mapping(candidate)
        if len(extracted) > len(best_metrics):
            best_metrics = extracted
    return best_metrics


def extract_metrics_from_csv_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best_metrics: dict[str, Any] = {}
    for row in rows:
        extracted = extract_metrics_from_mapping(row)
        if len(extracted) > len(best_metrics):
            best_metrics = extracted
    return best_metrics


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except OSError:
        return []


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except OSError:
            return ""
        except UnicodeDecodeError:
            continue
    return ""


def extract_metrics_from_html_text(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}

    flattened = html.unescape(re.sub(r"<[^>]+>", " ", text))
    flattened = re.sub(r"\s+", " ", flattened)
    metrics: dict[str, Any] = {}
    for spec in METRIC_SPECS:
        for alias in spec.aliases:
            pattern = re.compile(
                rf"{re.escape(alias)}[^0-9+-]*([+-]?\d+(?:[.,]\d+)?)",
                flags=re.IGNORECASE,
            )
            match = pattern.search(flattened)
            if match:
                metrics[spec.metric_id] = match.group(1).replace(",", ".")
                break
    return metrics


def _extract_html_table_after_marker(text: str, marker: str) -> str:
    marker_index = text.find(marker)
    if marker_index == -1:
        return ""
    table_start = text.find("<table", marker_index)
    if table_start == -1:
        return ""
    table_end = text.find("</table>", table_start)
    if table_end == -1:
        return ""
    return text[table_start : table_end + len("</table>")]


def _parse_html_table(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
        row_html = row_match.group(1)
        cells = [
            re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell_html))).strip()
            for cell_html in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        ]
        if cells:
            rows.append(cells)
    return rows


def _try_float(value: str) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text or text in {"-", "NA", "N/A", "None", "\xa0"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _sum_numeric_cells(cells: list[str]) -> float:
    total = 0.0
    for cell in cells:
        number = _try_float(cell)
        if number is not None:
            total += number
    return total


def extract_metrics_from_energyplus_table_html(text: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}

    site_energy_table = _extract_html_table_after_marker(
        text,
        "FullName:Annual Building Utility Performance Summary_Entire Facility_Site and Source Energy",
    )
    site_energy_rows = _parse_html_table(site_energy_table)
    for row in site_energy_rows:
        if len(row) >= 2 and row[0] == "Total Site Energy":
            total_site_energy_gj = _try_float(row[1])
            if total_site_energy_gj is not None:
                metrics["total_energy"] = round(total_site_energy_gj * 277.777778, 3)
            break

    end_uses_table = _extract_html_table_after_marker(
        text,
        "FullName:Annual Building Utility Performance Summary_Entire Facility_End Uses",
    )
    end_use_rows = _parse_html_table(end_uses_table)
    for row in end_use_rows:
        if not row:
            continue
        label = row[0]
        energy_sum_gj = _sum_numeric_cells(row[1:])
        if label == "Heating":
            metrics["annual_heating"] = round(energy_sum_gj * 277.777778, 3)
        elif label == "Cooling":
            metrics["annual_cooling"] = round(energy_sum_gj * 277.777778, 3)

    unmet_table = _extract_html_table_after_marker(
        text,
        "FullName:Annual Building Utility Performance Summary_Entire Facility_Comfort and Setpoint Not Met Summary",
    )
    unmet_rows = _parse_html_table(unmet_table)
    heating_unmet = 0.0
    cooling_unmet = 0.0
    for row in unmet_rows:
        if len(row) >= 2 and row[0] == "Time Setpoint Not Met During Occupied Heating":
            heating_unmet = _try_float(row[1]) or 0.0
        elif len(row) >= 2 and row[0] == "Time Setpoint Not Met During Occupied Cooling":
            cooling_unmet = _try_float(row[1]) or 0.0
    if heating_unmet or cooling_unmet:
        metrics["unmet_hours"] = round(heating_unmet + cooling_unmet, 3)

    demand_table = _extract_html_table_after_marker(
        text,
        "FullName:Demand End Use Components Summary_Entire Facility_End Uses",
    )
    demand_rows = _parse_html_table(demand_table)
    for row in demand_rows:
        if not row:
            continue
        label = row[0]
        power_sum_watts = _sum_numeric_cells(row[1:])
        if label == "Heating":
            metrics["peak_heating"] = round(power_sum_watts / 1000.0, 3)
        elif label == "Cooling":
            metrics["peak_cooling"] = round(power_sum_watts / 1000.0, 3)

    return metrics


def discover_simulation_metrics_payload(results_dir: Path) -> dict[str, Any] | None:
    root = Path(results_dir)
    if not root.exists():
        return None

    best_candidate: dict[str, Any] | None = None

    for json_path in sorted(root.glob("*.json")):
        if json_path.name in IGNORED_JSON_FILENAMES or any(
            json_path.name.endswith(suffix) for suffix in IGNORED_JSON_SUFFIXES
        ):
            continue
        payload = _read_json_file(json_path)
        if payload is None:
            continue
        metrics = extract_metrics_from_json_payload(payload)
        if not metrics:
            continue
        candidate = {
            "metrics": metrics,
            "source_type": "json_scan",
            "source_path": json_path.as_posix(),
        }
        if best_candidate is None or len(candidate["metrics"]) > len(best_candidate["metrics"]):
            best_candidate = candidate

    for csv_path in sorted(root.glob("*.csv")):
        rows = _read_csv_rows(csv_path)
        metrics = extract_metrics_from_csv_rows(rows)
        if not metrics:
            continue
        candidate = {
            "metrics": metrics,
            "source_type": "csv_scan",
            "source_path": csv_path.as_posix(),
        }
        if best_candidate is None or len(candidate["metrics"]) > len(best_candidate["metrics"]):
            best_candidate = candidate

    for html_path in sorted([*root.glob("*.htm"), *root.glob("*.html")]):
        text = _read_text_file(html_path)
        metrics = extract_metrics_from_energyplus_table_html(text)
        if not metrics:
            metrics = extract_metrics_from_html_text(text)
        if not metrics:
            continue
        candidate = {
            "metrics": metrics,
            "source_type": "html_scan",
            "source_path": html_path.as_posix(),
        }
        if best_candidate is None or len(candidate["metrics"]) > len(best_candidate["metrics"]):
            best_candidate = candidate

    return best_candidate


def write_simulation_metrics_payload(results_dir: Path, output_path: Path | None = None) -> Path | None:
    payload = discover_simulation_metrics_payload(results_dir)
    if payload is None:
        return None

    target = Path(output_path) if output_path else Path(results_dir) / "simulation_metrics.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenStudio/EnergyPlus sonuc klasorunden ortak simulation_metrics.json dosyasi uretir."
    )
    parser.add_argument("--results-dir", required=True, help="Sonuc klasoru yolu.")
    parser.add_argument("--output", help="Uretilecek simulation_metrics.json yolu.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written = write_simulation_metrics_payload(Path(args.results_dir), Path(args.output) if args.output else None)
    if written is None:
        print("Simulation metrics bulunamadi.")
        return 1
    print(f"Simulation metrics yazildi: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
