import argparse
import csv
import json
import sys
from pathlib import Path


SUPPORTED_VALIDATIONS = {
    "materials.csv": {
        "required_columns": {
            "name",
            "type",
            "thickness_m",
            "conductivity_w_per_mk",
            "thermal_resistance_m2k_per_w",
        },
        "critical_columns": {"name", "type"},
        "numeric_columns": {
            "thickness_m",
            "conductivity_w_per_mk",
            "thermal_resistance_m2k_per_w",
        },
        "duplicate_key_columns": ["name"],
    }
}


class CsvValidationError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSV dosyalarinda eksik kolon, bos alan, sayisal format ve tekrarli kayit denetimi yapar."
    )
    parser.add_argument("--input", required=True, help="Dogrulanacak CSV dosya yolu.")
    parser.add_argument(
        "--report-output",
        help="Rapor dosyasi yolu. .json veya .csv olabilir. Verilmezse sadece terminale yazdirir.",
    )
    return parser.parse_args()


def get_validation_rules(input_path: Path) -> dict:
    rules = SUPPORTED_VALIDATIONS.get(input_path.name)
    if rules is None:
        supported = ", ".join(sorted(SUPPORTED_VALIDATIONS))
        raise CsvValidationError(
            f"Desteklenmeyen CSV dosyasi: {input_path.name}. Desteklenen dosyalar: {supported}"
        )
    return rules


def load_rows(input_path: Path) -> tuple[list[dict], list[str]]:
    if not input_path.exists():
        raise CsvValidationError(f"Girdi CSV dosyasi bulunamadi: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise CsvValidationError(f"CSV baslik satiri bulunamadi: {input_path}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            row["__row_number"] = row_number
            rows.append(row)
        return rows, reader.fieldnames


def validate_required_columns(fieldnames: list[str], required_columns: set[str]) -> list[dict]:
    missing_columns = sorted(column for column in required_columns if column not in fieldnames)
    return [
        {
            "kategori": "eksik_kolon",
            "satir": "",
            "kolon": column,
            "mesaj": f"Gerekli kolon bulunamadi: {column}",
            "deger": "",
        }
        for column in missing_columns
    ]


def validate_critical_fields(rows: list[dict], critical_columns: set[str]) -> list[dict]:
    issues = []
    for row in rows:
        for column in critical_columns:
            value = (row.get(column) or "").strip()
            if value:
                continue
            issues.append(
                {
                    "kategori": "bos_kritik_alan",
                    "satir": row["__row_number"],
                    "kolon": column,
                    "mesaj": f"Kritik alan bos: {column}",
                    "deger": "",
                }
            )
    return issues


def validate_numeric_fields(rows: list[dict], numeric_columns: set[str]) -> list[dict]:
    issues = []
    for row in rows:
        for column in numeric_columns:
            value = (row.get(column) or "").strip()
            if value == "":
                continue
            try:
                float(value)
            except ValueError:
                issues.append(
                    {
                        "kategori": "gecersiz_sayisal_deger",
                        "satir": row["__row_number"],
                        "kolon": column,
                        "mesaj": f"Sayisal alan gecersiz veri iceriyor: {column}",
                        "deger": value,
                    }
                )
    return issues


def validate_duplicate_rows(rows: list[dict], duplicate_key_columns: list[str]) -> list[dict]:
    issues = []
    seen = {}
    for row in rows:
        key = tuple((row.get(column) or "").strip() for column in duplicate_key_columns)
        if any(part == "" for part in key):
            continue
        seen.setdefault(key, []).append(row["__row_number"])

    for key, row_numbers in seen.items():
        if len(row_numbers) < 2:
            continue
        issues.append(
            {
                "kategori": "tekrarli_kayit",
                "satir": ", ".join(str(number) for number in row_numbers),
                "kolon": ", ".join(duplicate_key_columns),
                "mesaj": "Tekrar eden kayit bulundu",
                "deger": " | ".join(key),
            }
        )
    return issues


def build_summary(input_path: Path, rows: list[dict], issues: list[dict]) -> dict:
    summary = {
        "dosya": str(input_path),
        "toplam_satir": len(rows),
        "toplam_sorun": len(issues),
        "kategori_ozeti": {},
    }
    for issue in issues:
        category = issue["kategori"]
        summary["kategori_ozeti"][category] = summary["kategori_ozeti"].get(category, 0) + 1
    return summary


def print_report(summary: dict, issues: list[dict]) -> None:
    print(f"Dosya: {summary['dosya']}")
    print(f"Toplam satir: {summary['toplam_satir']}")
    print(f"Toplam sorun: {summary['toplam_sorun']}")

    if not issues:
        print("Sorun bulunamadi.")
        return

    print("Kategori ozeti:")
    for category, count in sorted(summary["kategori_ozeti"].items()):
        print(f"- {category}: {count}")

    print("Detaylar:")
    for issue in issues:
        print(
            f"- [{issue['kategori']}] satir={issue['satir']} kolon={issue['kolon']} "
            f"mesaj={issue['mesaj']} deger={issue['deger']}"
        )


def write_report(report_output: Path, summary: dict, issues: list[dict]) -> None:
    report_output.parent.mkdir(parents=True, exist_ok=True)

    if report_output.suffix.lower() == ".json":
        with report_output.open("w", encoding="utf-8") as file:
            json.dump({"ozet": summary, "sorunlar": issues}, file, ensure_ascii=False, indent=2)
        return

    if report_output.suffix.lower() == ".csv":
        fieldnames = ["kategori", "satir", "kolon", "mesaj", "deger"]
        with report_output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(issues)
        return

    raise CsvValidationError("Rapor dosyasi uzantisi .csv veya .json olmali.")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)

    try:
        rules = get_validation_rules(input_path)
        rows, fieldnames = load_rows(input_path)

        issues = []
        issues.extend(validate_required_columns(fieldnames, rules["required_columns"]))

        if not any(issue["kategori"] == "eksik_kolon" for issue in issues):
            issues.extend(validate_critical_fields(rows, rules["critical_columns"]))
            issues.extend(validate_numeric_fields(rows, rules["numeric_columns"]))
            issues.extend(validate_duplicate_rows(rows, rules["duplicate_key_columns"]))

        summary = build_summary(input_path, rows, issues)
        print_report(summary, issues)

        if args.report_output:
            write_report(Path(args.report_output), summary, issues)
            print(f"Rapor dosyasi yazildi: {args.report_output}")

        return 0

    except CsvValidationError as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
