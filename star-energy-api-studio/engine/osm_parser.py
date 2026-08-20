from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HANDLE_RE = re.compile(r"^\{[0-9a-fA-F-]+\}$")


@dataclass(slots=True)
class OsmField:
    value: str
    label: str = ""


@dataclass(slots=True)
class OsmObject:
    object_type: str
    fields: list[OsmField] = field(default_factory=list)

    def by_label(self, label: str, default: str = "") -> str:
        for item in self.fields:
            if item.label == label:
                return item.value
        return default

    @property
    def handle(self) -> str:
        value = self.by_label("Handle")
        if value:
            return value
        return self.fields[0].value if self.fields else ""

    @property
    def name(self) -> str:
        for label in ("Name", "Construction Name", "Material Name"):
            value = self.by_label(label)
            if value and not HANDLE_RE.match(value):
                return value
        if len(self.fields) > 1:
            return self.fields[1].value
        return ""


@dataclass(slots=True)
class MaterialInfo:
    handle: str
    name: str
    material_type: str
    thickness_m: float | None
    conductivity_w_mk: float | None
    density_kg_m3: float | None
    specific_heat_j_kgk: float | None
    thermal_resistance_m2k_w: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "name": self.name,
            "type": self.material_type,
            "thickness_m": self.thickness_m,
            "thickness_cm": round(self.thickness_m * 100, 3)
            if self.thickness_m is not None
            else None,
            "conductivity_w_mk": self.conductivity_w_mk,
            "density_kg_m3": self.density_kg_m3,
            "specific_heat_j_kgk": self.specific_heat_j_kgk,
            "r_value_m2k_w": self.thermal_resistance_m2k_w,
        }


@dataclass(slots=True)
class ConstructionInfo:
    handle: str
    name: str
    layers: list[MaterialInfo | dict[str, str]]
    surface_count: int
    r_layers_m2k_w: float
    r_total_with_films_m2k_w: float
    u_value_w_m2k: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "name": self.name,
            "layers": [
                layer.to_dict() if isinstance(layer, MaterialInfo) else layer
                for layer in self.layers
            ],
            "surface_count": self.surface_count,
            "r_layers_m2k_w": self.r_layers_m2k_w,
            "r_total_with_films_m2k_w": self.r_total_with_films_m2k_w,
            "u_value_w_m2k": self.u_value_w_m2k,
        }


class OsmModel:
    """Legacy compatibility parser; production uses the HTTP/OpenStudio API path."""

    def __init__(self, path: Path, objects: list[OsmObject]) -> None:
        self.path = path
        self.objects = objects
        self.object_counts = Counter(item.object_type for item in objects)
        self._by_handle = {
            item.handle: item for item in objects if item.handle and HANDLE_RE.match(item.handle)
        }
        self.materials = self._materials()
        self.constructions = self._constructions()

    @classmethod
    def load(cls, path: Path) -> "OsmModel":
        if not path.exists():
            raise FileNotFoundError(f"OSM modeli bulunamadı: {path}")
        return cls(path, _parse_objects(path.read_text(encoding="utf-8-sig")))

    @property
    def spaces(self) -> int:
        return self.object_counts.get("OS:Space", 0)

    @property
    def thermal_zones(self) -> int:
        return self.object_counts.get("OS:ThermalZone", 0)

    @property
    def surfaces(self) -> int:
        return self.object_counts.get("OS:Surface", 0)

    @property
    def subsurfaces(self) -> int:
        return self.object_counts.get("OS:SubSurface", 0)

    def find_construction(self, name: str) -> ConstructionInfo | None:
        lowered = name.casefold()
        return next(
            (item for item in self.constructions if item.name.casefold() == lowered), None
        )

    def summary(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "spaces": self.spaces,
            "thermal_zones": self.thermal_zones,
            "surfaces": self.surfaces,
            "subsurfaces": self.subsurfaces,
            "constructions": len(self.constructions),
            "materials": len(self.materials),
            "object_counts": dict(self.object_counts.most_common()),
        }

    def _materials(self) -> dict[str, MaterialInfo]:
        materials: dict[str, MaterialInfo] = {}
        for item in self.objects:
            if item.object_type == "OS:Material":
                thickness = _float(item.by_label("Thickness {m}"))
                conductivity = _float(item.by_label("Conductivity {W/m-K}"))
                resistance = (
                    thickness / conductivity
                    if thickness is not None and conductivity not in (None, 0.0)
                    else None
                )
                info = MaterialInfo(
                    handle=item.handle,
                    name=item.name,
                    material_type=item.object_type,
                    thickness_m=thickness,
                    conductivity_w_mk=conductivity,
                    density_kg_m3=_float(item.by_label("Density {kg/m3}")),
                    specific_heat_j_kgk=_float(item.by_label("Specific Heat {J/kg-K}")),
                    thermal_resistance_m2k_w=round(resistance, 5)
                    if resistance is not None
                    else None,
                )
                materials[item.handle] = info
            elif item.object_type == "OS:Material:NoMass":
                resistance = _float(item.by_label("Thermal Resistance {m2-K/W}"))
                materials[item.handle] = MaterialInfo(
                    handle=item.handle,
                    name=item.name,
                    material_type=item.object_type,
                    thickness_m=None,
                    conductivity_w_mk=None,
                    density_kg_m3=None,
                    specific_heat_j_kgk=None,
                    thermal_resistance_m2k_w=resistance,
                )
        return materials

    def _constructions(self) -> list[ConstructionInfo]:
        surface_counts: Counter[str] = Counter()
        for item in self.objects:
            if item.object_type == "OS:Surface":
                handle = item.by_label("Construction Name")
                if handle:
                    surface_counts[handle] += 1

        constructions: list[ConstructionInfo] = []
        for item in self.objects:
            if item.object_type != "OS:Construction":
                continue
            layer_handles = [
                field.value for field in item.fields if field.label.startswith("Layer ")
            ]
            layers: list[MaterialInfo | dict[str, str]] = []
            r_layers = 0.0
            for handle in layer_handles:
                material = self.materials.get(handle)
                if material is None:
                    referenced = self._by_handle.get(handle)
                    layers.append(
                        {
                            "handle": handle,
                            "name": referenced.name if referenced else "Bilinmeyen katman",
                            "type": referenced.object_type if referenced else "unknown",
                        }
                    )
                    continue
                layers.append(material)
                r_layers += material.thermal_resistance_m2k_w or 0.0
            # Düşey dış duvar için TS/ISO yaklaşımındaki iç+dış yüzey dirençleri.
            r_total = r_layers + 0.13 + 0.04
            u_value = 1.0 / r_total if r_total > 0 else 0.0
            constructions.append(
                ConstructionInfo(
                    handle=item.handle,
                    name=item.name,
                    layers=layers,
                    surface_count=surface_counts[item.handle],
                    r_layers_m2k_w=round(r_layers, 4),
                    r_total_with_films_m2k_w=round(r_total, 4),
                    u_value_w_m2k=round(u_value, 4),
                )
            )
        return sorted(constructions, key=lambda item: item.name.casefold())


def _parse_objects(text: str) -> list[OsmObject]:
    objects: list[OsmObject] = []
    current: OsmObject | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("!"):
            continue
        if current is None:
            if line.startswith("OS:"):
                object_type = line.split(",", 1)[0].strip()
                current = OsmObject(object_type=object_type)
                if ";" in line:
                    objects.append(current)
                    current = None
            continue

        content, _, comment = line.partition("!-")
        content = content.strip()
        label = comment.strip()
        terminates = ";" in content
        value = content.rstrip(",;").strip()
        current.fields.append(OsmField(value=value, label=label))
        if terminates:
            objects.append(current)
            current = None
    return objects


def _float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
