from dataclasses import dataclass
from pathlib import Path
import re

from parameter_catalog import ParameterDefinition
from update_csv_fields import CsvUpdateError, validate_value


@dataclass(frozen=True)
class SelectedParameterChange:
    parameter: ParameterDefinition
    current_value: str
    new_value: str
    record_label: str
    record_choice: dict[str, object] | None


def generate_scenario_name(dataset: str, parameter_ids: list[str]) -> str:
    dataset_stem = Path(dataset).stem or "scenario"
    compact_ids = "_".join(parameter_ids[:3]) if parameter_ids else "draft"
    raw_name = f"{dataset_stem}_{compact_ids}"
    return sanitize_scenario_name(raw_name)


def sanitize_scenario_name(value: str) -> str:
    normalized_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return normalized_name.strip("_") or "parameter_selection_draft"


def build_change_list(
    selected_changes: list[SelectedParameterChange],
) -> tuple[list[dict[str, object]], list[str]]:
    change_list = []
    errors: list[str] = []
    seen_targets: set[tuple[str, str, str, str]] = set()

    for item in selected_changes:
        record_choice = item.record_choice
        if not isinstance(record_choice, dict):
            errors.append(f"{item.parameter.label} icin once bir kayit secin.")
            continue
        if not item.new_value.strip():
            errors.append(f"{item.parameter.label} icin yeni deger girilmedi.")
            continue
        if item.new_value.strip() == item.current_value.strip():
            errors.append(
                f"{item.parameter.label} icin yeni deger mevcut deger ile ayni; farkli bir deger girin."
            )
            continue

        try:
            validate_value(item.new_value, item.parameter.value_type, item.parameter.field_name)
        except CsvUpdateError as error:
            errors.append(str(error))
            continue

        target_key = (
            str(item.parameter.dataset),
            str(record_choice.get("match_column", "name")),
            str(record_choice.get("match_value", "")),
            str(item.parameter.field_name),
        )
        if target_key in seen_targets:
            errors.append(
                f"{item.parameter.label} icin ayni kayit ve alan birden fazla kez secildi."
            )
            continue
        seen_targets.add(target_key)

        change_item = {
            "parameter_id": item.parameter.id,
            "label": item.parameter.label,
            "dataset": item.parameter.dataset,
            "field_name": item.parameter.field_name,
            "old_value": item.current_value,
            "new_value": item.new_value,
            "unit": item.parameter.unit or "-",
            "category": item.parameter.category,
            "record_label": item.record_label,
            "match": {
                "column": str(record_choice.get("match_column", "name")),
                "value": str(record_choice.get("match_value", "")),
            },
            "extra_match": record_choice.get("extra_matches", {}),
        }
        change_list.append(change_item)

    return change_list, errors


def build_scenario_from_selected_changes(
    selected_changes: list[SelectedParameterChange],
    scenario_name: str = "",
    description: str = "",
) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
    if not selected_changes:
        return None, [], ["Taslak olusturmak icin once en az bir parametre secin."]

    datasets = sorted({item.parameter.dataset for item in selected_changes})
    if len(datasets) != 1:
        return None, [], [
            "Secili parametreler birden fazla veri setinden geliyor. Ilk surum taslagi tek veri seti ile sinirlidir."
        ]

    change_list, errors = build_change_list(selected_changes)
    if errors:
        return None, change_list, errors

    final_scenario_name = sanitize_scenario_name(
        scenario_name or generate_scenario_name(datasets[0], [item.parameter.id for item in selected_changes])
    )
    if len(final_scenario_name) > 80:
        return None, change_list, [
            "Senaryo adi cok uzun. Daha kisa ve anlasilir bir ad kullanin."
        ]
    operations = []
    for change in change_list:
        operation = {
            "name": f"set_{change['parameter_id']}",
            "match": change["match"],
            "updates": {
                str(change["field_name"]): str(change["new_value"]),
            },
            "meta": {
                "parameter_id": change["parameter_id"],
                "label": change["label"],
                "dataset": change["dataset"],
                "category": change["category"],
                "unit": change["unit"],
                "current_value": change["old_value"],
                "record_label": change["record_label"],
                "record_selection_required": False,
            },
        }
        extra_match = change.get("extra_match", {})
        if isinstance(extra_match, dict) and extra_match:
            operation["extra_match"] = extra_match
        operations.append(operation)

    scenario = {
        "scenario_name": final_scenario_name,
        "description": description.strip(),
        "input": f"csv_output/{datasets[0]}",
        "output": f"simulation_outputs/{final_scenario_name}/{final_scenario_name}__{Path(datasets[0]).stem}.csv",
        "log_output": f"simulation_outputs/{final_scenario_name}/{final_scenario_name}__changes.json",
        "changes": change_list,
        "operations": operations,
    }
    return scenario, change_list, []


def build_apply_scenario_definition_payload(scenario: dict[str, object]) -> dict[str, object]:
    operations = []
    for operation in scenario.get("operations", []):
        if not isinstance(operation, dict):
            continue
        compatible_operation = {
            "name": operation.get("name"),
            "match": operation.get("match", {}),
            "updates": operation.get("updates", {}),
        }
        extra_match = operation.get("extra_match")
        if isinstance(extra_match, dict) and extra_match:
            compatible_operation["extra_match"] = extra_match
        operations.append(compatible_operation)

    payload = {
        "scenario_name": scenario.get("scenario_name", ""),
        "description": scenario.get("description", ""),
        "input": scenario.get("input", ""),
        "output": scenario.get("output", ""),
        "log_output": scenario.get("log_output", ""),
        "operations": operations,
    }
    return payload
