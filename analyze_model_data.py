import json
from collections import Counter
from pathlib import Path


INPUT_JSON_PATH = "model_data.json"


def load_model_data(json_path: str) -> dict | None:
    path = Path(json_path)
    if not path.exists():
        print(f"JSON dosyasi bulunamadi: {json_path}")
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sum_area(items: list[dict], key: str, filter_key: str | None = None, filter_value: str | None = None) -> float:
    total = 0.0
    for item in items:
        if filter_key is not None and item.get(filter_key) != filter_value:
            continue
        total += item.get(key) or 0.0
    return round(total, 2)


def print_model_summary(data: dict) -> None:
    summary = data.get("model_summary", {})
    print("=== MODEL OZETI ===")
    print("OpenStudio surumu:", summary.get("openstudio_version", "N/A"))
    print("Zone sayisi:", summary.get("zone_count", 0))
    print("Space sayisi:", summary.get("space_count", 0))
    print("Duvar sayisi:", summary.get("wall_count", 0))
    print("Cati sayisi:", summary.get("roof_count", 0))
    print("Doseme sayisi:", summary.get("floor_count", 0))
    print("Pencere sayisi:", summary.get("window_count", 0))
    print("Aciklik sayisi:", summary.get("opening_count", 0))
    print("Malzeme sayisi:", summary.get("material_count", 0))
    print("Construction sayisi:", summary.get("construction_count", 0))
    print("Toplam taban alani (m2):", summary.get("total_floor_area_m2", 0))
    print("Toplam hacim (m3):", summary.get("total_volume_m3", 0))


def print_area_report(data: dict) -> None:
    walls = data.get("walls", [])
    windows = data.get("windows", [])
    spaces = data.get("spaces", [])
    roofs = data.get("roofs", [])
    floors = data.get("floors", [])

    outdoor_wall_area = sum_area(walls, "gross_area_m2", "element_class", "dis_duvar")
    indoor_wall_area = sum_area(walls, "gross_area_m2", "element_class", "ic_duvar")
    roof_area = sum_area(roofs, "gross_area_m2", "element_class", "cati")
    floor_area = sum_area(floors, "gross_area_m2")
    total_window_area = sum_area(windows, "gross_area_m2", "element_class", "dis_pencere")
    total_space_area = sum_area(spaces, "floor_area_m2")

    print("\n=== ALAN RAPORU ===")
    print("Toplam space alani (m2):", total_space_area)
    print("Toplam dis duvar alani (m2):", outdoor_wall_area)
    print("Toplam ic duvar alani (m2):", indoor_wall_area)
    print("Toplam cati alani (m2):", roof_area)
    print("Toplam doseme alani (m2):", floor_area)
    print("Toplam dis pencere alani (m2):", total_window_area)


def print_classification_report(data: dict) -> None:
    surface_items = data.get("walls", []) + data.get("roofs", []) + data.get("floors", [])
    opening_items = data.get("openings", [])
    surface_counter = Counter(item.get("element_class", "bilinmiyor") for item in surface_items)
    opening_counter = Counter(item.get("element_class", "bilinmiyor") for item in opening_items)

    print("\n=== ELEMAN SINIFLANDIRMA OZETI ===")
    print("Yuzey siniflari:")
    for class_name, count in sorted(surface_counter.items()):
        print(f"- {class_name}: {count}")

    print("Aciklik siniflari:")
    for class_name, count in sorted(opening_counter.items()):
        print(f"- {class_name}: {count}")


def print_zone_report(data: dict) -> None:
    zones = data.get("zones", [])

    print("\n=== ZONE OZETI ===")
    for zone in zones:
        print(
            f"- {zone.get('name', 'N/A')}: "
            f"alan={zone.get('floor_area_m2', 'N/A')} m2, "
            f"space_sayisi={zone.get('space_count', 0)}"
        )


def print_construction_report(data: dict) -> None:
    constructions = data.get("constructions", [])
    walls = data.get("walls", [])
    windows = data.get("windows", [])

    construction_usage = Counter()
    for wall in walls:
        if wall.get("construction_name"):
            construction_usage[wall["construction_name"]] += 1
    for window in windows:
        if window.get("construction_name"):
            construction_usage[window["construction_name"]] += 1

    print("\n=== CONSTRUCTION OZETI ===")
    for construction in constructions:
        name = construction.get("name", "N/A")
        layer_count = construction.get("layer_count", 0)
        usage_count = construction_usage.get(name, 0)
        print(f"- {name}: katman_sayisi={layer_count}, kullanim_sayisi={usage_count}")


def print_material_usage_report(data: dict) -> None:
    constructions = data.get("constructions", [])
    material_counter = Counter()

    for construction in constructions:
        for layer in construction.get("layers", []):
            material_name = layer.get("name")
            if material_name:
                material_counter[material_name] += 1

    print("\n=== MALZEME KULLANIM OZETI ===")
    for material_name, count in material_counter.most_common(10):
        print(f"- {material_name}: {count} construction katmaninda geciyor")


def main() -> None:
    data = load_model_data(INPUT_JSON_PATH)
    if data is None:
        return

    print_model_summary(data)
    print_area_report(data)
    print_classification_report(data)
    print_zone_report(data)
    print_construction_report(data)
    print_material_usage_report(data)


if __name__ == "__main__":
    main()
