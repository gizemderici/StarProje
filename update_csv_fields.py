import argparse
import csv
import json
import sys
from pathlib import Path


ROW_NUMBER_FIELD = "__row_number"


SUPPORTED_FILES = {
    "materials.csv": {
        "key_columns": {"name"},
        "editable_columns": {
            "name": "string",
            "thickness_m": "float",
            "conductivity_w_per_mk": "float",
            "thermal_resistance_m2k_per_w": "float",
            "u_factor_w_per_m2k": "float",
            "shgc": "float",
        },
    },
    "construction_layers.csv": {
        "key_columns": {"construction_name", "layer_index", "name"},
        "editable_columns": {
            "construction_name": "string",
            "layer_index": "integer",
            "name": "string",
            "thickness_m": "float",
            "conductivity_w_per_mk": "float",
            "thermal_resistance_m2k_per_w": "float",
            "u_factor_w_per_m2k": "float",
            "shgc": "float",
        },
    },
}


class CsvUpdateError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Belirli bir CSV dosyasinda kontrollu kolon guncellemesi yapar."
    )
    parser.add_argument("--input", required=True, help="Guncellenecek CSV dosya yolu.")
    parser.add_argument("--output", required=True, help="Yeni olusacak CSV dosya yolu.")
    parser.add_argument(
        "--log-output",
        help="Degisiklik kaydinin yazilacagi dosya yolu. .csv veya .json olabilir.",
    )
    parser.add_argument(
        "--match-column",
        required=True,
        help="Guncellenecek satiri bulmak icin kullanilacak kolon.",
    )
    parser.add_argument(
        "--match-value",
        required=True,
        help="Guncellenecek satiri bulmak icin aranacak deger.",
    )
    parser.add_argument(
        "--set",
        dest="updates",
        action="append",
        required=True,
        help="Guncelleme ifadesi. Ornek: --set thickness_m=0.22",
    )
    return parser.parse_args()


def load_rows(input_path: Path) -> tuple[list[dict], list[str]]:
    if not input_path.exists():
        raise CsvUpdateError(f"Girdi CSV dosyasi bulunamadi: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise CsvUpdateError(f"CSV baslik satiri bulunamadi: {input_path}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            row[ROW_NUMBER_FIELD] = row_number
            rows.append(row)
        return rows, reader.fieldnames


def get_file_rules(input_path: Path) -> dict:
    rules = SUPPORTED_FILES.get(input_path.name)
    if rules is None:
        supported = ", ".join(sorted(SUPPORTED_FILES))
        raise CsvUpdateError(
            f"Desteklenmeyen CSV dosyasi: {input_path.name}. Desteklenen dosyalar: {supported}"
        )
    return rules


def ensure_columns_exist(fieldnames: list[str], required_columns: set[str], input_path: Path) -> None:
    missing = sorted(column for column in required_columns if column not in fieldnames)
    if missing:
        raise CsvUpdateError(
            f"Eksik kolon(lar) bulundu ({', '.join(missing)}) dosya: {input_path}"
        )


def parse_update_expressions(
    update_expressions: list[str], editable_columns: dict[str, str]
) -> dict[str, str]:
    updates = {}
    for expression in update_expressions:
        if "=" not in expression:
            raise CsvUpdateError(
                f"Gecersiz guncelleme ifadesi: '{expression}'. Beklenen format: kolon=deger"
            )

        column, value = expression.split("=", 1)
        column = column.strip()
        value = value.strip()

        if not column:
            raise CsvUpdateError(
                f"Gecersiz guncelleme ifadesi: '{expression}'. Kolon adi bos olamaz."
            )

        if column not in editable_columns:
            allowed = ", ".join(sorted(editable_columns))
            raise CsvUpdateError(
                f"'{column}' kolonu guncellenemez. Izin verilen kolonlar: {allowed}"
            )

        validate_value(value, editable_columns[column], column)
        updates[column] = value

    return updates


def validate_value(value: str, value_type: str, column: str) -> None:
    if value_type == "string":
        if value == "":
            raise CsvUpdateError(f"'{column}' kolonu bos birakilamaz.")
        return

    if value_type == "float":
        if value == "":
            return
        try:
            float(value)
        except ValueError as error:
            raise CsvUpdateError(
                f"'{column}' kolonu sayisal bir deger bekliyor. Alinan deger: '{value}'"
            ) from error
        return

    if value_type == "integer":
        if value == "":
            raise CsvUpdateError(f"'{column}' kolonu bos birakilamaz.")
        try:
            int(value)
        except ValueError as error:
            raise CsvUpdateError(
                f"'{column}' kolonu tam sayi bir deger bekliyor. Alinan deger: '{value}'"
            ) from error
        return

    raise CsvUpdateError(f"Bilinmeyen kolon tipi tanimi: {value_type}")


def update_rows(
    rows: list[dict],
    input_path: Path,
    match_column: str,
    match_value: str,
    updates: dict[str, str],
) -> tuple[int, list[dict]]:
    updated_count = 0
    change_logs = []
    for row in rows:
        if row.get(match_column) == match_value:
            for column, value in updates.items():
                old_value = row.get(column, "")
                if old_value == value:
                    continue
                change_logs.append(
                    {
                        "dosya": str(input_path),
                        "satir": row[ROW_NUMBER_FIELD],
                        "kolon": column,
                        "eski_deger": old_value,
                        "yeni_deger": value,
                    }
                )
                row[column] = value
            if any(
                log["satir"] == row[ROW_NUMBER_FIELD]
                for log in change_logs
            ):
                updated_count += 1
    return updated_count, change_logs


def write_rows(output_path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            {
                key: value
                for key, value in row.items()
                if key in fieldnames
            }
            for row in rows
        )


def get_log_output_path(output_path: Path, requested_log_path: str | None) -> Path:
    if requested_log_path:
        log_path = Path(requested_log_path)
    else:
        log_path = output_path.with_name(f"{output_path.stem}_changes.csv")

    if log_path.suffix.lower() not in {".csv", ".json"}:
        raise CsvUpdateError(
            "Log dosyasi uzantisi .csv veya .json olmali."
        )
    return log_path


def write_change_log(log_output_path: Path, change_logs: list[dict]) -> None:
    log_output_path.parent.mkdir(parents=True, exist_ok=True)

    if log_output_path.suffix.lower() == ".json":
        with log_output_path.open("w", encoding="utf-8") as file:
            json.dump(change_logs, file, ensure_ascii=False, indent=2)
        return

    fieldnames = ["dosya", "satir", "kolon", "eski_deger", "yeni_deger"]
    with log_output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(change_logs)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        rules = get_file_rules(input_path)
        rows, fieldnames = load_rows(input_path)
        log_output_path = get_log_output_path(output_path, args.log_output)
        ensure_columns_exist(fieldnames, rules["key_columns"], input_path)

        if args.match_column not in rules["key_columns"]:
            allowed_match_columns = ", ".join(sorted(rules["key_columns"]))
            raise CsvUpdateError(
                f"'{args.match_column}' ile eslestirme desteklenmiyor. "
                f"Izin verilen eslestirme kolonlari: {allowed_match_columns}"
            )

        updates = parse_update_expressions(args.updates, rules["editable_columns"])
        ensure_columns_exist(
            fieldnames,
            {args.match_column} | set(updates.keys()),
            input_path,
        )
        updated_count, change_logs = update_rows(
            rows,
            input_path,
            args.match_column,
            args.match_value,
            updates,
        )

        if updated_count == 0:
            raise CsvUpdateError(
                "Eslestirilen satir bulunamadi veya verilen degerler mevcut veriyle ayni: "
                f"{args.match_column}='{args.match_value}'"
            )

        write_rows(output_path, rows, fieldnames)
        write_change_log(log_output_path, change_logs)
        print(
            f"Guncelleme tamamlandi. {updated_count} satir guncellendi. "
            f"Cikti dosyasi: {output_path}. Log dosyasi: {log_output_path}"
        )
        return 0

    except CsvUpdateError as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
