import argparse
from pathlib import Path

from update_csv_fields import (
    ROW_NUMBER_FIELD,
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
        description="Senaryo bazli toplu CSV guncellemesi yapar."
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=sorted(SCENARIOS),
        help="Calistirilacak senaryo adi.",
    )
    parser.add_argument("--input", required=True, help="Girdi CSV dosya yolu.")
    parser.add_argument("--output", required=True, help="Senaryo cikti dosya yolu.")
    parser.add_argument(
        "--log-output",
        help="Degisiklik logu dosya yolu. Verilmezse otomatik uretilir.",
    )
    parser.add_argument(
        "--param",
        dest="params",
        action="append",
        default=[],
        help="Senaryo parametresi. Ornek: --param factor=1.2",
    )
    return parser.parse_args()


def parse_param_expressions(param_expressions: list[str]) -> dict[str, str]:
    params = {}
    for expression in param_expressions:
        if "=" not in expression:
            raise CsvUpdateError(
                f"Gecersiz parametre ifadesi: '{expression}'. Beklenen format: anahtar=deger"
            )
        key, value = expression.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise CsvUpdateError(
                f"Gecersiz parametre ifadesi: '{expression}'. Parametre adi bos olamaz."
            )
        params[key] = value
    return params


def require_param(params: dict[str, str], name: str) -> str:
    value = params.get(name)
    if value is None or value == "":
        raise CsvUpdateError(f"'{name}' parametresi zorunludur.")
    return value


def parse_float_param(params: dict[str, str], name: str) -> float:
    value = require_param(params, name)
    try:
        return float(value)
    except ValueError as error:
        raise CsvUpdateError(
            f"'{name}' parametresi sayisal olmalidir. Alinan deger: '{value}'"
        ) from error


def parse_optional_float_param(params: dict[str, str], name: str) -> float | None:
    value = params.get(name)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as error:
        raise CsvUpdateError(
            f"'{name}' parametresi sayisal olmalidir. Alinan deger: '{value}'"
        ) from error


def parse_optional_int_param(params: dict[str, str], name: str) -> int | None:
    value = params.get(name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise CsvUpdateError(
            f"'{name}' parametresi tam sayi olmalidir. Alinan deger: '{value}'"
        ) from error


def format_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_change_log(input_path: Path, row: dict, column: str, new_value: str) -> dict | None:
    old_value = row.get(column, "")
    if old_value == new_value:
        return None
    return {
        "dosya": str(input_path),
        "satir": row[ROW_NUMBER_FIELD],
        "kolon": column,
        "eski_deger": old_value,
        "yeni_deger": new_value,
    }


def apply_row_updates(
    input_path: Path,
    row: dict,
    updates: dict[str, str],
    editable_columns: dict[str, str],
) -> list[dict]:
    change_logs = []
    for column, new_value in updates.items():
        validate_value(new_value, editable_columns[column], column)
        change_log = build_change_log(input_path, row, column, new_value)
        if change_log is None:
            continue
        row[column] = new_value
        change_logs.append(change_log)
    return change_logs


def run_insulation_thickness_boost(
    rows: list[dict],
    input_path: Path,
    editable_columns: dict[str, str],
    params: dict[str, str],
) -> list[dict]:
    factor = parse_float_param(params, "factor")
    keywords = params.get("keywords", "izolasyon,yalitim").split(",")
    normalized_keywords = [item.strip().lower() for item in keywords if item.strip()]
    if not normalized_keywords:
        raise CsvUpdateError("'keywords' parametresi en az bir anahtar kelime icermelidir.")

    change_logs = []
    for row in rows:
        material_name = row.get("name", "").lower()
        thickness_value = row.get("thickness_m", "").strip()
        if not thickness_value:
            continue
        if not any(keyword in material_name for keyword in normalized_keywords):
            continue

        new_thickness = format_float(float(thickness_value) * factor)
        change_logs.extend(
            apply_row_updates(
                input_path,
                row,
                {"thickness_m": new_thickness},
                editable_columns,
            )
        )
    return change_logs


def run_material_conductivity_override(
    rows: list[dict],
    input_path: Path,
    editable_columns: dict[str, str],
    params: dict[str, str],
) -> list[dict]:
    names = require_param(params, "names")
    target_value = format_float(parse_float_param(params, "value"))
    selected_names = {item.strip() for item in names.split(",") if item.strip()}
    if not selected_names:
        raise CsvUpdateError("'names' parametresi en az bir malzeme adi icermelidir.")

    change_logs = []
    for row in rows:
        if row.get("name") not in selected_names:
            continue
        change_logs.extend(
            apply_row_updates(
                input_path,
                row,
                {"conductivity_w_per_mk": target_value},
                editable_columns,
            )
        )
    return change_logs


def run_construction_layer_update(
    rows: list[dict],
    input_path: Path,
    editable_columns: dict[str, str],
    params: dict[str, str],
) -> list[dict]:
    construction_name = require_param(params, "construction_name")
    layer_name = params.get("layer_name")
    layer_index = parse_optional_int_param(params, "layer_index")
    thickness_delta = parse_optional_float_param(params, "thickness_delta")
    conductivity_value = parse_optional_float_param(params, "conductivity_value")

    if layer_name is None and layer_index is None:
        raise CsvUpdateError(
            "'layer_name' veya 'layer_index' parametrelerinden en az biri verilmelidir."
        )
    if thickness_delta is None and conductivity_value is None:
        raise CsvUpdateError(
            "'thickness_delta' veya 'conductivity_value' parametrelerinden en az biri verilmelidir."
        )

    change_logs = []
    for row in rows:
        if row.get("construction_name") != construction_name:
            continue
        if layer_name is not None and row.get("name") != layer_name:
            continue
        if layer_index is not None and row.get("layer_index") != str(layer_index):
            continue

        updates = {}
        if thickness_delta is not None:
            current_thickness = row.get("thickness_m", "").strip()
            if not current_thickness:
                raise CsvUpdateError(
                    "Secilen katmanda 'thickness_m' degeri bos oldugu icin artis uygulanamadi."
                )
            updates["thickness_m"] = format_float(float(current_thickness) + thickness_delta)
        if conductivity_value is not None:
            updates["conductivity_w_per_mk"] = format_float(conductivity_value)

        change_logs.extend(
            apply_row_updates(
                input_path,
                row,
                updates,
                editable_columns,
            )
        )

    return change_logs


SCENARIOS = {
    "insulation_thickness_boost": {
        "target_file": "materials.csv",
        "required_columns": {"name", "thickness_m"},
        "runner": run_insulation_thickness_boost,
        "description": "Izolasyon ve yalitim malzemelerinin kalinligini carpana gore artirir.",
    },
    "material_conductivity_override": {
        "target_file": "materials.csv",
        "required_columns": {"name", "conductivity_w_per_mk"},
        "runner": run_material_conductivity_override,
        "description": "Secili malzemelerin iletkenligini tek bir degere ceker.",
    },
    "construction_layer_update": {
        "target_file": "construction_layers.csv",
        "required_columns": {
            "construction_name",
            "layer_index",
            "name",
            "thickness_m",
            "conductivity_w_per_mk",
        },
        "runner": run_construction_layer_update,
        "description": "Belirli construction katmanlarinda kalinlik ve iletkenlik gunceller.",
    },
}


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        scenario = SCENARIOS[args.scenario]
        if input_path.name != scenario["target_file"]:
            raise CsvUpdateError(
                f"'{args.scenario}' senaryosu yalnizca {scenario['target_file']} dosyasi ile calisir."
            )

        params = parse_param_expressions(args.params)
        rows, fieldnames = load_rows(input_path)
        rules = get_file_rules(input_path)
        ensure_columns_exist(fieldnames, scenario["required_columns"], input_path)
        log_output_path = get_log_output_path(output_path, args.log_output)

        change_logs = scenario["runner"](
            rows,
            input_path,
            rules["editable_columns"],
            params,
        )

        if not change_logs:
            raise CsvUpdateError(
                "Senaryo hicbir satiri guncellemedi. Parametreleri ve eslesme kosullarini kontrol edin."
            )

        write_rows(output_path, rows, fieldnames)
        write_change_log(log_output_path, change_logs)
        changed_rows = len({log["satir"] for log in change_logs})
        print(
            f"Senaryo tamamlandi: {args.scenario}. "
            f"{changed_rows} satir, {len(change_logs)} alan degisti. "
            f"Cikti dosyasi: {output_path}. Log dosyasi: {log_output_path}"
        )
        return 0

    except CsvUpdateError as error:
        print(f"Hata: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
