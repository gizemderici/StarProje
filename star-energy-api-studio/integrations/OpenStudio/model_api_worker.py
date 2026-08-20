"""Executed by OpenStudio CLI's embedded Python runtime.

This is the only component that opens an OSM model. It uses the official
OpenStudio SDK API and emits a JSON projection for the HTTP service layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import openstudio


def _material_payload(material) -> dict[str, object]:
    payload: dict[str, object] = {
        "handle": str(material.handle()),
        "name": material.nameString(),
        "type": str(material.iddObjectType().valueName()).replace("OS_", "OS:"),
        "thickness_m": None,
        "conductivity_w_mk": None,
        "density_kg_m3": None,
        "specific_heat_j_kgk": None,
        "r_value_m2k_w": None,
    }

    standard = material.to_StandardOpaqueMaterial()
    if standard.is_initialized():
        item = standard.get()
        payload.update(
            thickness_m=float(item.thickness()),
            conductivity_w_mk=float(item.conductivity()),
            density_kg_m3=float(item.density()),
            specific_heat_j_kgk=float(item.specificHeat()),
            r_value_m2k_w=float(item.thermalResistance()),
        )
        return payload

    massless = material.to_MasslessOpaqueMaterial()
    if massless.is_initialized():
        payload["r_value_m2k_w"] = float(massless.get().thermalResistance())
        return payload

    air_gap = material.to_AirGap()
    if air_gap.is_initialized():
        payload["r_value_m2k_w"] = float(air_gap.get().thermalResistance())
    return payload


def export_model(osm_path: Path) -> dict[str, object]:
    translator = openstudio.osversion.VersionTranslator()
    optional_model = translator.loadModel(openstudio.path(str(osm_path)))
    if optional_model.empty():
        raise RuntimeError(f"OpenStudio modeli açamadı: {osm_path}")
    model = optional_model.get()

    surfaces = list(model.getSurfaces())
    zones = []
    for zone in model.getThermalZones():
        zone_spaces = list(zone.spaces())
        zone_surfaces = [
            surface for space in zone_spaces for surface in space.surfaces()
        ]
        window_area = sum(
            float(subsurface.grossArea())
            for surface in zone_surfaces
            for subsurface in surface.subSurfaces()
            if subsurface.subSurfaceType() in {"FixedWindow", "OperableWindow", "GlassDoor"}
        )
        zones.append(
            {
                "zone": zone.nameString(),
                "conditioned": "Evet"
                if zone.thermostatSetpointDualSetpoint().is_initialized()
                else "Hayır",
                "area_m2": round(sum(float(space.floorArea()) for space in zone_spaces), 2),
                "volume_m3": round(sum(float(space.volume()) for space in zone_spaces), 2),
                "window_area_m2": round(window_area, 2),
                "lighting_w_m2": None,
            }
        )
    materials: dict[str, dict[str, object]] = {}
    constructions: list[dict[str, object]] = []
    for construction in model.getConstructions():
        layer_payloads = []
        for layer in construction.layers():
            material = _material_payload(layer)
            materials[str(material["handle"])] = material
            layer_payloads.append(material)

        r_layers = sum(
            float(layer["r_value_m2k_w"] or 0.0) for layer in layer_payloads
        )
        r_total = r_layers + 0.13 + 0.04
        resolved_surfaces = [
            surface
            for surface in surfaces
            if surface.construction().is_initialized()
            and surface.construction().get().handle() == construction.handle()
        ]
        constructions.append(
            {
                "handle": str(construction.handle()),
                "name": construction.nameString(),
                "layers": layer_payloads,
                "surface_count": sum(
                    1 for surface in resolved_surfaces if not surface.isConstructionDefaulted()
                ),
                "resolved_surface_count": len(resolved_surfaces),
                "r_layers_m2k_w": round(r_layers, 5),
                "r_total_with_films_m2k_w": round(r_total, 5),
                "u_value_w_m2k": round(1.0 / r_total, 5) if r_total else 0.0,
            }
        )

    return {
        "source": "openstudio-sdk",
        "openstudio_version": openstudio.openStudioVersion(),
        "building_name": model.getBuilding().nameString(),
        "spaces": len(model.getSpaces()),
        "thermal_zones": len(model.getThermalZones()),
        "surfaces": len(surfaces),
        "subsurfaces": len(model.getSubSurfaces()),
        "zones": sorted(zones, key=lambda item: item["zone"].casefold()),
        "constructions": sorted(constructions, key=lambda item: item["name"].casefold()),
        "materials": list(materials.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = export_model(Path(args.osm).resolve())
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
