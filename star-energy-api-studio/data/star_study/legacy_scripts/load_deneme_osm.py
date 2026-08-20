import argparse
import csv
from pathlib import Path

import openstudio


DEFAULT_OSM_PATH = Path(r"C:\star\deneme.osm")


def load_model(path: Path) -> openstudio.model.Model:
    vt = openstudio.osversion.VersionTranslator()
    model_optional = vt.loadModel(openstudio.path(str(path)))

    if model_optional.empty():
        raise RuntimeError(f"Model yuklenemedi: {path}")

    return model_optional.get()


def print_names(title: str, items, limit: int = 10):
    print(f"\n{title} ({len(items)} adet)")
    for item in items[:limit]:
        print("-", item.nameString())
    if len(items) > limit:
        print(f"... ve {len(items) - limit} tane daha")


def safe_get(value, default=""):
    try:
        return value()
    except Exception:
        return default


def export_materials_csv(model: openstudio.model.Model, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    materials = model.getMaterials()

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "type",
                "roughness",
                "thickness_m",
                "conductivity_w_mk",
                "density_kg_m3",
                "specific_heat_j_kgk",
            ],
        )
        writer.writeheader()

        for material in materials:
            row = {
                "name": material.nameString(),
                "type": material.iddObjectType().valueName(),
                "roughness": "",
                "thickness_m": "",
                "conductivity_w_mk": "",
                "density_kg_m3": "",
                "specific_heat_j_kgk": "",
            }

            caster = None
            if hasattr(material, "toStandardOpaqueMaterial"):
                caster = material.toStandardOpaqueMaterial()
            elif hasattr(material, "to_StandardOpaqueMaterial"):
                caster = material.to_StandardOpaqueMaterial()

            if caster is not None and caster.is_initialized():
                opaque = caster.get()
                row["roughness"] = safe_get(opaque.roughness)
                row["thickness_m"] = safe_get(opaque.thickness)
                row["conductivity_w_mk"] = safe_get(opaque.conductivity)
                row["density_kg_m3"] = safe_get(opaque.density)
                row["specific_heat_j_kgk"] = safe_get(opaque.specificHeat)

            writer.writerow(row)

    print(f"\nMaterial CSV yazildi: {out_path}")


def find_by_name(title: str, items, query: str):
    query_lower = query.strip().lower()
    matches = [item for item in items if query_lower in item.nameString().lower()]
    print_names(f"{title} icinde arama sonucu: '{query}'", matches, limit=50)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM_PATH, help="Yuklenecek OSM dosya yolu")
    parser.add_argument("--export-materials-csv", type=Path, help="Material listesini CSV olarak kaydeder")
    parser.add_argument("--find-material", help="Material adlarinda arama yapar")
    parser.add_argument("--find-space", help="Space adlarinda arama yapar")
    parser.add_argument("--limit", type=int, default=10, help="Listelerde gosterilecek maksimum oge sayisi")
    args = parser.parse_args()

    osm_path = args.osm
    if not osm_path.exists():
        raise FileNotFoundError(f"OSM dosyasi bulunamadi: {osm_path}")

    model = load_model(osm_path)

    buildings = model.getBuildings()
    spaces = model.getSpaces()
    surfaces = model.getSurfaces()
    constructions = model.getConstructions()
    materials = model.getMaterials()

    print(f"Model yuklendi: {osm_path}")
    print(f"Bina sayisi: {len(buildings)}")
    print(f"Space sayisi: {len(spaces)}")
    print(f"Surface sayisi: {len(surfaces)}")
    print(f"Construction sayisi: {len(constructions)}")
    print(f"Material sayisi: {len(materials)}")

    print_names("Binalar", buildings, limit=args.limit)
    print_names("Space'ler", spaces, limit=args.limit)
    print_names("Surface'ler", surfaces, limit=args.limit)
    print_names("Construction'lar", constructions, limit=args.limit)
    print_names("Material'lar", materials, limit=args.limit)

    if args.find_material:
        find_by_name("Material'lar", materials, args.find_material)

    if args.find_space:
        find_by_name("Space'ler", spaces, args.find_space)

    if args.export_materials_csv:
        export_materials_csv(model, args.export_materials_csv)


if __name__ == "__main__":
    main()
