import argparse
import json
import sys
from pathlib import Path

from update_csv_fields import (
    CsvUpdateError,
    ensure_columns_exist,
    get_file_rules,
    get_log_output_path,
    load_rows,
    validate_value,
    write_change_log,
    write_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JSON tabanli senaryo tanimini okuyup CSV guncellemesi uygular."
    )
    parser.add_argument(
        "--scenario-file",
        required=True,
        help="Calistirilacak senaryo tanim dosyasi yolu.",
    )
    return parser.parse_args()


def load_scenario_definition(scenario_path: Path) -> dict:
    if not scenario_path.exists():
        raise CsvUpdateError(f"Senaryo dosyasi bulunamadi: {scenario_path}")

    with scenario_path.open("r", encoding="utf-8") as file:
        try:
            scenario = json.load(file)
        except json.JSONDecodeError as error:
            raise CsvUpdateError(
                f"Senaryo dosyasi gecerli JSON degil: {scenario_path}"
            ) from error

    required_fields = {"scenario_name", "input", "output", "operations"}
    missing_fields = sorted(field for field in required_fields if field not in scenario)
    if missing_fields:
        raise CsvUpdateError(
            f"Senaryo dosyasinda eksik alan(lar) bulundu: {', '.join(missing_fields)}"
        )

    if not isinstance(scenario["operations"], list) or not scenario["operations"]:
        raise CsvUpdateError("'operations' alani bos olmayan bir liste olmalidir.")

    return scenario


def validate_operation_structure(index: int, operation: dict) -> None:
    if not isinstance(operation, dict):
        raise CsvUpdateError(f"{index}. islem gecerli bir nesne olmali.")

    if "match" not in operation or "updates" not in operation:
        raise CsvUpdateError(
            f"{index}. islem icinde 'match' ve 'updates' alanlari zorunludur."
        )

    match = operation["match"]
    updates = operation["updates"]

    if not isinstance(match, dict) or "column" not in match or "value" not in match:
        raise CsvUpdateError(
            f"{index}. islemde 'match' alani 'column' ve 'value' icermelidir."
        )

    if not isinstance(updates, dict) or not updates:
        raise CsvUpdateError(f"{index}. islemde 'updates' alani bos olmayan bir nesne olmali.")


def apply_operation(
    operation_index: int,
    operation: dict,
    rows: list[dict],
    input_path: Path,
    fieldnames: list[str],
    rules: dict,
) -> list[dict]:
    validate_operation_structure(operation_index, operation)

    match_column = operation["match"]["column"]
    match_value = str(operation["match"]["value"])
    updates = operation["updates"]

    if match_column not in rules["key_columns"]:
        allowed = ", ".join(sorted(rules["key_columns"]))
        raise CsvUpdateError(
            f"{operation_index}. islemde '{match_column}' ile eslestirme desteklenmiyor. "
            f"Izin verilen kolonlar: {allowed}"
        )

    ensure_columns_exist(fieldnames, {match_column} | set(updates.keys()), input_path)

    for column, value in updates.items():
        if column not in rules["editable_columns"]:
            allowed = ", ".join(sorted(rules["editable_columns"]))
            raise CsvUpdateError(
                f"{operation_index}. islemde '{column}' kolonu guncellenemez. "
                f"Izin verilen kolonlar: {allowed}"
            )
        validate_value(str(value), rules["editable_columns"][column], column)

    change_logs = []
    matched_any = False
    changed_any = False

    for row in rows:
        if row.get(match_column) != match_value:
            continue

        matched_any = True
        for column, value in updates.items():
            new_value = str(value)
            old_value = row.get(column, "")
            if old_value == new_value:
                continue
            row[column] = new_value
            changed_any = True
            change_logs.append(
                {
                    "dosya": str(input_path),
                    "satir": row["__row_number"],
                    "kolon": column,
                    "eski_deger": old_value,
                    "yeni_deger": new_value,
                    "islem": operation.get("name", f"operation_{operation_index}"),
                }
            )

    if not matched_any:
        raise CsvUpdateError(
            f"{operation_index}. islem icin eslesen satir bulunamadi: "
            f"{match_column}='{match_value}'"
        )

    if not changed_any:
        raise CsvUpdateError(
            f"{operation_index}. islem eslesen satiri buldu ancak yeni degerler mevcut veriyle ayni."
        )

    return change_logs


def apply_scenario_to_rows(scenario: dict) -> tuple[list[dict], list[str], list[dict], Path]:
    input_path = Path(scenario["input"])
    rows, fieldnames = load_rows(input_path)
    rules = get_file_rules(input_path)
    ensure_columns_exist(fieldnames, set(rules["key_columns"]), input_path)

    all_change_logs = []
    for index, operation in enumerate(scenario["operations"], start=1):
        all_change_logs.extend(
            apply_operation(index, operation, rows, input_path, fieldnames, rules)
        )

    return rows, fieldnames, all_change_logs, input_path


def run_scenario_definition(scenario: dict) -> tuple[Path, Path, int]:
    output_path = Path(scenario["output"])
    log_output_path = get_log_output_path(output_path, scenario.get("log_output"))
    rows, fieldnames, all_change_logs, _ = apply_scenario_to_rows(scenario)

    write_rows(output_path, rows, fieldnames)
    write_change_log(log_output_path, all_change_logs)
    return output_path, log_output_path, len(all_change_logs)


def main() -> int:
    args = parse_args()
    scenario_path = Path(args.scenario_file)

    try:
        scenario = load_scenario_definition(scenario_path)
        output_path, log_output_path, change_count = run_scenario_definition(scenario)

        print(
            f"Senaryo uygulandi: {scenario['scenario_name']}. "
            f"{change_count} alan degisti. "
            f"Cikti dosyasi: {output_path}. Log dosyasi: {log_output_path}"
        )
        return 0

    except CsvUpdateError as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
