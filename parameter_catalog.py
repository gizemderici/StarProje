from dataclasses import dataclass
from typing import Any


DATASET_MATERIALS = "materials.csv"
DATASET_CONSTRUCTIONS = "constructions.csv"
DATASET_CONSTRUCTION_LAYERS = "construction_layers.csv"
DATASET_WALLS = "walls.csv"
DATASET_ROOFS = "roofs.csv"
DATASET_FLOORS = "floors.csv"
DATASET_WINDOWS = "windows.csv"

VALUE_TYPE_STRING = "string"
VALUE_TYPE_INTEGER = "integer"
VALUE_TYPE_FLOAT = "float"

CATEGORY_MATERIALS = "Materials"
CATEGORY_CONSTRUCTIONS = "Constructions"
CATEGORY_WALLS = "Walls"
CATEGORY_ROOFS = "Roofs"
CATEGORY_FLOORS = "Floors"
CATEGORY_WINDOWS = "Windows"
CATEGORY_OPENINGS = "Openings"
CATEGORY_THERMAL_PROPERTIES = "Thermal Properties"
CATEGORY_COST_RELATED = "Cost Related"
CATEGORY_COMFORT_RELATED = "Comfort Related"

CATEGORY_ORDER: tuple[str, ...] = (
    CATEGORY_MATERIALS,
    CATEGORY_CONSTRUCTIONS,
    CATEGORY_WALLS,
    CATEGORY_ROOFS,
    CATEGORY_FLOORS,
    CATEGORY_WINDOWS,
    CATEGORY_OPENINGS,
    CATEGORY_THERMAL_PROPERTIES,
    CATEGORY_COST_RELATED,
    CATEGORY_COMFORT_RELATED,
)


@dataclass(frozen=True)
class ParameterDefinition:
    id: str
    label: str
    dataset: str
    field_name: str
    unit: str | None
    value_type: str
    min_value: float | None
    max_value: float | None
    description: str
    category: str
    example: Any
    affected_entities: tuple[str, ...]
    expected_impacts: tuple[str, ...]


DATASET_KEY_COLUMNS: dict[str, dict[str, str]] = {
    DATASET_MATERIALS: {
        "name": VALUE_TYPE_STRING,
    },
    DATASET_CONSTRUCTIONS: {
        "name": VALUE_TYPE_STRING,
    },
    DATASET_CONSTRUCTION_LAYERS: {
        "construction_name": VALUE_TYPE_STRING,
        "layer_index": VALUE_TYPE_INTEGER,
        "name": VALUE_TYPE_STRING,
    },
    DATASET_WALLS: {
        "name": VALUE_TYPE_STRING,
    },
    DATASET_ROOFS: {
        "name": VALUE_TYPE_STRING,
    },
    DATASET_FLOORS: {
        "name": VALUE_TYPE_STRING,
    },
    DATASET_WINDOWS: {
        "name": VALUE_TYPE_STRING,
    },
}


PARAMETER_DEFINITIONS: tuple[ParameterDefinition, ...] = (
    ParameterDefinition(
        id="material_thickness",
        label="Material Thickness",
        dataset=DATASET_MATERIALS,
        field_name="thickness_m",
        unit="m",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.001,
        max_value=1.0,
        description="Material layer thickness in meters.",
        category=CATEGORY_MATERIALS,
        example=0.05,
        affected_entities=("material",),
        expected_impacts=("u_value", "thermal_mass", "assembly_thickness"),
    ),
    ParameterDefinition(
        id="material_conductivity",
        label="Material Conductivity",
        dataset=DATASET_MATERIALS,
        field_name="conductivity_w_per_mk",
        unit="W/mK",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.01,
        max_value=10.0,
        description="Thermal conductivity of the material.",
        category=CATEGORY_MATERIALS,
        example=0.15,
        affected_entities=("material",),
        expected_impacts=("heat_transfer", "envelope_performance"),
    ),
    ParameterDefinition(
        id="material_thermal_resistance",
        label="Material Thermal Resistance",
        dataset=DATASET_MATERIALS,
        field_name="thermal_resistance_m2k_per_w",
        unit="m2K/W",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.01,
        max_value=20.0,
        description="Thermal resistance for massless or resistance-based materials.",
        category=CATEGORY_MATERIALS,
        example=2.5,
        affected_entities=("material",),
        expected_impacts=("u_value", "heat_loss"),
    ),
    ParameterDefinition(
        id="material_density",
        label="Material Density",
        dataset=DATASET_MATERIALS,
        field_name="density_kg_per_m3",
        unit="kg/m3",
        value_type=VALUE_TYPE_FLOAT,
        min_value=10.0,
        max_value=10000.0,
        description="Density of the material in kilograms per cubic meter.",
        category=CATEGORY_MATERIALS,
        example=1800.0,
        affected_entities=("material",),
        expected_impacts=("thermal_mass", "heat_storage", "weight"),
    ),
    ParameterDefinition(
        id="material_specific_heat",
        label="Material Specific Heat",
        dataset=DATASET_MATERIALS,
        field_name="specific_heat_j_per_kgk",
        unit="J/kgK",
        value_type=VALUE_TYPE_FLOAT,
        min_value=100.0,
        max_value=5000.0,
        description="Specific heat capacity of the material.",
        category=CATEGORY_MATERIALS,
        example=840.0,
        affected_entities=("material",),
        expected_impacts=("thermal_mass", "temperature_response"),
    ),
    ParameterDefinition(
        id="material_thermal_absorptance",
        label="Material Thermal Absorptance",
        dataset=DATASET_MATERIALS,
        field_name="thermal_absorptance",
        unit=None,
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.0,
        max_value=1.0,
        description="Long-wave thermal absorptance of the material surface.",
        category=CATEGORY_MATERIALS,
        example=0.9,
        affected_entities=("material",),
        expected_impacts=("surface_exchange", "radiative_behavior"),
    ),
    ParameterDefinition(
        id="material_solar_absorptance",
        label="Material Solar Absorptance",
        dataset=DATASET_MATERIALS,
        field_name="solar_absorptance",
        unit=None,
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.0,
        max_value=1.0,
        description="Solar absorptance of the material surface.",
        category=CATEGORY_MATERIALS,
        example=0.7,
        affected_entities=("material",),
        expected_impacts=("solar_gain", "surface_temperature"),
    ),
    ParameterDefinition(
        id="material_visible_absorptance",
        label="Material Visible Absorptance",
        dataset=DATASET_MATERIALS,
        field_name="visible_absorptance",
        unit=None,
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.0,
        max_value=1.0,
        description="Visible spectrum absorptance of the material surface.",
        category=CATEGORY_MATERIALS,
        example=0.7,
        affected_entities=("material",),
        expected_impacts=("daylight_reflectance", "surface_optics"),
    ),
    ParameterDefinition(
        id="construction_name",
        label="Construction Name",
        dataset=DATASET_CONSTRUCTIONS,
        field_name="name",
        unit=None,
        value_type=VALUE_TYPE_STRING,
        min_value=None,
        max_value=None,
        description="Identifier used by layers and surfaces to reference a construction.",
        category=CATEGORY_CONSTRUCTIONS,
        example="disduvar_v2",
        affected_entities=("construction", "construction_layer", "wall", "roof", "floor", "window"),
        expected_impacts=("construction_mapping", "surface_assignment"),
    ),
    ParameterDefinition(
        id="construction_layer_index",
        label="Construction Layer Index",
        dataset=DATASET_CONSTRUCTION_LAYERS,
        field_name="layer_index",
        unit=None,
        value_type=VALUE_TYPE_INTEGER,
        min_value=1,
        max_value=50,
        description="Order of the layer within the construction stack.",
        category=CATEGORY_CONSTRUCTIONS,
        example=2,
        affected_entities=("construction_layer",),
        expected_impacts=("layer_order", "assembly_behavior"),
    ),
    ParameterDefinition(
        id="construction_layer_material_name",
        label="Construction Layer Material",
        dataset=DATASET_CONSTRUCTION_LAYERS,
        field_name="name",
        unit=None,
        value_type=VALUE_TYPE_STRING,
        min_value=None,
        max_value=None,
        description="Material assigned to a specific construction layer.",
        category=CATEGORY_CONSTRUCTIONS,
        example="tugla",
        affected_entities=("construction_layer", "material"),
        expected_impacts=("assembly_composition", "thermal_performance"),
    ),
    ParameterDefinition(
        id="construction_layer_thickness",
        label="Construction Layer Thickness",
        dataset=DATASET_CONSTRUCTION_LAYERS,
        field_name="thickness_m",
        unit="m",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.001,
        max_value=1.0,
        description="Thickness of a specific construction layer.",
        category=CATEGORY_CONSTRUCTIONS,
        example=0.08,
        affected_entities=("construction_layer",),
        expected_impacts=("u_value", "assembly_thickness"),
    ),
    ParameterDefinition(
        id="construction_layer_conductivity",
        label="Construction Layer Conductivity",
        dataset=DATASET_CONSTRUCTION_LAYERS,
        field_name="conductivity_w_per_mk",
        unit="W/mK",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.01,
        max_value=10.0,
        description="Thermal conductivity of the material represented on the layer row.",
        category=CATEGORY_CONSTRUCTIONS,
        example=0.15,
        affected_entities=("construction_layer",),
        expected_impacts=("heat_transfer", "envelope_performance"),
    ),
    ParameterDefinition(
        id="construction_layer_thermal_resistance",
        label="Construction Layer Thermal Resistance",
        dataset=DATASET_CONSTRUCTION_LAYERS,
        field_name="thermal_resistance_m2k_per_w",
        unit="m2K/W",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.01,
        max_value=20.0,
        description="Thermal resistance value stored on a specific layer row.",
        category=CATEGORY_CONSTRUCTIONS,
        example=2.5,
        affected_entities=("construction_layer",),
        expected_impacts=("u_value", "heat_loss"),
    ),
    ParameterDefinition(
        id="wall_construction_name",
        label="Wall Construction",
        dataset=DATASET_WALLS,
        field_name="construction_name",
        unit=None,
        value_type=VALUE_TYPE_STRING,
        min_value=None,
        max_value=None,
        description="Construction assigned to a wall surface.",
        category=CATEGORY_WALLS,
        example="disduvar",
        affected_entities=("wall", "construction"),
        expected_impacts=("wall_u_value", "surface_behavior"),
    ),
    ParameterDefinition(
        id="roof_construction_name",
        label="Roof Construction",
        dataset=DATASET_ROOFS,
        field_name="construction_name",
        unit=None,
        value_type=VALUE_TYPE_STRING,
        min_value=None,
        max_value=None,
        description="Construction assigned to a roof or ceiling surface.",
        category=CATEGORY_ROOFS,
        example="cati_yalitimi",
        affected_entities=("roof", "construction"),
        expected_impacts=("roof_u_value", "surface_behavior"),
    ),
    ParameterDefinition(
        id="floor_construction_name",
        label="Floor Construction",
        dataset=DATASET_FLOORS,
        field_name="construction_name",
        unit=None,
        value_type=VALUE_TYPE_STRING,
        min_value=None,
        max_value=None,
        description="Construction assigned to a floor surface.",
        category=CATEGORY_FLOORS,
        example="zemin",
        affected_entities=("floor", "construction"),
        expected_impacts=("floor_u_value", "surface_behavior"),
    ),
    ParameterDefinition(
        id="window_construction_name",
        label="Window Construction",
        dataset=DATASET_WINDOWS,
        field_name="construction_name",
        unit=None,
        value_type=VALUE_TYPE_STRING,
        min_value=None,
        max_value=None,
        description="Construction assigned to a window sub-surface.",
        category=CATEGORY_WINDOWS,
        example="pencere_low_e",
        affected_entities=("window", "construction"),
        expected_impacts=("solar_gain", "window_heat_transfer"),
    ),
    ParameterDefinition(
        id="window_u_factor",
        label="Window U-Factor",
        dataset=DATASET_WINDOWS,
        field_name="u_factor",
        unit="W/m2K",
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.5,
        max_value=6.0,
        description="Thermal transmittance of the window assembly.",
        category=CATEGORY_WINDOWS,
        example=1.8,
        affected_entities=("window",),
        expected_impacts=("heat_loss", "heating_load", "cooling_load"),
    ),
    ParameterDefinition(
        id="window_shgc",
        label="Window SHGC",
        dataset=DATASET_WINDOWS,
        field_name="shgc",
        unit=None,
        value_type=VALUE_TYPE_FLOAT,
        min_value=0.0,
        max_value=1.0,
        description="Solar heat gain coefficient of the window assembly.",
        category=CATEGORY_WINDOWS,
        example=0.4,
        affected_entities=("window",),
        expected_impacts=("solar_gain", "cooling_load", "daylight_balance"),
    ),
)


PARAMETER_CATALOG: dict[str, ParameterDefinition] = {
    parameter.id: parameter for parameter in PARAMETER_DEFINITIONS
}


def get_parameter_definition(parameter_id: str) -> ParameterDefinition | None:
    return PARAMETER_CATALOG.get(parameter_id)


def list_parameter_definitions() -> list[ParameterDefinition]:
    return list(PARAMETER_DEFINITIONS)


def list_parameter_ids() -> list[str]:
    return [parameter.id for parameter in PARAMETER_DEFINITIONS]


def list_categories() -> list[str]:
    return list(CATEGORY_ORDER)


def list_parameters_for_dataset(dataset: str) -> list[ParameterDefinition]:
    return [parameter for parameter in PARAMETER_DEFINITIONS if parameter.dataset == dataset]


def group_parameters_by_category() -> dict[str, list[ParameterDefinition]]:
    grouped: dict[str, list[ParameterDefinition]] = {
        category: [] for category in CATEGORY_ORDER
    }
    for parameter in PARAMETER_DEFINITIONS:
        grouped.setdefault(parameter.category, []).append(parameter)
    return grouped


def build_parameter_groups_for_ui() -> list[dict[str, object]]:
    grouped = group_parameters_by_category()
    return [
        {
            "category": category,
            "parameter_count": len(grouped[category]),
            "parameters": grouped[category],
        }
        for category in CATEGORY_ORDER
    ]


def build_editable_columns_by_dataset() -> dict[str, dict[str, str]]:
    editable_columns: dict[str, dict[str, str]] = {
        dataset: {} for dataset in DATASET_KEY_COLUMNS
    }
    for parameter in PARAMETER_DEFINITIONS:
        editable_columns.setdefault(parameter.dataset, {})
        editable_columns[parameter.dataset][parameter.field_name] = parameter.value_type
    return editable_columns


def build_supported_files() -> dict[str, dict[str, dict[str, str] | set[str]]]:
    editable_columns = build_editable_columns_by_dataset()
    supported_files: dict[str, dict[str, dict[str, str] | set[str]]] = {}
    for dataset, key_columns in DATASET_KEY_COLUMNS.items():
        supported_files[dataset] = {
            "key_columns": set(key_columns),
            "editable_columns": editable_columns.get(dataset, {}),
        }
    return supported_files
