import json
from pathlib import Path

import openstudio as openstudio


OSM_PATH = r"C:\star\deneme.osm"
OUTPUT_JSON_PATH = "model_data.json"


def load_model(osm_path: str):
    if not Path(osm_path).exists():
        print(f"OSM dosyasi bulunamadi: {osm_path}")
        return None

    translator = openstudio.osversion.VersionTranslator()
    model_optional = translator.loadModel(openstudio.path(osm_path))
    if not model_optional.is_initialized():
        print(f"Model yuklenemedi: {osm_path}")
        return None
    return model_optional.get()


def safe_name(item) -> str:
    name = item.name()
    if hasattr(name, "is_initialized") and name.is_initialized():
        return name.get()
    return str(name)


def optional_number(value):
    if hasattr(value, "is_initialized"):
        if not value.is_initialized():
            return None
        return value.get()
    return value


def format_number(value, digits: int = 2) -> str:
    number = optional_number(value)
    if number is None:
        return "N/A"
    return str(round(number, digits))


def rounded_number(value, digits: int = 2):
    number = optional_number(value)
    if number is None:
        return None
    return round(number, digits)


def zone_to_dict(zone) -> dict:
    spaces = zone.spaces()
    return {
        "name": safe_name(zone),
        "space_count": len(spaces),
        "space_names": [safe_name(space) for space in spaces],
        "floor_area_m2": rounded_number(zone.floorArea()),
        "volume_m3": rounded_number(zone.volume()),
    }


def wall_to_dict(wall) -> dict:
    space = optional_number(wall.space())
    construction = optional_number(wall.construction())
    return {
        "name": safe_name(wall),
        "surface_type": wall.surfaceType(),
        "gross_area_m2": rounded_number(wall.grossArea()),
        "outside_boundary_condition": wall.outsideBoundaryCondition(),
        "azimuth_rad": rounded_number(wall.azimuth()),
        "space_name": safe_name(space) if space is not None else None,
        "construction_name": safe_name(construction) if construction is not None else None,
    }


def window_to_dict(window) -> dict:
    surface = optional_number(window.surface())
    construction = optional_number(window.construction())
    return {
        "name": safe_name(window),
        "sub_surface_type": window.subSurfaceType(),
        "gross_area_m2": rounded_number(window.grossArea()),
        "host_surface_name": safe_name(surface) if surface is not None else None,
        "construction_name": safe_name(construction) if construction is not None else None,
    }


def space_to_dict(space) -> dict:
    thermal_zone = optional_number(space.thermalZone())
    return {
        "name": safe_name(space),
        "floor_area_m2": rounded_number(space.floorArea()),
        "volume_m3": rounded_number(space.volume()),
        "thermal_zone_name": safe_name(thermal_zone) if thermal_zone is not None else None,
    }


def material_summary(material) -> str:
    parts = [f"Tip: {material.iddObjectType().valueName()}"]

    if material.to_StandardOpaqueMaterial().is_initialized():
        opaque = material.to_StandardOpaqueMaterial().get()
        parts.append(f"Kalinlik (m): {round(opaque.thickness(), 4)}")
        parts.append(f"Iletkenlik: {round(opaque.conductivity(), 4)}")
    elif material.to_MasslessOpaqueMaterial().is_initialized():
        massless = material.to_MasslessOpaqueMaterial().get()
        parts.append(f"Thermal Resistance: {round(massless.thermalResistance(), 4)}")
    elif material.to_SimpleGlazing().is_initialized():
        glazing = material.to_SimpleGlazing().get()
        parts.append(f"U-Factor: {round(glazing.uFactor(), 4)}")
        parts.append(f"SHGC: {round(glazing.solarHeatGainCoefficient(), 4)}")

    return ", ".join(parts)


def material_to_dict(material) -> dict:
    data = {
        "name": safe_name(material),
        "type": material.iddObjectType().valueName(),
    }

    if material.to_StandardOpaqueMaterial().is_initialized():
        opaque = material.to_StandardOpaqueMaterial().get()
        data["thickness_m"] = rounded_number(opaque.thickness(), 4)
        data["conductivity_w_per_mk"] = rounded_number(opaque.conductivity(), 4)
    elif material.to_MasslessOpaqueMaterial().is_initialized():
        massless = material.to_MasslessOpaqueMaterial().get()
        data["thermal_resistance_m2k_per_w"] = rounded_number(massless.thermalResistance(), 4)
    elif material.to_SimpleGlazing().is_initialized():
        glazing = material.to_SimpleGlazing().get()
        data["u_factor_w_per_m2k"] = rounded_number(glazing.uFactor(), 4)
        data["shgc"] = rounded_number(glazing.solarHeatGainCoefficient(), 4)

    return data


def get_construction_layers(construction):
    if hasattr(construction, "layers"):
        try:
            return construction.layers()
        except Exception:
            pass

    if hasattr(construction, "to_LayeredConstruction"):
        layered = construction.to_LayeredConstruction()
        if hasattr(layered, "is_initialized") and layered.is_initialized():
            return layered.get().layers()

    if hasattr(construction, "to_Construction"):
        standard = construction.to_Construction()
        if hasattr(standard, "is_initialized") and standard.is_initialized():
            return standard.get().layers()

    return []


def construction_to_dict(construction) -> dict:
    layers = get_construction_layers(construction)
    return {
        "name": safe_name(construction),
        "type": construction.iddObjectType().valueName(),
        "layer_count": len(layers),
        "layers": [material_to_dict(layer) for layer in layers],
    }


def export_model_data(model) -> dict:
    zones = model.getThermalZones()
    walls = [surface for surface in model.getSurfaces() if surface.surfaceType() == "Wall"]
    window_types = {"FixedWindow", "OperableWindow", "Skylight"}
    windows = [sub_surface for sub_surface in model.getSubSurfaces() if sub_surface.subSurfaceType() in window_types]
    spaces = model.getSpaces()
    materials = model.getMaterials()
    constructions = model.getConstructions()

    return {
        "model_summary": {
            "openstudio_version": openstudio.openStudioVersion(),
            "zone_count": len(zones),
            "wall_count": len(walls),
            "window_count": len(windows),
            "space_count": len(spaces),
            "material_count": len(materials),
            "construction_count": len(constructions),
            "total_floor_area_m2": round(sum(optional_number(space.floorArea()) or 0.0 for space in spaces), 2),
            "total_volume_m3": round(sum(optional_number(space.volume()) or 0.0 for space in spaces), 2),
        },
        "zones": [zone_to_dict(zone) for zone in zones],
        "walls": [wall_to_dict(wall) for wall in walls],
        "windows": [window_to_dict(window) for window in windows],
        "spaces": [space_to_dict(space) for space in spaces],
        "materials": [material_to_dict(material) for material in materials],
        "constructions": [construction_to_dict(construction) for construction in constructions],
    }


def write_json(data: dict, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def print_zones(model) -> None:
    zones = model.getThermalZones()
    print("\n=== ZONES ===")
    print("Toplam zone sayisi:", len(zones))

    for zone in zones:
        spaces = zone.spaces()
        print(f"- Zone: {safe_name(zone)}")
        print("  Bagli space sayisi:", len(spaces))
        print("  Toplam alan (m2):", format_number(zone.floorArea()))
        print("  Hacim (m3):", format_number(zone.volume()))


def print_walls(model) -> None:
    walls = [surface for surface in model.getSurfaces() if surface.surfaceType() == "Wall"]
    print("\n=== DUVARLAR ===")
    print("Toplam duvar sayisi:", len(walls))

    for wall in walls[:20]:
        print(f"- Duvar: {safe_name(wall)}")
        print("  Alan (m2):", format_number(wall.grossArea()))
        print("  Dis sinir kosulu:", wall.outsideBoundaryCondition())
        print("  Azimut:", format_number(wall.azimuth()))

    if len(walls) > 20:
        print(f"... {len(walls) - 20} adet duvar daha var")


def print_windows(model) -> None:
    window_types = {"FixedWindow", "OperableWindow", "Skylight"}
    windows = [sub_surface for sub_surface in model.getSubSurfaces() if sub_surface.subSurfaceType() in window_types]

    print("\n=== PENCERELER ===")
    print("Toplam pencere sayisi:", len(windows))

    for window in windows[:20]:
        print(f"- Pencere: {safe_name(window)}")
        print("  Tip:", window.subSurfaceType())
        print("  Alan (m2):", format_number(window.grossArea()))

    if len(windows) > 20:
        print(f"... {len(windows) - 20} adet pencere daha var")


def print_areas(model) -> None:
    spaces = model.getSpaces()
    total_floor_area = sum(optional_number(space.floorArea()) or 0.0 for space in spaces)
    total_volume = sum(optional_number(space.volume()) or 0.0 for space in spaces)

    print("\n=== ALANLAR ===")
    print("Toplam space sayisi:", len(spaces))
    print("Toplam taban alani (m2):", round(total_floor_area, 2))
    print("Toplam hacim (m3):", round(total_volume, 2))

    for space in spaces[:20]:
        print(f"- Space: {safe_name(space)}")
        print("  Alan (m2):", format_number(space.floorArea()))
        print("  Hacim (m3):", format_number(space.volume()))

    if len(spaces) > 20:
        print(f"... {len(spaces) - 20} adet space daha var")


def print_materials(model) -> None:
    materials = model.getMaterials()
    print("\n=== MALZEMELER ===")
    print("Toplam malzeme sayisi:", len(materials))

    for material in materials[:20]:
        print(f"- Malzeme: {safe_name(material)}")
        print("  " + material_summary(material))

    if len(materials) > 20:
        print(f"... {len(materials) - 20} adet malzeme daha var")


def print_constructions(model) -> None:
    constructions = model.getConstructions()
    print("\n=== CONSTRUCTIONS ===")
    print("Toplam construction sayisi:", len(constructions))

    for construction in constructions[:20]:
        layers = get_construction_layers(construction)
        layer_names = [safe_name(layer) for layer in layers]
        print(f"- Construction: {safe_name(construction)}")
        print("  Tip:", construction.iddObjectType().valueName())
        print("  Katman sayisi:", len(layers))
        print("  Katmanlar:", ", ".join(layer_names) if layer_names else "N/A")

    if len(constructions) > 20:
        print(f"... {len(constructions) - 20} adet construction daha var")


def main() -> None:
    model = load_model(OSM_PATH)
    if model is None:
        print("Model yuklenemedi")
        return

    model_data = export_model_data(model)

    print("Model yuklendi")
    print("OpenStudio surumu:", openstudio.openStudioVersion())
    print_zones(model)
    print_walls(model)
    print_windows(model)
    print_areas(model)
    print_materials(model)
    print_constructions(model)
    write_json(model_data, OUTPUT_JSON_PATH)
    print(f"\nJSON dosyasi olusturuldu: {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    main()
