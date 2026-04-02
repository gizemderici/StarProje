import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


CSV_ROOT = Path("csv_output")

DATASETS = {
    "materials.csv": {
        "entity": "material",
        "key_columns": ["name"],
        "primary_fields": [
            "name",
            "thickness_m",
            "conductivity_w_per_mk",
            "thermal_resistance_m2k_per_w",
            "u_factor_w_per_m2k",
            "shgc",
        ],
    },
    "construction_layers.csv": {
        "entity": "construction_layer",
        "key_columns": ["construction_name", "layer_index", "name"],
        "primary_fields": [
            "construction_name",
            "layer_index",
            "name",
            "thickness_m",
            "conductivity_w_per_mk",
            "thermal_resistance_m2k_per_w",
            "u_factor_w_per_m2k",
            "shgc",
        ],
    },
    "constructions.csv": {
        "entity": "construction",
        "key_columns": ["name"],
        "primary_fields": ["name"],
    },
    "walls.csv": {
        "entity": "surface",
        "key_columns": ["name"],
        "primary_fields": ["name", "construction_name", "space_name"],
    },
    "floors.csv": {
        "entity": "surface",
        "key_columns": ["name"],
        "primary_fields": ["name", "construction_name", "space_name"],
    },
    "roofs.csv": {
        "entity": "surface",
        "key_columns": ["name"],
        "primary_fields": ["name", "construction_name", "space_name"],
    },
    "windows.csv": {
        "entity": "sub_surface",
        "key_columns": ["name"],
        "primary_fields": ["name", "construction_name", "host_surface_name"],
    },
    "openings.csv": {
        "entity": "sub_surface",
        "key_columns": ["name"],
        "primary_fields": ["name", "construction_name", "host_surface_name"],
    },
    "spaces.csv": {
        "entity": "space",
        "key_columns": ["name"],
        "primary_fields": ["name", "thermal_zone_name"],
    },
    "zones.csv": {
        "entity": "zone",
        "key_columns": ["name"],
        "primary_fields": ["name"],
    },
}

SURFACE_FILES = ["walls.csv", "floors.csv", "roofs.csv"]
SUB_SURFACE_FILES = ["windows.csv", "openings.csv"]
CONSTRUCTION_CONSUMERS = SURFACE_FILES + SUB_SURFACE_FILES

DIRECT_RELATIONSHIPS = [
    {
        "source": ("materials.csv", "name"),
        "target": ("construction_layers.csv", "name"),
        "description": "Malzeme adi construction katmaninda referans olarak kullanilir.",
    },
    {
        "source": ("constructions.csv", "name"),
        "target": ("construction_layers.csv", "construction_name"),
        "description": "Katmanlar construction adina baglidir.",
    },
    {
        "source": ("constructions.csv", "name"),
        "target": ("walls.csv", "construction_name"),
        "description": "Duvarlar construction adina baglidir.",
    },
    {
        "source": ("constructions.csv", "name"),
        "target": ("floors.csv", "construction_name"),
        "description": "Dosemeler construction adina baglidir.",
    },
    {
        "source": ("constructions.csv", "name"),
        "target": ("roofs.csv", "construction_name"),
        "description": "Catilar construction adina baglidir.",
    },
    {
        "source": ("constructions.csv", "name"),
        "target": ("windows.csv", "construction_name"),
        "description": "Pencereler construction adina baglidir.",
    },
    {
        "source": ("constructions.csv", "name"),
        "target": ("openings.csv", "construction_name"),
        "description": "Acikliklar construction adina baglidir.",
    },
    {
        "source": ("spaces.csv", "name"),
        "target": ("walls.csv", "space_name"),
        "description": "Duvar kayitlari mekan adini referans alir.",
    },
    {
        "source": ("spaces.csv", "name"),
        "target": ("floors.csv", "space_name"),
        "description": "Doseme kayitlari mekan adini referans alir.",
    },
    {
        "source": ("spaces.csv", "name"),
        "target": ("roofs.csv", "space_name"),
        "description": "Cati kayitlari mekan adini referans alir.",
    },
    {
        "source": ("zones.csv", "name"),
        "target": ("spaces.csv", "thermal_zone_name"),
        "description": "Mekan kayitlari thermal zone adina baglidir.",
    },
    {
        "source": ("walls.csv", "name"),
        "target": ("windows.csv", "host_surface_name"),
        "description": "Pencereler ana yuzey olarak duvar adini referans alir.",
    },
    {
        "source": ("walls.csv", "name"),
        "target": ("openings.csv", "host_surface_name"),
        "description": "Acikliklar ana yuzey olarak duvar adini referans alir.",
    },
]


class DependencyAnalysisError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSV veri setleri arasindaki bagimliliklari analiz eder."
    )
    parser.add_argument(
        "--csv-root",
        default=str(CSV_ROOT),
        help="Analiz edilecek CSV klasoru.",
    )
    parser.add_argument(
        "--dataset",
        help="Etkisi incelenecek veri seti. Ornek: materials.csv",
    )
    parser.add_argument(
        "--match-column",
        help="Secilecek satiri bulmak icin kullanilacak kolon.",
    )
    parser.add_argument(
        "--match-value",
        help="Secilecek satirin kolon degeri.",
    )
    parser.add_argument(
        "--changed-column",
        help="Degistigi varsayilan kolon. Rapor aciklamalarinda kullanilir.",
    )
    parser.add_argument(
        "--output",
        help="Raporun yazilacagi dosya yolu. .json veya .md olabilir.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "md"],
        default="json",
        help="Terminale veya cikti dosyasina yazilacak format.",
    )
    parser.add_argument(
        "--old-root",
        help="Eski state icin CSV klasoru. Verilirse otomatik degisim tespiti yapilir.",
    )
    parser.add_argument(
        "--new-root",
        help="Yeni state icin CSV klasoru. Verilirse otomatik degisim tespiti yapilir.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Otomatik tespit modunda islenecek maksimum degisim sayisi.",
    )
    return parser.parse_args()


def load_csv_rows(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        raise DependencyAnalysisError(f"CSV dosyasi bulunamadi: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise DependencyAnalysisError(f"CSV baslik satiri bulunamadi: {path}")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def build_row_key(dataset_name: str, row: dict) -> str:
    dataset_config = DATASETS[dataset_name]
    parts = []
    for column in dataset_config["key_columns"]:
        parts.append(f"{column}={row.get(column, '')}")
    return " | ".join(parts)


def compact_row(row: dict, columns: list[str]) -> dict:
    return {column: row.get(column, "") for column in columns if column in row}


class CsvRepository:
    def __init__(self, csv_root: Path):
        self.csv_root = csv_root
        self.datasets: dict[str, dict] = {}
        self._indexes: dict[tuple[str, str], dict[str, list[dict]]] = {}
        self._load()

    def _load(self) -> None:
        for dataset_name, config in DATASETS.items():
            path = self.csv_root / dataset_name
            if not path.exists():
                continue
            rows, fieldnames = load_csv_rows(path)
            self.datasets[dataset_name] = {
                "path": path,
                "rows": rows,
                "fieldnames": fieldnames,
                "config": config,
            }

    def require_dataset(self, dataset_name: str) -> dict:
        dataset = self.datasets.get(dataset_name)
        if dataset is None:
            raise DependencyAnalysisError(f"Veri seti bulunamadi: {dataset_name}")
        return dataset

    def get_rows(self, dataset_name: str) -> list[dict]:
        return self.require_dataset(dataset_name)["rows"]

    def find_rows(self, dataset_name: str, column: str, value: str) -> list[dict]:
        dataset = self.require_dataset(dataset_name)
        if column not in dataset["fieldnames"]:
            raise DependencyAnalysisError(
                f"'{dataset_name}' icinde '{column}' kolonu bulunamadi."
            )

        index_key = (dataset_name, column)
        if index_key not in self._indexes:
            index = defaultdict(list)
            for row in dataset["rows"]:
                index[str(row.get(column, ""))].append(row)
            self._indexes[index_key] = index
        return list(self._indexes[index_key].get(str(value), []))

    def get_row_map(self, dataset_name: str) -> dict[tuple[str, ...], dict]:
        dataset = self.require_dataset(dataset_name)
        key_columns = dataset["config"]["key_columns"]
        row_map = {}
        for row in dataset["rows"]:
            key = tuple(str(row.get(column, "")) for column in key_columns)
            if any(part == "" for part in key):
                raise DependencyAnalysisError(
                    f"'{dataset_name}' icinde anahtar kolonlarda bos deger bulundu: {key_columns}"
                )
            if key in row_map:
                raise DependencyAnalysisError(
                    f"'{dataset_name}' icinde tekrarli anahtar bulundu: {' | '.join(key)}"
                )
            row_map[key] = row
        return row_map


def make_impact_entry(
    dataset_name: str,
    rows: list[dict],
    via: str,
    impact_type: str,
    reason: str,
) -> dict:
    config = DATASETS[dataset_name]
    sample_rows = [
        {
            "row_key": build_row_key(dataset_name, row),
            "preview": compact_row(row, config["key_columns"] + config["primary_fields"][:3]),
        }
        for row in rows[:5]
    ]
    return {
        "dataset": dataset_name,
        "impact_type": impact_type,
        "via": via,
        "affected_row_count": len(rows),
        "sample_rows": sample_rows,
        "reason": reason,
    }


def analyze_material_dependency(repo: CsvRepository, row: dict, changed_column: str | None) -> dict:
    material_name = row.get("name", "")
    property_name = changed_column or "name"
    direct_rows = repo.find_rows("construction_layers.csv", "name", material_name)

    impacts = []
    if direct_rows:
        impacts.append(
            make_impact_entry(
                "construction_layers.csv",
                direct_rows,
                f"materials.csv.name={material_name}",
                "direct",
                f"Malzeme '{material_name}' construction katmanlarinda referans aliniyor; '{property_name}' degisimi bu katmanlarin davranisini etkiler.",
            )
        )

    construction_names = sorted(
        {
            dependency_row.get("construction_name", "")
            for dependency_row in direct_rows
            if dependency_row.get("construction_name", "")
        }
    )
    construction_rows = []
    for construction_name in construction_names:
        construction_rows.extend(repo.find_rows("constructions.csv", "name", construction_name))
    if construction_rows:
        impacts.append(
            make_impact_entry(
                "constructions.csv",
                construction_rows,
                "construction_layers.csv.construction_name",
                "indirect",
                "Malzeme etkisi once construction katmanina, ardindan ilgili construction tanimlarina yayilir.",
            )
        )

    for dataset_name in CONSTRUCTION_CONSUMERS:
        surface_rows = []
        for construction_name in construction_names:
            surface_rows.extend(repo.find_rows(dataset_name, "construction_name", construction_name))
        if surface_rows:
            impacts.append(
                make_impact_entry(
                    dataset_name,
                    surface_rows,
                    "constructions.csv.name",
                    "indirect",
                    f"Bu veri setindeki kayitlar, etkilenen construction'lari kullandigi icin '{property_name}' degisiminden dolayli olarak etkilenir.",
                )
            )

    return {
        "root_entity": "material",
        "root_value": material_name,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_construction_dependency(repo: CsvRepository, row: dict, changed_column: str | None) -> dict:
    construction_name = row.get("name", "")
    property_name = changed_column or "name"
    impacts = []

    layer_rows = repo.find_rows("construction_layers.csv", "construction_name", construction_name)
    if layer_rows:
        impacts.append(
            make_impact_entry(
                "construction_layers.csv",
                layer_rows,
                f"constructions.csv.name={construction_name}",
                "direct",
                f"Construction '{construction_name}' katman tanimlarini dogrudan belirler; '{property_name}' degisimi katman baglantilarini etkiler.",
            )
        )

    for dataset_name in CONSTRUCTION_CONSUMERS:
        consumer_rows = repo.find_rows(dataset_name, "construction_name", construction_name)
        if consumer_rows:
            impacts.append(
                make_impact_entry(
                    dataset_name,
                    consumer_rows,
                    f"constructions.csv.name={construction_name}",
                    "direct",
                    f"Bu kayitlar '{construction_name}' construction'ini kullaniyor; '{property_name}' degisimi yuzey davranisini dogrudan etkiler.",
                )
            )

    return {
        "root_entity": "construction",
        "root_value": construction_name,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_construction_layer_dependency(
    repo: CsvRepository, row: dict, changed_column: str | None
) -> dict:
    construction_name = row.get("construction_name", "")
    material_name = row.get("name", "")
    layer_key = build_row_key("construction_layers.csv", row)
    property_name = changed_column or "name"
    impacts = []

    material_rows = repo.find_rows("materials.csv", "name", material_name)
    if material_rows:
        impacts.append(
            make_impact_entry(
                "materials.csv",
                material_rows,
                f"construction_layers.csv:{layer_key}",
                "direct",
                f"Katman '{material_name}' malzemesine bagli; '{property_name}' degisimi malzeme referansini veya davranisini etkiler.",
            )
        )

    construction_rows = repo.find_rows("constructions.csv", "name", construction_name)
    if construction_rows:
        impacts.append(
            make_impact_entry(
                "constructions.csv",
                construction_rows,
                f"construction_layers.csv:{layer_key}",
                "direct",
                "Katman degisikligi ayni construction altindaki toplam katman kurgusunu etkiler.",
            )
        )

    for dataset_name in CONSTRUCTION_CONSUMERS:
        consumer_rows = repo.find_rows(dataset_name, "construction_name", construction_name)
        if consumer_rows:
            impacts.append(
                make_impact_entry(
                    dataset_name,
                    consumer_rows,
                    "constructions.csv.name",
                    "indirect",
                    "Katman degisikligi ilgili construction'i kullanan yuzeylere dolayli olarak yayilir.",
                )
            )

    return {
        "root_entity": "construction_layer",
        "root_value": layer_key,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_space_dependency(repo: CsvRepository, row: dict, changed_column: str | None) -> dict:
    space_name = row.get("name", "")
    zone_name = row.get("thermal_zone_name", "")
    property_name = changed_column or "name"
    impacts = []

    for dataset_name in SURFACE_FILES:
        surface_rows = repo.find_rows(dataset_name, "space_name", space_name)
        if surface_rows:
            impacts.append(
                make_impact_entry(
                    dataset_name,
                    surface_rows,
                    f"spaces.csv.name={space_name}",
                    "direct",
                    f"Bu kayitlar '{space_name}' mekanina bagli; '{property_name}' degisimi iliskiyi dogrudan etkiler.",
                )
            )

    if zone_name:
        zone_rows = repo.find_rows("zones.csv", "name", zone_name)
        if zone_rows:
            impacts.append(
                make_impact_entry(
                    "zones.csv",
                    zone_rows,
                    f"spaces.csv.thermal_zone_name={zone_name}",
                    "direct",
                    "Mekan kaydi thermal zone ile dogrudan iliskilidir.",
                )
            )

    return {
        "root_entity": "space",
        "root_value": space_name,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_zone_dependency(repo: CsvRepository, row: dict, changed_column: str | None) -> dict:
    zone_name = row.get("name", "")
    property_name = changed_column or "name"
    impacts = []

    space_rows = repo.find_rows("spaces.csv", "thermal_zone_name", zone_name)
    if space_rows:
        impacts.append(
            make_impact_entry(
                "spaces.csv",
                space_rows,
                f"zones.csv.name={zone_name}",
                "direct",
                f"Zone '{zone_name}' mekan kayitlarinda referans aliniyor.",
            )
        )

        space_names = {space_row.get("name", "") for space_row in space_rows if space_row.get("name", "")}
        for dataset_name in SURFACE_FILES:
            surface_rows = []
            for space_name in space_names:
                surface_rows.extend(repo.find_rows(dataset_name, "space_name", space_name))
            if surface_rows:
                impacts.append(
                    make_impact_entry(
                        dataset_name,
                        surface_rows,
                        "spaces.csv.name",
                        "indirect",
                        "Zone degisikligi ilgili mekanlar uzerinden yuzey kayitlarina dolayli olarak yansir.",
                    )
                )

    return {
        "root_entity": "zone",
        "root_value": zone_name,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_surface_dependency(
    repo: CsvRepository, dataset_name: str, row: dict, changed_column: str | None
) -> dict:
    surface_name = row.get("name", "")
    construction_name = row.get("construction_name", "")
    space_name = row.get("space_name", "")
    property_name = changed_column or "name"
    impacts = []

    if construction_name:
        construction_rows = repo.find_rows("constructions.csv", "name", construction_name)
        if construction_rows:
            impacts.append(
                make_impact_entry(
                    "constructions.csv",
                    construction_rows,
                    f"{dataset_name}.construction_name={construction_name}",
                    "direct",
                    "Yuzey kaydi bir construction referansina baglidir.",
                )
            )

        layer_rows = repo.find_rows("construction_layers.csv", "construction_name", construction_name)
        if layer_rows:
            impacts.append(
                make_impact_entry(
                    "construction_layers.csv",
                    layer_rows,
                    "constructions.csv.name",
                    "indirect",
                    "Yuzeyde kullanilan construction'in katmanlari da dolayli etki zincirine dahildir.",
                )
            )

    if space_name:
        space_rows = repo.find_rows("spaces.csv", "name", space_name)
        if space_rows:
            impacts.append(
                make_impact_entry(
                    "spaces.csv",
                    space_rows,
                    f"{dataset_name}.space_name={space_name}",
                    "direct",
                    "Yuzey kaydi bir mekana baglidir.",
                )
            )

    for sub_surface_dataset in SUB_SURFACE_FILES:
        host_rows = repo.find_rows(sub_surface_dataset, "host_surface_name", surface_name)
        if host_rows:
            impacts.append(
                make_impact_entry(
                    sub_surface_dataset,
                    host_rows,
                    f"{dataset_name}.name={surface_name}",
                    "direct",
                    f"Bu yuzey '{surface_name}' ana yuzeyi olarak alt-yuzeylerde referans aliniyor; '{property_name}' degisimi host iliskisini etkiler.",
                )
            )

    return {
        "root_entity": "surface",
        "root_value": surface_name,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_sub_surface_dependency(
    repo: CsvRepository, dataset_name: str, row: dict, changed_column: str | None
) -> dict:
    item_name = row.get("name", "")
    construction_name = row.get("construction_name", "")
    host_surface_name = row.get("host_surface_name", "")
    property_name = changed_column or "name"
    impacts = []

    if construction_name:
        construction_rows = repo.find_rows("constructions.csv", "name", construction_name)
        if construction_rows:
            impacts.append(
                make_impact_entry(
                    "constructions.csv",
                    construction_rows,
                    f"{dataset_name}.construction_name={construction_name}",
                    "direct",
                    "Alt-yuzey kaydi bir construction referansina baglidir.",
                )
            )

        layer_rows = repo.find_rows("construction_layers.csv", "construction_name", construction_name)
        if layer_rows:
            impacts.append(
                make_impact_entry(
                    "construction_layers.csv",
                    layer_rows,
                    "constructions.csv.name",
                    "indirect",
                    "Alt-yuzeyde kullanilan construction'in katmanlari dolayli etki zincirine dahildir.",
                )
            )

    if host_surface_name:
        wall_rows = repo.find_rows("walls.csv", "name", host_surface_name)
        if wall_rows:
            impacts.append(
                make_impact_entry(
                    "walls.csv",
                    wall_rows,
                    f"{dataset_name}.host_surface_name={host_surface_name}",
                    "direct",
                    f"Alt-yuzey '{item_name}' ana yuzey olarak '{host_surface_name}' duvarina baglidir.",
                )
            )

    return {
        "root_entity": "sub_surface",
        "root_value": item_name,
        "changed_column": property_name,
        "impacts": impacts,
    }


def analyze_row_dependency(
    repo: CsvRepository,
    dataset_name: str,
    match_column: str,
    match_value: str,
    changed_column: str | None,
) -> dict:
    matched_rows = repo.find_rows(dataset_name, match_column, match_value)
    if not matched_rows:
        raise DependencyAnalysisError(
            f"'{dataset_name}' icinde {match_column}='{match_value}' icin kayit bulunamadi."
        )

    all_reports = []
    for row in matched_rows:
        if dataset_name == "materials.csv":
            report = analyze_material_dependency(repo, row, changed_column)
        elif dataset_name == "constructions.csv":
            report = analyze_construction_dependency(repo, row, changed_column)
        elif dataset_name == "construction_layers.csv":
            report = analyze_construction_layer_dependency(repo, row, changed_column)
        elif dataset_name == "spaces.csv":
            report = analyze_space_dependency(repo, row, changed_column)
        elif dataset_name == "zones.csv":
            report = analyze_zone_dependency(repo, row, changed_column)
        elif dataset_name in SURFACE_FILES:
            report = analyze_surface_dependency(repo, dataset_name, row, changed_column)
        elif dataset_name in SUB_SURFACE_FILES:
            report = analyze_sub_surface_dependency(repo, dataset_name, row, changed_column)
        else:
            raise DependencyAnalysisError(f"Bagimlilik analizi desteklenmeyen veri seti: {dataset_name}")

        report["matched_row"] = {
            "row_key": build_row_key(dataset_name, row),
            "preview": compact_row(
                row,
                DATASETS[dataset_name]["key_columns"] + DATASETS[dataset_name]["primary_fields"],
            ),
        }
        all_reports.append(report)

    return {
        "csv_root": repo.csv_root.as_posix(),
        "dataset": dataset_name,
        "match_column": match_column,
        "match_value": match_value,
        "changed_column": changed_column,
        "matched_row_count": len(matched_rows),
        "reports": all_reports,
    }


def build_change_entry(
    dataset_name: str,
    key: tuple[str, ...],
    column: str,
    old_value: str,
    new_value: str,
    status: str = "updated",
) -> dict:
    key_columns = DATASETS[dataset_name]["key_columns"]
    row_key = " | ".join(
        f"{key_column}={key_value}"
        for key_column, key_value in zip(key_columns, key)
    )
    return {
        "dataset": dataset_name,
        "row_key": row_key,
        "column": column,
        "old_value": old_value,
        "new_value": new_value,
        "change_type": status,
    }


def compare_dataset_states(
    old_repo: CsvRepository, new_repo: CsvRepository, dataset_name: str
) -> list[dict]:
    old_map = old_repo.get_row_map(dataset_name)
    new_map = new_repo.get_row_map(dataset_name)
    dataset = new_repo.require_dataset(dataset_name) if dataset_name in new_repo.datasets else old_repo.require_dataset(dataset_name)
    comparable_columns = [
        column for column in dataset["fieldnames"] if column not in dataset["config"]["key_columns"]
    ]

    changes = []
    old_keys = set(old_map)
    new_keys = set(new_map)

    for key in sorted(old_keys - new_keys):
        changes.append(
            build_change_entry(
                dataset_name,
                key,
                "__row__",
                json.dumps(old_map[key], ensure_ascii=False),
                "",
                "removed",
            )
        )

    for key in sorted(new_keys - old_keys):
        changes.append(
            build_change_entry(
                dataset_name,
                key,
                "__row__",
                "",
                json.dumps(new_map[key], ensure_ascii=False),
                "added",
            )
        )

    for key in sorted(old_keys & new_keys):
        old_row = old_map[key]
        new_row = new_map[key]
        for column in comparable_columns:
            old_value = str(old_row.get(column, ""))
            new_value = str(new_row.get(column, ""))
            if old_value == new_value:
                continue
            changes.append(
                build_change_entry(dataset_name, key, column, old_value, new_value, "updated")
            )

    return changes


def detect_state_changes(
    old_repo: CsvRepository, new_repo: CsvRepository, limit: int
) -> dict:
    all_datasets = sorted(set(old_repo.datasets) & set(new_repo.datasets))
    all_changes = []
    for dataset_name in all_datasets:
        all_changes.extend(compare_dataset_states(old_repo, new_repo, dataset_name))

    limited_changes = all_changes[: max(limit, 0)]
    return {
        "total_change_count": len(all_changes),
        "processed_change_count": len(limited_changes),
        "changes": limited_changes,
    }


def resolve_match_value_from_row_key(dataset_name: str, row_key: str) -> tuple[str, str]:
    key_columns = DATASETS[dataset_name]["key_columns"]
    parts = [part.strip() for part in row_key.split("|")]
    values_by_column = {}
    for part in parts:
        if "=" not in part:
            continue
        column, value = part.split("=", 1)
        values_by_column[column.strip()] = value

    first_key = key_columns[0]
    if first_key not in values_by_column:
        raise DependencyAnalysisError(
            f"Satir anahtari cozumlenemedi. Veri seti: {dataset_name}, satir anahtari: {row_key}"
        )
    return first_key, values_by_column[first_key]


def build_impact_analysis_from_changes(
    new_repo: CsvRepository, detected_changes: dict
) -> dict:
    results = []
    for change in detected_changes["changes"]:
        dataset_name = change["dataset"]
        if change["change_type"] != "updated":
            results.append(
                {
                    "change": change,
                    "status": "skipped",
                    "message": "Eklenen/silinen satirlar icin etki analizi bu surumde hesaplanmiyor.",
                    "impact_summary": {
                        "direct_count": 0,
                        "indirect_count": 0,
                        "total_affected_datasets": 0,
                    },
                    "impact_report": None,
                }
            )
            continue

        match_column, match_value = resolve_match_value_from_row_key(dataset_name, change["row_key"])
        impact_report = analyze_row_dependency(
            new_repo,
            dataset_name,
            match_column,
            match_value,
            change["column"],
        )

        direct_count = 0
        indirect_count = 0
        affected_datasets = set()
        for item in impact_report["reports"]:
            for impact in item["impacts"]:
                affected_datasets.add(impact["dataset"])
                if impact["impact_type"] == "direct":
                    direct_count += impact["affected_row_count"]
                else:
                    indirect_count += impact["affected_row_count"]

        results.append(
            {
                "change": change,
                "status": "analyzed",
                "message": "Etki analizi basariyla hesaplandi." if direct_count or indirect_count else "Degisiklik bulundu ancak bagli alan etkisi tespit edilmedi.",
                "impact_summary": {
                    "direct_count": direct_count,
                    "indirect_count": indirect_count,
                    "total_affected_datasets": len(affected_datasets),
                },
                "impact_report": impact_report,
            }
        )

    return {
        "old_root": detected_changes.get("old_root"),
        "new_root": detected_changes.get("new_root"),
        "trigger_mode": "state_diff",
        "total_change_count": detected_changes["total_change_count"],
        "processed_change_count": detected_changes["processed_change_count"],
        "results": results,
    }


def build_relationship_summary(repo: CsvRepository) -> list[dict]:
    summary = []
    for relationship in DIRECT_RELATIONSHIPS:
        source_dataset, source_column = relationship["source"]
        target_dataset, target_column = relationship["target"]
        if source_dataset not in repo.datasets or target_dataset not in repo.datasets:
            continue

        source_values = {
            row.get(source_column, "")
            for row in repo.get_rows(source_dataset)
            if row.get(source_column, "")
        }
        matched_rows = []
        for value in source_values:
            matched_rows.extend(repo.find_rows(target_dataset, target_column, value))

        summary.append(
            {
                "source_dataset": source_dataset,
                "source_column": source_column,
                "target_dataset": target_dataset,
                "target_column": target_column,
                "matched_row_count": len(matched_rows),
                "description": relationship["description"],
            }
        )
    return summary


def build_overview_report(repo: CsvRepository) -> dict:
    datasets = []
    for dataset_name, dataset in repo.datasets.items():
        config = dataset["config"]
        datasets.append(
            {
                "dataset": dataset_name,
                "row_count": len(dataset["rows"]),
                "key_columns": config["key_columns"],
                "primary_fields": config["primary_fields"],
                "fieldnames": dataset["fieldnames"],
            }
        )

    return {
        "csv_root": repo.csv_root.as_posix(),
        "trigger_mode": "overview",
        "dataset_count": len(datasets),
        "datasets": datasets,
        "direct_relationships": build_relationship_summary(repo),
    }


def render_markdown(report: dict) -> str:
    if "reports" in report:
        lines = [
            "# Bagimlilik Etki Raporu",
            "",
            f"- Veri seti: `{report['dataset']}`",
            f"- Eslesen satir sayisi: `{report['matched_row_count']}`",
            f"- Eslesen kosul: `{report['match_column']}={report['match_value']}`",
        ]
        if report.get("changed_column"):
            lines.append(f"- Degistigi varsayilan kolon: `{report['changed_column']}`")
        lines.append("")

        for item in report["reports"]:
            lines.append(f"## {item['matched_row']['row_key']}")
            lines.append("")
            lines.append("Eslesen satir:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(item["matched_row"]["preview"], ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")

            direct_impacts = [impact for impact in item["impacts"] if impact["impact_type"] == "direct"]
            indirect_impacts = [impact for impact in item["impacts"] if impact["impact_type"] == "indirect"]

            lines.append("Dogrudan etkiler:")
            if not direct_impacts:
                lines.append("- Yok")
            else:
                for impact in direct_impacts:
                    lines.append(
                        f"- `{impact['dataset']}` | satir: `{impact['affected_row_count']}` | neden: {impact['reason']}"
                    )
            lines.append("")

            lines.append("Dolayli etkiler:")
            if not indirect_impacts:
                lines.append("- Yok")
            else:
                for impact in indirect_impacts:
                    lines.append(
                        f"- `{impact['dataset']}` | satir: `{impact['affected_row_count']}` | neden: {impact['reason']}"
                    )
            lines.append("")
        return "\n".join(lines)

    if report.get("trigger_mode") == "state_diff":
        lines = [
            "# Otomatik Etki Analizi",
            "",
            f"- Eski state: `{report['old_root']}`",
            f"- Yeni state: `{report['new_root']}`",
            f"- Toplam degisim: `{report['total_change_count']}`",
            f"- Islenen degisim: `{report['processed_change_count']}`",
            "",
        ]

        if not report["results"]:
            lines.append("Degisiklik bulunamadi.")
            return "\n".join(lines)

        for result in report["results"]:
            change = result["change"]
            lines.append(
                f"## {change['dataset']} | {change['row_key']} | {change['column']}"
            )
            lines.append("")
            lines.append(f"- Degisim tipi: `{change['change_type']}`")
            lines.append(f"- Eski deger: `{change['old_value']}`")
            lines.append(f"- Yeni deger: `{change['new_value']}`")
            lines.append(f"- Durum: `{result['status']}`")
            lines.append(f"- Mesaj: {result['message']}")
            lines.append(
                f"- Ozet: direct=`{result['impact_summary']['direct_count']}`, indirect=`{result['impact_summary']['indirect_count']}`, dataset=`{result['impact_summary']['total_affected_datasets']}`"
            )
            lines.append("")

            impact_report = result["impact_report"]
            if not impact_report:
                continue

            for item in impact_report["reports"]:
                direct_impacts = [
                    impact for impact in item["impacts"] if impact["impact_type"] == "direct"
                ]
                indirect_impacts = [
                    impact for impact in item["impacts"] if impact["impact_type"] == "indirect"
                ]
                lines.append(f"- Kaynak satir: `{item['matched_row']['row_key']}`")
                if direct_impacts:
                    for impact in direct_impacts:
                        lines.append(
                            f"- Dogrudan: `{impact['dataset']}` satir=`{impact['affected_row_count']}`"
                        )
                if indirect_impacts:
                    for impact in indirect_impacts:
                        lines.append(
                            f"- Dolayli: `{impact['dataset']}` satir=`{impact['affected_row_count']}`"
                        )
                if not direct_impacts and not indirect_impacts:
                    lines.append("- Etki bulunamadi")
                lines.append("")
        return "\n".join(lines)

    lines = [
        "# CSV Bagimlilik Haritasi",
        "",
        f"- CSV klasoru: `{report['csv_root']}`",
        f"- Veri seti sayisi: `{report['dataset_count']}`",
        "",
        "## Veri Setleri",
        "",
    ]
    for dataset in report["datasets"]:
        lines.append(
            f"- `{dataset['dataset']}` | satir: `{dataset['row_count']}` | anahtar: `{', '.join(dataset['key_columns'])}` | ana alanlar: `{', '.join(dataset['primary_fields'])}`"
        )

    lines.extend(
        [
            "",
            "## Dogrudan Iliskiler",
            "",
        ]
    )
    for relationship in report["direct_relationships"]:
        lines.append(
            f"- `{relationship['source_dataset']}.{relationship['source_column']}` -> `{relationship['target_dataset']}.{relationship['target_column']}` | eslesen satir: `{relationship['matched_row_count']}` | {relationship['description']}"
        )
    return "\n".join(lines)


def write_output(output_path: Path, content: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()

    try:
        if args.old_root or args.new_root:
            if not args.old_root or not args.new_root:
                raise DependencyAnalysisError(
                    "--old-root ve --new-root birlikte verilmelidir."
                )
            old_repo = CsvRepository(Path(args.old_root))
            new_repo = CsvRepository(Path(args.new_root))
            detected_changes = detect_state_changes(old_repo, new_repo, args.limit)
            detected_changes["old_root"] = old_repo.csv_root.as_posix()
            detected_changes["new_root"] = new_repo.csv_root.as_posix()
            report = build_impact_analysis_from_changes(new_repo, detected_changes)
        else:
            repo = CsvRepository(Path(args.csv_root))

            if args.dataset:
                if not args.match_column or args.match_value is None:
                    raise DependencyAnalysisError(
                        "--dataset kullanildiginda --match-column ve --match-value zorunludur."
                    )
                report = analyze_row_dependency(
                    repo,
                    args.dataset,
                    args.match_column,
                    args.match_value,
                    args.changed_column,
                )
            else:
                report = build_overview_report(repo)

        if args.format == "md":
            output_text = render_markdown(report)
        else:
            output_text = json.dumps(report, ensure_ascii=False, indent=2)

        if args.output:
            write_output(Path(args.output), output_text)
        else:
            print(output_text)
        return 0
    except DependencyAnalysisError as error:
        print(f"Hata: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
