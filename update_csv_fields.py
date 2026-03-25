import argparse
import csv
import sys
from pathlib import Path


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
    }
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
        rows = list(reader)
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

    raise CsvUpdateError(f"Bilinmeyen kolon tipi tanimi: {value_type}")


def update_rows(
    rows: list[dict],
    match_column: str,
    match_value: str,
    updates: dict[str, str],
) -> int:
    updated_count = 0
    for row in rows:
        if row.get(match_column) == match_value:
            for column, value in updates.items():
                row[column] = value
            updated_count += 1
    return updated_count


def write_rows(output_path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        rules = get_file_rules(input_path)
        rows, fieldnames = load_rows(input_path)
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
        updated_count = update_rows(rows, args.match_column, args.match_value, updates)

        if updated_count == 0:
            raise CsvUpdateError(
                f"Eslestirilen satir bulunamadi: {args.match_column}='{args.match_value}'"
            )

        write_rows(output_path, rows, fieldnames)
        print(
            f"Guncelleme tamamlandi. {updated_count} satir guncellendi. "
            f"Cikti dosyasi: {output_path}"
        )
        return 0

    except CsvUpdateError as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
