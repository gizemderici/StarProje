from __future__ import annotations

from collections.abc import Iterable


PARAMETER_SECTION_LABELS: tuple[str, ...] = (
    "Tum",
    "Material",
    "Construction",
    "Window",
)

PARAMETER_SECTION_CATEGORY_MAP: dict[str, set[str]] = {
    "Tum": set(),
    "Material": {"Materials"},
    "Construction": {"Constructions", "Walls", "Roofs", "Floors"},
    "Window": {"Windows"},
}


def resolve_parameter_section_categories(section_label: str) -> set[str]:
    return set(PARAMETER_SECTION_CATEGORY_MAP.get(section_label, set()))


def resolve_parameter_section_for_category(category_label: str) -> str:
    normalized_category = str(category_label or "").strip()
    if not normalized_category or normalized_category == "Tum Kategoriler":
        return "Tum"

    for section_label, categories in PARAMETER_SECTION_CATEGORY_MAP.items():
        if normalized_category in categories:
            return section_label
    return "Tum"


def resolve_default_category_for_section(section_label: str) -> str:
    normalized_section = str(section_label or "").strip()
    if normalized_section == "Material":
        return "Materials"
    if normalized_section == "Window":
        return "Windows"
    return "Tum Kategoriler"


def filter_parameters_for_section(
    parameters: Iterable[object],
    section_label: str,
) -> list[object]:
    allowed_categories = resolve_parameter_section_categories(section_label)
    if not allowed_categories:
        return list(parameters)
    return [
        parameter
        for parameter in parameters
        if str(getattr(parameter, "category", "")) in allowed_categories
    ]


def build_parameter_section_counts(parameters: Iterable[object]) -> dict[str, int]:
    parameter_list = list(parameters)
    return {
        label: len(filter_parameters_for_section(parameter_list, label))
        for label in PARAMETER_SECTION_LABELS
    }


def build_parameter_card_classes(
    *,
    compact: bool = False,
    selected: bool = False,
    emphasized: bool = False,
) -> str:
    class_names = [
        "w-full",
        "h-full",
        "transition-all",
        "duration-200",
        "bg-white",
        "border",
        "border-slate-200",
        "rounded-2xl",
    ]
    if compact:
        class_names.extend(["shadow-sm", "hover:-translate-y-0.5", "hover:shadow-md"])
    if selected:
        class_names.extend(["bg-sky-50", "border-sky-200", "shadow-md"])
    if emphasized:
        class_names.extend(["ring-2", "ring-sky-300", "shadow-lg"])
    return " ".join(class_names)
