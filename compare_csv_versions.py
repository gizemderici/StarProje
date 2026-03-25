import argparse
import csv
import json
import sys
from pathlib import Path


SUPPORTED_COMPARISONS = {
    "materials.csv": {
        "aliases": {"materials"},
        "key_columns": ["name"],
    }
}


class CsvCompareError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bir CSV dosyasinin eski ve yeni surumu arasindaki farklari raporlar."
    )
    parser.add_argument("--old", required=True, help="Eski CSV dosya yolu.")
    parser.add_argument("--new", required=True, help="Yeni CSV dosya yolu.")
    parser.add_argument(
        "--report-output",
        help="Rapor dosyasi yolu. .json veya .csv olabilir. Verilmezse sadece terminale yazdirir.",
    )
    return parser.parse_args()


def get_comparison_rules(old_path: Path, new_path: Path) -> dict:
    old_rules = resolve_comparison_rules(old_path)
    new_rules = resolve_comparison_rules(new_path)

    if old_rules is None or new_rules is None:
        supported = ", ".join(sorted(SUPPORTED_COMPARISONS))
        missing_name = old_path.name if old_rules is None else new_path.name
        raise CsvCompareError(
            f"Desteklenmeyen CSV dosyasi: {missing_name}. Desteklenen dosyalar: {supported}"
        )

    if old_rules is not new_rules:
        raise CsvCompareError(
            "Eski ve yeni dosyalar ayni CSV turune ait olmali. Algilanan veri turleri farkli."
        )

    return old_rules


def resolve_comparison_rules(input_path: Path) -> dict | None:
    file_name = input_path.name.lower()
    stem_name = input_path.stem.lower()

    for canonical_name, rules in SUPPORTED_COMPARISONS.items():
        canonical_stem = Path(canonical_name).stem.lower()
        aliases = {alias.lower() for alias in rules.get("aliases", set())}

        if file_name == canonical_name.lower():
            return rules
        if stem_name == canonical_stem:
            return rules
        if stem_name.startswith(f"{canonical_stem}_"):
            return rules
        if stem_name.endswith(f"_{canonical_stem}"):
            return rules
        if stem_name in aliases:
            return rules
        if any(stem_name.startswith(f"{alias}_") or stem_name.endswith(f"_{alias}") for alias in aliases):
            return rules

    return None


def load_rows(input_path: Path) -> tuple[list[dict], list[str]]:
    if not input_path.exists():
        raise CsvCompareError(f"CSV dosyasi bulunamadi: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise CsvCompareError(f"CSV baslik satiri bulunamadi: {input_path}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            row["__row_number"] = row_number
            rows.append(row)
        return rows, reader.fieldnames


def ensure_columns_exist(fieldnames: list[str], required_columns: list[str], input_path: Path) -> None:
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise CsvCompareError(
            f"Eksik kolon(lar) bulundu ({', '.join(missing)}) dosya: {input_path}"
        )


def build_row_map(rows: list[dict], key_columns: list[str], input_path: Path) -> dict[tuple[str, ...], dict]:
    row_map = {}
    for row in rows:
        key = tuple((row.get(column) or "").strip() for column in key_columns)
        if any(part == "" for part in key):
            raise CsvCompareError(
                f"Anahtar kolonlarda bos deger bulundu. Dosya: {input_path}, satir: {row['__row_number']}"
            )
        if key in row_map:
            key_text = " | ".join(key)
            raise CsvCompareError(
                f"Karsilastirma anahtari tekrarli. Dosya: {input_path}, anahtar: {key_text}"
            )
        row_map[key] = row
    return row_map


def compare_rows(
    old_rows: list[dict],
    new_rows: list[dict],
    old_fieldnames: list[str],
    new_fieldnames: list[str],
    key_columns: list[str],
) -> dict:
    comparable_columns = sorted((set(old_fieldnames) | set(new_fieldnames)) - {"__row_number"})
    old_map = build_row_map(old_rows, key_columns, Path("old"))
    new_map = build_row_map(new_rows, key_columns, Path("new"))

    old_keys = set(old_map)
    new_keys = set(new_map)

    added_rows = []
    for key in sorted(new_keys - old_keys):
        row = new_map[key]
        added_rows.append(
            {
                "anahtar": " | ".join(key),
                "satir": row["__row_number"],
                "veri": {column: row.get(column, "") for column in comparable_columns},
            }
        )

    removed_rows = []
    for key in sorted(old_keys - new_keys):
        row = old_map[key]
        removed_rows.append(
            {
                "anahtar": " | ".join(key),
                "satir": row["__row_number"],
                "veri": {column: row.get(column, "") for column in comparable_columns},
            }
        )

    changed_cells = []
    for key in sorted(old_keys & new_keys):
        old_row = old_map[key]
        new_row = new_map[key]
        for column in comparable_columns:
            old_value = old_row.get(column, "")
            new_value = new_row.get(column, "")
            if old_value == new_value:
                continue
            changed_cells.append(
                {
                    "anahtar": " | ".join(key),
                    "kolon": column,
                    "eski_deger": old_value,
                    "yeni_deger": new_value,
                    "eski_satir": old_row["__row_number"],
                    "yeni_satir": new_row["__row_number"],
                }
            )

    return {
        "eklenen_satirlar": added_rows,
        "silinen_satirlar": removed_rows,
        "degisen_hucreler": changed_cells,
    }


def build_summary(old_path: Path, new_path: Path, diff_report: dict) -> dict:
    return {
        "eski_dosya": str(old_path),
        "yeni_dosya": str(new_path),
        "eklenen_satir_sayisi": len(diff_report["eklenen_satirlar"]),
        "silinen_satir_sayisi": len(diff_report["silinen_satirlar"]),
        "degisen_hucre_sayisi": len(diff_report["degisen_hucreler"]),
    }


def print_report(summary: dict, diff_report: dict) -> None:
    print(f"Eski dosya: {summary['eski_dosya']}")
    print(f"Yeni dosya: {summary['yeni_dosya']}")
    print(f"Eklenen satir: {summary['eklenen_satir_sayisi']}")
    print(f"Silinen satir: {summary['silinen_satir_sayisi']}")
    print(f"Degisen hucre: {summary['degisen_hucre_sayisi']}")

    if diff_report["eklenen_satirlar"]:
        print("Eklenen satirlar:")
        for item in diff_report["eklenen_satirlar"]:
            print(f"- anahtar={item['anahtar']} satir={item['satir']}")

    if diff_report["silinen_satirlar"]:
        print("Silinen satirlar:")
        for item in diff_report["silinen_satirlar"]:
            print(f"- anahtar={item['anahtar']} satir={item['satir']}")

    if diff_report["degisen_hucreler"]:
        print("Degisen hucreler:")
        for item in diff_report["degisen_hucreler"]:
            print(
                f"- anahtar={item['anahtar']} kolon={item['kolon']} "
                f"eski={item['eski_deger']} yeni={item['yeni_deger']}"
            )

    if (
        not diff_report["eklenen_satirlar"]
        and not diff_report["silinen_satirlar"]
        and not diff_report["degisen_hucreler"]
    ):
        print("Fark bulunamadi.")


def write_report(report_output: Path, summary: dict, diff_report: dict) -> None:
    report_output.parent.mkdir(parents=True, exist_ok=True)

    if report_output.suffix.lower() == ".json":
        with report_output.open("w", encoding="utf-8") as file:
            json.dump({"ozet": summary, "farklar": diff_report}, file, ensure_ascii=False, indent=2)
        return

    if report_output.suffix.lower() == ".csv":
        fieldnames = [
            "kategori",
            "anahtar",
            "kolon",
            "eski_deger",
            "yeni_deger",
            "eski_satir",
            "yeni_satir",
        ]
        rows = []
        for item in diff_report["eklenen_satirlar"]:
            rows.append(
                {
                    "kategori": "eklenen_satir",
                    "anahtar": item["anahtar"],
                    "kolon": "",
                    "eski_deger": "",
                    "yeni_deger": json.dumps(item["veri"], ensure_ascii=False),
                    "eski_satir": "",
                    "yeni_satir": item["satir"],
                }
            )
        for item in diff_report["silinen_satirlar"]:
            rows.append(
                {
                    "kategori": "silinen_satir",
                    "anahtar": item["anahtar"],
                    "kolon": "",
                    "eski_deger": json.dumps(item["veri"], ensure_ascii=False),
                    "yeni_deger": "",
                    "eski_satir": item["satir"],
                    "yeni_satir": "",
                }
            )
        for item in diff_report["degisen_hucreler"]:
            rows.append(
                {
                    "kategori": "degisen_hucre",
                    "anahtar": item["anahtar"],
                    "kolon": item["kolon"],
                    "eski_deger": item["eski_deger"],
                    "yeni_deger": item["yeni_deger"],
                    "eski_satir": item["eski_satir"],
                    "yeni_satir": item["yeni_satir"],
                }
            )

        with report_output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return

    raise CsvCompareError("Rapor dosyasi uzantisi .csv veya .json olmali.")


def main() -> int:
    args = parse_args()
    old_path = Path(args.old)
    new_path = Path(args.new)

    try:
        rules = get_comparison_rules(old_path, new_path)
        old_rows, old_fieldnames = load_rows(old_path)
        new_rows, new_fieldnames = load_rows(new_path)
        ensure_columns_exist(old_fieldnames, rules["key_columns"], old_path)
        ensure_columns_exist(new_fieldnames, rules["key_columns"], new_path)

        diff_report = compare_rows(
            old_rows,
            new_rows,
            old_fieldnames,
            new_fieldnames,
            rules["key_columns"],
        )
        summary = build_summary(old_path, new_path, diff_report)
        print_report(summary, diff_report)

        if args.report_output:
            write_report(Path(args.report_output), summary, diff_report)
            print(f"Rapor dosyasi yazildi: {args.report_output}")

        return 0

    except CsvCompareError as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
