import csv
import json
from pathlib import Path


INPUT_JSON_PATH = "model_data.json"
OUTPUT_DIR = "csv_output"


def load_model_data(json_path: str) -> dict | None:
    path = Path(json_path)
    if not path.exists():
        print(f"JSON dosyasi bulunamadi: {json_path}")
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def ensure_output_dir(output_dir: str) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def normalize_value(value):
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if value is None:
        return ""
    return value


def write_csv(rows: list[dict], output_path: Path) -> None:
    if not rows:
        with output_path.open("w", newline="", encoding="utf-8-sig") as file:
            file.write("")
        return

    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: normalize_value(row.get(key)) for key in fieldnames})


def flatten_construction_layers(constructions: list[dict]) -> list[dict]:
    rows = []
    for construction in constructions:
        construction_name = construction.get("name")
        construction_type = construction.get("type")
        for index, layer in enumerate(construction.get("layers", []), start=1):
            row = {
                "construction_name": construction_name,
                "construction_type": construction_type,
                "layer_index": index,
            }
            row.update(layer)
            rows.append(row)
    return rows


def summary_rows(summary: dict) -> list[dict]:
    return [{"metric": key, "value": value} for key, value in summary.items()]


def export_to_csv(data: dict, output_dir: str) -> list[Path]:
    directory = ensure_output_dir(output_dir)
    exported_files = []

    datasets = {
        "model_summary.csv": summary_rows(data.get("model_summary", {})),
        "zones.csv": data.get("zones", []),
        "walls.csv": data.get("walls", []),
        "roofs.csv": data.get("roofs", []),
        "floors.csv": data.get("floors", []),
        "windows.csv": data.get("windows", []),
        "openings.csv": data.get("openings", []),
        "spaces.csv": data.get("spaces", []),
        "materials.csv": data.get("materials", []),
        "constructions.csv": [
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "layer_count": item.get("layer_count"),
            }
            for item in data.get("constructions", [])
        ],
        "construction_layers.csv": flatten_construction_layers(data.get("constructions", [])),
    }

    for filename, rows in datasets.items():
        output_path = directory / filename
        write_csv(rows, output_path)
        exported_files.append(output_path)

    return exported_files


def main() -> None:
    data = load_model_data(INPUT_JSON_PATH)
    if data is None:
        return

    exported_files = export_to_csv(data, OUTPUT_DIR)
    print("CSV dosyalari olusturuldu:")
    for file_path in exported_files:
        print(f"- {file_path}")


if __name__ == "__main__":
    main()
