import csv
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path

from nicegui import ui

from analyze_csv_dependencies import (
    CsvRepository,
    DependencyAnalysisError,
    analyze_row_dependency,
)
from apply_scenario_definition import load_scenario_definition, run_scenario_definition
from build_simulation_output import build_manifest, build_output_paths, write_manifest
from update_csv_fields import CsvUpdateError


CSV_SEARCH_DIRS = [Path("csv_output"), Path("simulation_outputs")]
SCENARIO_DIR = Path("scenario_definitions")
SIMULATION_OUTPUT_DIR = Path("simulation_outputs")
MAX_PREVIEW_ROWS = 500
DEFAULT_ROWS_PER_PAGE = 20
COMMON_CSV_ORDER = [
    "csv_output/materials.csv",
    "csv_output/construction_layers.csv",
    "csv_output/walls.csv",
    "csv_output/floors.csv",
    "csv_output/windows.csv",
]


def collect_csv_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*.csv")))
    return files


def collect_log_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*changes.json")))
            files.extend(sorted(directory.rglob("*changes.csv")))
    return files


def collect_scenario_files() -> list[Path]:
    if not SCENARIO_DIR.exists():
        return []
    return sorted(SCENARIO_DIR.rglob("*.json"))


def collect_manifest_files() -> list[Path]:
    if not SIMULATION_OUTPUT_DIR.exists():
        return []
    return sorted(SIMULATION_OUTPUT_DIR.rglob("*__manifest.json"))


def read_json_file(path: Path) -> dict | list:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_csv_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            return [], []

        rows = []
        for index, row in enumerate(reader, start=1):
            normalized_row = {key: value for key, value in row.items()}
            normalized_row["__row_id"] = index
            rows.append(normalized_row)

        return rows, reader.fieldnames


def read_log_rows(log_path: Path) -> tuple[list[dict], list[str]]:
    if log_path.suffix.lower() == ".json":
        raw_data = read_json_file(log_path)
        if not isinstance(raw_data, list):
            return [], []

        rows = []
        fieldnames = []
        for index, item in enumerate(raw_data, start=1):
            if not isinstance(item, dict):
                continue
            row = {key: value for key, value in item.items()}
            row["__row_id"] = index
            rows.append(row)
            for key in row.keys():
                if key != "__row_id" and key not in fieldnames:
                    fieldnames.append(key)
        return rows, fieldnames

    return read_csv_rows(log_path)


def read_manifest_entries() -> list[dict]:
    manifests = []
    for manifest_path in collect_manifest_files():
        raw_data = read_json_file(manifest_path)
        if not isinstance(raw_data, dict):
            continue

        entry = dict(raw_data)
        entry["manifest_path"] = manifest_path.as_posix()
        entry["manifest_mtime"] = manifest_path.stat().st_mtime
        manifests.append(entry)

    manifests.sort(key=lambda item: item.get("manifest_mtime", 0))
    return manifests


def get_initial_csv(options: list[str]) -> str | None:
    for expected in COMMON_CSV_ORDER:
        if expected in options:
            return expected
    return options[0] if options else None


def get_initial_log(options: list[str]) -> str | None:
    return options[0] if options else None


def get_initial_scenario(options: list[str]) -> str | None:
    return options[0] if options else None


def filter_rows(
    rows: list[dict],
    global_query: str = "",
    column_name: str = "",
    column_query: str = "",
) -> list[dict]:
    filtered_rows = rows
    normalized_global = global_query.strip().lower()
    normalized_column = column_query.strip().lower()

    if normalized_global:
        filtered_rows = [
            row
            for row in filtered_rows
            if any(
                normalized_global in str(value).lower()
                for key, value in row.items()
                if key != "__row_id"
            )
        ]

    if column_name and normalized_column:
        filtered_rows = [
            row
            for row in filtered_rows
            if normalized_column in str(row.get(column_name, "")).lower()
        ]

    return filtered_rows


def open_row_detail(title: str, row: dict, fieldnames: list[str]) -> None:
    with ui.dialog() as dialog, ui.card().classes("min-w-[24rem] max-w-3xl w-full"):
        ui.label(title).classes("text-lg font-medium")
        with ui.column().classes("w-full gap-2"):
            for field in fieldnames:
                with ui.row().classes("w-full justify-between items-start gap-4"):
                    ui.label(field).classes("text-sm text-slate-500")
                    ui.label(str(row.get(field, ""))).classes("text-sm text-right break-all")
        ui.button("Kapat", on_click=dialog.close).props("flat color=primary")
    dialog.open()


def format_scenario_markdown(scenario: dict) -> str:
    operations = scenario.get("operations", [])
    operation_lines = []
    for operation in operations:
        match = operation.get("match", {})
        updates = operation.get("updates", {})
        updates_text = ", ".join(f"{key}={value}" for key, value in updates.items()) or "-"
        operation_lines.append(
            f"- **{operation.get('name', 'islem')}**: "
            f"`{match.get('column', '-')}` = `{match.get('value', '-')}` -> {updates_text}"
        )

    return "\n".join(
        [
            f"**Senaryo:** {scenario.get('scenario_name', '-')}",
            f"**Aciklama:** {scenario.get('description', '-')}",
            f"**Girdi:** `{scenario.get('input', '-')}`",
            "",
            "**Islemler:**",
            *operation_lines,
        ]
    )


def try_parse_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_delta(old_value: object, new_value: object) -> tuple[str, str]:
    old_number = try_parse_number(old_value)
    new_number = try_parse_number(new_value)
    if old_number is None or new_number is None:
        return "-", "Degisim"

    delta = new_number - old_number
    if delta > 0:
        direction = "Artis"
    elif delta < 0:
        direction = "Azalis"
    else:
        direction = "Sabit"
    return f"{delta:.4f}".rstrip("0").rstrip("."), direction


def build_impact_rows_for_scenario(
    scenario_path: Path, scenario: dict, log_path: Path
) -> tuple[list[dict], str]:
    if not log_path.exists():
        return [], "Senaryo etkilerini gormek icin once hazirlik akislarini calistirin."

    log_rows, _ = read_log_rows(log_path)
    if not log_rows:
        return [], "Secili senaryo icin degisiklik kaydi bulunamadi."

    input_path = Path(scenario["input"])
    repo = CsvRepository(input_path.parent)
    operations_by_name = {
        operation.get("name", f"operation_{index}"): operation
        for index, operation in enumerate(scenario.get("operations", []), start=1)
    }

    impact_rows = []
    for log_row in log_rows:
        operation_name = str(log_row.get("islem", ""))
        operation = operations_by_name.get(operation_name)
        if operation is None:
            continue

        match = operation.get("match", {})
        match_column = str(match.get("column", "")).strip()
        match_value = str(match.get("value", "")).strip()
        changed_column = str(log_row.get("kolon", "")).strip()
        if not match_column or not match_value or not changed_column:
            continue

        try:
            impact_report = analyze_row_dependency(
                repo,
                input_path.name,
                match_column,
                match_value,
                changed_column,
            )
        except DependencyAnalysisError:
            continue

        old_value = str(log_row.get("eski_deger", ""))
        new_value = str(log_row.get("yeni_deger", ""))
        delta_text, direction = format_delta(old_value, new_value)
        old_number = try_parse_number(old_value)
        new_number = try_parse_number(new_value)
        delta_numeric = None
        if old_number is not None and new_number is not None:
            delta_numeric = new_number - old_number

        for item in impact_report["reports"]:
            impacts = item.get("impacts", [])
            if not impacts:
                impact_rows.append(
                    {
                        "id": f"{operation_name}-{changed_column}-empty",
                        "degisen_alan": changed_column,
                        "eski_deger": old_value or "-",
                        "yeni_deger": new_value or "-",
                        "degisim_miktari": delta_text,
                        "degisim_numeric": delta_numeric,
                        "yon": direction,
                        "etki_tipi": "Yok",
                        "etkilenen_veri": "-",
                        "etkilenen_satir": 0,
                        "kaynak": f"{match_column}={match_value}",
                        "neden": "Bagli etki bulunamadi.",
                    }
                )
                continue

            for impact in impacts:
                impact_rows.append(
                    {
                        "id": (
                            f"{operation_name}-{changed_column}-"
                            f"{impact['impact_type']}-{impact['dataset']}"
                        ),
                        "degisen_alan": changed_column,
                        "eski_deger": old_value or "-",
                        "yeni_deger": new_value or "-",
                        "degisim_miktari": delta_text,
                        "degisim_numeric": delta_numeric,
                        "yon": direction,
                        "etki_tipi": "Dogrudan" if impact["impact_type"] == "direct" else "Dolayli",
                        "etkilenen_veri": impact["dataset"],
                        "etkilenen_satir": impact["affected_row_count"],
                        "kaynak": f"{match_column}={match_value}",
                        "neden": impact["reason"],
                    }
                )

    if not impact_rows:
        return [], "Etki analizi icin uygun degisiklik kaydi bulunamadi."

    return impact_rows, (
        f"Senaryo: {scenario.get('scenario_name', scenario_path.stem)} | "
        f"Toplam etki kaydi: {len(impact_rows)}"
    )


def filter_impact_rows(
    impact_rows: list[dict],
    query: str = "",
    impact_type: str = "Tum Etkiler",
    sort_mode: str = "Varsayilan",
) -> list[dict]:
    filtered_rows = impact_rows
    normalized_query = query.strip().lower()

    if normalized_query:
        filtered_rows = [
            row
            for row in filtered_rows
            if any(
                normalized_query in str(row.get(field, "")).lower()
                for field in ["degisen_alan", "etkilenen_veri", "kaynak", "neden"]
            )
        ]

    if impact_type == "Sadece Dogrudan":
        filtered_rows = [row for row in filtered_rows if row.get("etki_tipi") == "Dogrudan"]
    elif impact_type == "Sadece Dolayli":
        filtered_rows = [row for row in filtered_rows if row.get("etki_tipi") == "Dolayli"]

    if sort_mode == "En Buyuk Degisim":
        filtered_rows = sorted(
            filtered_rows,
            key=lambda row: abs(row.get("degisim_numeric") or 0),
            reverse=True,
        )
    elif sort_mode == "En Fazla Etki":
        filtered_rows = sorted(
            filtered_rows,
            key=lambda row: int(row.get("etkilenen_satir", 0)),
            reverse=True,
        )

    return filtered_rows


def build_impact_summary(impact_rows: list[dict]) -> dict:
    if not impact_rows:
        return {
            "changed_fields": "-",
            "total_rows": 0,
            "direct_rows": 0,
            "indirect_rows": 0,
            "critical_message": "Henuz ozet olusturulacak etki kaydi yok.",
            "critical_tone": "neutral",
        }

    changed_fields = sorted(
        {
            str(row.get("degisen_alan", "")).strip()
            for row in impact_rows
            if str(row.get("degisen_alan", "")).strip()
        }
    )
    direct_rows = sum(
        int(row.get("etkilenen_satir", 0))
        for row in impact_rows
        if row.get("etki_tipi") == "Dogrudan"
    )
    indirect_rows = sum(
        int(row.get("etkilenen_satir", 0))
        for row in impact_rows
        if row.get("etki_tipi") == "Dolayli"
    )
    total_rows = direct_rows + indirect_rows

    if total_rows >= 20 or indirect_rows >= 15:
        critical_message = "Kritik etki: degisiklik genis bir bagimlilik zincirine yayiliyor."
        critical_tone = "critical"
    elif total_rows > 0:
        critical_message = "Degisiklik birden fazla bagli alani etkiliyor."
        critical_tone = "warning"
    else:
        critical_message = "Belirgin bagli etki tespit edilmedi."
        critical_tone = "neutral"

    return {
        "changed_fields": ", ".join(changed_fields) if changed_fields else "-",
        "total_rows": total_rows,
        "direct_rows": direct_rows,
        "indirect_rows": indirect_rows,
        "critical_message": critical_message,
        "critical_tone": critical_tone,
    }


def build_impact_chart_model(impact_rows: list[dict]) -> dict:
    change_groups = {}
    dataset_groups = {}

    for row in impact_rows:
        change_key = (str(row.get("kaynak", "")), str(row.get("degisen_alan", "")))
        if change_key not in change_groups:
            change_groups[change_key] = {
                "label": f"{change_key[0]} | {change_key[1]}",
                "old_value": row.get("eski_deger", "-"),
                "new_value": row.get("yeni_deger", "-"),
                "direct_rows": 0,
                "indirect_rows": 0,
            }
        if row.get("etki_tipi") == "Dogrudan":
            change_groups[change_key]["direct_rows"] += int(row.get("etkilenen_satir", 0))
        elif row.get("etki_tipi") == "Dolayli":
            change_groups[change_key]["indirect_rows"] += int(row.get("etkilenen_satir", 0))

        dataset_name = str(row.get("etkilenen_veri", "-"))
        impact_type = str(row.get("etki_tipi", "Yok"))
        dataset_groups.setdefault(
            dataset_name,
            {"dataset": dataset_name, "Dogrudan": 0, "Dolayli": 0},
        )
        if impact_type in {"Dogrudan", "Dolayli"}:
            dataset_groups[dataset_name][impact_type] += int(row.get("etkilenen_satir", 0))

    comparison_labels = []
    old_values = []
    new_values = []
    highlight_values = []
    for item in change_groups.values():
        comparison_labels.append(item["label"])
        old_number = try_parse_number(item["old_value"])
        new_number = try_parse_number(item["new_value"])
        delta_number = None
        if old_number is not None and new_number is not None:
            delta_number = new_number - old_number

        common_meta = {
            "old_value": item["old_value"],
            "new_value": item["new_value"],
            "delta": delta_number,
            "direct_rows": item["direct_rows"],
            "indirect_rows": item["indirect_rows"],
        }
        old_values.append(
            {
                "value": old_number,
                "meta": common_meta,
                "itemStyle": {"color": "#94a3b8"},
            }
        )
        new_values.append(
            {
                "value": new_number,
                "meta": common_meta,
                "itemStyle": {
                    "color": "#0f766e",
                    "borderColor": "#134e4a",
                    "borderWidth": 2,
                },
            }
        )
        highlight_values.append(
            {
                "value": new_number,
                "meta": common_meta,
                "itemStyle": {"color": "#dc2626"},
            }
        )

    dataset_labels = []
    direct_values = []
    indirect_values = []
    for item in sorted(
        dataset_groups.values(),
        key=lambda value: value["Dogrudan"] + value["Dolayli"],
        reverse=True,
    ):
        dataset_labels.append(item["dataset"])
        direct_values.append(item["Dogrudan"])
        indirect_values.append(item["Dolayli"])

    relation_nodes = []
    relation_links = []
    source_nodes = {}
    direct_nodes = {}
    indirect_nodes = {}
    direct_link_totals = defaultdict(int)
    indirect_link_totals = defaultdict(int)

    for row in impact_rows:
        source_key = (str(row.get("kaynak", "-")), str(row.get("degisen_alan", "-")))
        source_id = f"source::{source_key[0]}::{source_key[1]}"
        source_label = f"{source_key[0]}\n{source_key[1]}"
        if source_id not in source_nodes:
            source_nodes[source_id] = {
                "id": source_id,
                "name": source_label,
                "symbolSize": 58,
                "category": 0,
                "x": 0,
                "y": 0,
                "fixed": True,
                "itemStyle": {"color": "#0f766e", "borderColor": "#134e4a", "borderWidth": 3},
                "value": {
                    "type": "source",
                    "label": source_label,
                },
            }

        target_dataset = str(row.get("etkilenen_veri", "-"))
        impact_type = str(row.get("etki_tipi", "Yok"))
        affected_rows = int(row.get("etkilenen_satir", 0))

        if impact_type == "Dogrudan":
            direct_id = f"direct::{target_dataset}"
            if direct_id not in direct_nodes:
                direct_nodes[direct_id] = {
                    "id": direct_id,
                    "name": target_dataset,
                    "symbolSize": 38,
                    "category": 1,
                    "itemStyle": {"color": "#84cc16", "borderColor": "#4d7c0f", "borderWidth": 2},
                    "value": {
                        "type": "direct",
                        "label": target_dataset,
                    },
                }
            direct_link_totals[(source_id, direct_id)] += affected_rows
            continue

        if impact_type == "Dolayli":
            indirect_id = f"indirect::{target_dataset}"
            if indirect_id not in indirect_nodes:
                indirect_nodes[indirect_id] = {
                    "id": indirect_id,
                    "name": target_dataset,
                    "symbolSize": 30,
                    "category": 2,
                    "itemStyle": {"color": "#f59e0b", "borderColor": "#b45309", "borderWidth": 2},
                    "value": {
                        "type": "indirect",
                        "label": target_dataset,
                    },
                }
            indirect_link_totals[(source_id, indirect_id)] += affected_rows

    relation_nodes.extend(source_nodes.values())
    relation_nodes.extend(direct_nodes.values())
    relation_nodes.extend(indirect_nodes.values())

    for (source_id, direct_id), total in direct_link_totals.items():
        relation_links.append(
            {
                "source": source_id,
                "target": direct_id,
                "value": total,
                "lineStyle": {"color": "#84cc16", "width": 3, "curveness": 0.08},
                "label": {"show": total > 0, "formatter": str(total)},
            }
        )

    for (source_id, indirect_id), total in indirect_link_totals.items():
        relation_links.append(
            {
                "source": source_id,
                "target": indirect_id,
                "value": total,
                "lineStyle": {"color": "#f59e0b", "type": "dashed", "width": 2, "curveness": 0.2},
                "label": {"show": False},
            }
        )

    return {
        "comparison": {
            "labels": comparison_labels,
            "old_values": old_values,
            "new_values": new_values,
            "highlight_values": highlight_values,
        },
        "distribution": {
            "labels": dataset_labels,
            "direct_values": direct_values,
            "indirect_values": indirect_values,
        },
        "relations": {
            "nodes": relation_nodes,
            "links": relation_links,
            "categories": [
                {"name": "Ana Degisim"},
                {"name": "Dogrudan Etki"},
                {"name": "Dolayli Etki"},
            ],
        },
    }


def build_recent_scenarios_markdown(manifests: list[dict]) -> str:
    if not manifests:
        return "Henuz senaryo cikti paketi uretilmedi."

    recent_entries = manifests[-5:]
    lines = []
    for manifest in reversed(recent_entries):
        lines.append(
            f"- **{manifest.get('scenario_name', '-')}** | "
            f"degisen alan: {manifest.get('changed_field_count', 0)} | "
            f"islem: {manifest.get('operation_count', 0)}"
        )
    return "\n".join(lines)


def scenario_output_targets(scenario_path: Path) -> tuple[Path, Path, Path]:
    scenario = load_scenario_definition(scenario_path)
    scenario_copy = deepcopy(scenario)
    input_path = Path(scenario_copy["input"])
    return build_output_paths(scenario_copy["scenario_name"], input_path, SIMULATION_OUTPUT_DIR)


@ui.page("/")
def main_page() -> None:
    ui.page_title("CSV Izleme Paneli")
    dark_mode = ui.dark_mode()

    state = {
        "csv_files": [path.as_posix() for path in collect_csv_files()],
        "log_files": [path.as_posix() for path in collect_log_files()],
        "scenario_files": [path.as_posix() for path in collect_scenario_files()],
    }

    selected_csv = get_initial_csv(state["csv_files"])
    selected_log = get_initial_log(state["log_files"])
    selected_scenario = get_initial_scenario(state["scenario_files"])

    with ui.header().classes("items-center justify-between bg-slate-800 text-white"):
        ui.label("CSV ve Senaryo Izleme Paneli").classes("text-lg font-medium")
        with ui.row().classes("items-center gap-3"):
            ui.label("Koyu Tema").classes("text-sm")
            ui.switch(value=False, on_change=lambda e: dark_mode.set_value(bool(e.value)))

    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-5"):
        ui.label(
            "CSV verileri, degisiklik loglari ve senaryo ciktilarini tek ekranda izlemek icin gelistirilmis panel."
        ).classes("text-base text-slate-700")

        with ui.row().classes("w-full gap-4 items-stretch"):
            with ui.card().classes("w-full"):
                ui.label("Toplam Senaryo Ciktisi").classes("text-sm text-slate-500")
                total_scenarios_value = ui.label("0").classes("text-3xl font-bold")

            with ui.card().classes("w-full"):
                ui.label("Toplam Degisen Alan").classes("text-sm text-slate-500")
                total_changes_value = ui.label("0").classes("text-3xl font-bold")

            with ui.card().classes("w-full"):
                ui.label("Son Calistirilan Senaryo").classes("text-sm text-slate-500")
                last_scenario_value = ui.label("-").classes("text-lg font-medium")

        with ui.tabs().classes("w-full") as tabs:
            data_tab = ui.tab("Veri")
            logs_tab = ui.tab("Loglar")
            scenarios_tab = ui.tab("Senaryolar")
            analytics_tab = ui.tab("Analiz")

        with ui.tab_panels(tabs, value=data_tab).classes("w-full"):
            with ui.tab_panel(data_tab):
                with ui.card().classes("w-full"):
                    ui.label("Hizli Erisim").classes("text-base font-medium")
                    quick_access_row = ui.row().classes("w-full gap-2")

                with ui.card().classes("w-full"):
                    ui.label("CSV Veri Tablosu").classes("text-base font-medium")
                    csv_select = ui.select(
                        options=state["csv_files"],
                        value=selected_csv,
                        label="CSV dosyasi",
                    ).classes("w-full")
                    with ui.row().classes("w-full gap-4"):
                        global_search = ui.input(
                            label="Genel arama",
                            placeholder="Tum kolonlarda ara",
                        ).classes("w-full")
                        column_filter_select = ui.select(
                            options=[],
                            label="Kolon filtresi",
                        ).classes("w-full")
                        column_filter_input = ui.input(
                            label="Kolon degeri",
                            placeholder="Secilen kolon icinde filtrele",
                        ).classes("w-full")
                    rows_per_page = ui.select(
                        options=[10, 20, 50, 100],
                        value=DEFAULT_ROWS_PER_PAGE,
                        label="Sayfa basina satir",
                    ).classes("w-40")
                    csv_info = ui.label("").classes("text-sm text-slate-600")
                    csv_table_container = ui.column().classes("w-full")

                def refresh_quick_access() -> None:
                    quick_access_row.clear()
                    with quick_access_row:
                        for quick_file in COMMON_CSV_ORDER:
                            if quick_file not in state["csv_files"]:
                                continue
                            ui.button(
                                Path(quick_file).name,
                                on_click=lambda path=quick_file: csv_select.set_value(path),
                            ).props("outline size=sm")

                def refresh_csv_table() -> None:
                    csv_table_container.clear()
                    selected_value = csv_select.value
                    if not selected_value:
                        csv_info.set_text("Lutfen bir CSV dosyasi secin.")
                        return

                    csv_path = Path(selected_value)
                    if not csv_path.exists():
                        csv_info.set_text(f"Dosya bulunamadi: {selected_value}")
                        return

                    rows, fieldnames = read_csv_rows(csv_path)
                    column_filter_select.options = fieldnames
                    column_filter_select.update()
                    if fieldnames and column_filter_select.value not in fieldnames:
                        column_filter_select.set_value(fieldnames[0])

                    filtered_rows = filter_rows(
                        rows,
                        global_query=global_search.value or "",
                        column_name=column_filter_select.value or "",
                        column_query=column_filter_input.value or "",
                    )
                    preview_rows = filtered_rows[:MAX_PREVIEW_ROWS]

                    csv_info.set_text(
                        f"Dosya: {csv_path.as_posix()} | Toplam satir: {len(rows)} | "
                        f"Filtrelenen: {len(filtered_rows)} | Onizleme: {len(preview_rows)}"
                    )

                    with csv_table_container:
                        if not fieldnames:
                            ui.label("CSV baslik satiri bulunamadi.").classes("text-red-600")
                            return

                        table = ui.table(
                            columns=[
                                {"name": field, "label": field, "field": field, "sortable": True}
                                for field in fieldnames
                            ],
                            rows=preview_rows,
                            row_key="__row_id",
                            pagination={"rowsPerPage": int(rows_per_page.value)},
                        ).classes("w-full")
                        table.on(
                            "rowClick",
                            lambda event, columns=fieldnames: open_row_detail(
                                "Satir Detayi",
                                event.args["row"],
                                columns,
                            ),
                        )

                        if len(filtered_rows) > MAX_PREVIEW_ROWS:
                            ui.label(
                                f"Performans icin ilk {MAX_PREVIEW_ROWS} satir gosteriliyor."
                            ).classes("text-sm text-amber-700")

                csv_select.on_value_change(lambda _: refresh_csv_table())
                global_search.on_value_change(lambda _: refresh_csv_table())
                column_filter_select.on_value_change(lambda _: refresh_csv_table())
                column_filter_input.on_value_change(lambda _: refresh_csv_table())
                rows_per_page.on_value_change(lambda _: refresh_csv_table())
                ui.button("Veri Tablosunu Yenile", on_click=refresh_csv_table).props("outline")

                refresh_quick_access()
                refresh_csv_table()

            with ui.tab_panel(logs_tab):
                with ui.card().classes("w-full"):
                    ui.label("Degisiklik Gecmisi").classes("text-base font-medium")
                    log_select = ui.select(
                        options=state["log_files"],
                        value=selected_log,
                        label="Log dosyasi",
                    ).classes("w-full")
                    with ui.row().classes("w-full gap-4"):
                        log_file_filter = ui.input(label="Dosya filtresi").classes("w-full")
                        log_column_filter = ui.input(label="Kolon filtresi").classes("w-full")
                        log_operation_filter = ui.input(label="Senaryo / islem filtresi").classes("w-full")
                    log_info = ui.label("").classes("text-sm text-slate-600")
                    log_table_container = ui.column().classes("w-full")

                def refresh_log_table() -> None:
                    log_table_container.clear()
                    selected_value = log_select.value
                    if not selected_value:
                        log_info.set_text("Lutfen bir log dosyasi secin.")
                        return

                    log_path = Path(selected_value)
                    if not log_path.exists():
                        log_info.set_text(f"Log dosyasi bulunamadi: {selected_value}")
                        return

                    rows, fieldnames = read_log_rows(log_path)
                    filtered_rows = rows

                    if log_file_filter.value:
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if log_file_filter.value.lower() in str(row.get("dosya", "")).lower()
                        ]

                    if log_column_filter.value:
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if log_column_filter.value.lower() in str(row.get("kolon", "")).lower()
                        ]

                    if log_operation_filter.value:
                        filtered_rows = [
                            row
                            for row in filtered_rows
                            if any(
                                log_operation_filter.value.lower() in str(row.get(key, "")).lower()
                                for key in ["islem", "dosya", "kolon"]
                            )
                        ]

                    log_info.set_text(
                        f"Log dosyasi: {log_path.as_posix()} | Toplam kayit: {len(rows)} | "
                        f"Filtrelenen: {len(filtered_rows)}"
                    )

                    with log_table_container:
                        if not fieldnames:
                            ui.label("Log kaydi bulunamadi.").classes("text-red-600")
                            return

                        table = ui.table(
                            columns=[
                                {"name": field, "label": field, "field": field, "sortable": True}
                                for field in fieldnames
                            ],
                            rows=filtered_rows[:MAX_PREVIEW_ROWS],
                            row_key="__row_id",
                            pagination={"rowsPerPage": 10},
                        ).classes("w-full")
                        table.on(
                            "rowClick",
                            lambda event, columns=fieldnames: open_row_detail(
                                "Log Kaydi Detayi",
                                event.args["row"],
                                columns,
                            ),
                        )

                log_select.on_value_change(lambda _: refresh_log_table())
                log_file_filter.on_value_change(lambda _: refresh_log_table())
                log_column_filter.on_value_change(lambda _: refresh_log_table())
                log_operation_filter.on_value_change(lambda _: refresh_log_table())
                ui.button("Log Tablosunu Yenile", on_click=refresh_log_table).props("outline")
                refresh_log_table()

            with ui.tab_panel(scenarios_tab):
                with ui.card().classes("w-full"):
                    ui.label("Kayitli Senaryolar").classes("text-base font-medium")
                    scenarios_grid = ui.row().classes("w-full gap-4")
                    scenario_select = ui.select(
                        options=state["scenario_files"],
                        value=selected_scenario,
                        label="Senaryo sec",
                    ).classes("w-full")
                    scenario_summary = ui.label("").classes("text-sm text-slate-600")
                    scenario_detail = ui.markdown("").classes("w-full text-sm")
                    recent_scenarios = ui.markdown("").classes("w-full text-sm")
                    with ui.row().classes("gap-2"):
                        open_output_button = ui.button("Cikti Veri Dosyasini Goster").props("outline")
                        open_log_button = ui.button("Cikti Log Dosyasini Goster").props("outline")
                        run_button = ui.button("Hazirlik Akisini Baslat").props("color=primary")

                with ui.card().classes("w-full"):
                    ui.label("Degisim Ozeti").classes("text-base font-medium")
                    summary_hint = ui.label(
                        "Detay listeye girmeden once degisikligin genel etkisi burada gorunecek."
                    ).classes("text-sm text-slate-600")
                    with ui.row().classes("w-full gap-4 items-stretch"):
                        with ui.card().classes("w-full bg-slate-50"):
                            ui.label("Degisen Ana Alan").classes("text-sm text-slate-500")
                            changed_field_value = ui.label("-").classes("text-lg font-medium")
                        with ui.card().classes("w-full bg-slate-50"):
                            ui.label("Toplam Etkilenen Satir").classes("text-sm text-slate-500")
                            total_impact_value = ui.label("0").classes("text-3xl font-bold")
                        with ui.card().classes("w-full bg-emerald-50"):
                            ui.label("Dogrudan Etki").classes("text-sm text-emerald-700")
                            direct_impact_value = ui.label("0").classes("text-3xl font-bold text-emerald-700")
                        with ui.card().classes("w-full bg-amber-50"):
                            ui.label("Dolayli Etki").classes("text-sm text-amber-700")
                            indirect_impact_value = ui.label("0").classes("text-3xl font-bold text-amber-700")
                    critical_impact_banner = ui.label(
                        "Kritik etki bilgisi burada gosterilecek."
                    ).classes("w-full rounded-md px-3 py-2 text-sm bg-slate-100 text-slate-700")

                with ui.card().classes("w-full"):
                    ui.label("Etkilenen Alanlar").classes("text-base font-medium")
                    impact_summary = ui.label(
                        "Bir senaryo sectiginizde etkilenen alanlar burada listelenecek."
                    ).classes("text-sm text-slate-600")
                    impact_error = ui.label("").classes("text-sm text-red-600")
                    with ui.row().classes("w-full gap-4 items-end"):
                        impact_search_input = ui.input(
                            label="Etki icinde ara",
                            placeholder="Alan, veri seti veya kaynak ara",
                        ).classes("w-full")
                        impact_type_filter = ui.select(
                            options=["Tum Etkiler", "Sadece Dogrudan", "Sadece Dolayli"],
                            value="Tum Etkiler",
                            label="Etki tipi",
                        ).classes("w-56")
                        impact_sort_select = ui.select(
                            options=["Varsayilan", "En Buyuk Degisim", "En Fazla Etki"],
                            value="Varsayilan",
                            label="Siralama",
                        ).classes("w-56")
                        clear_impact_filters_button = ui.button("Filtreleri Temizle").props("outline")
                    impact_table_container = ui.column().classes("w-full")

                with ui.card().classes("w-full"):
                    ui.label("Grafik Onizleme").classes("text-base font-medium")
                    impact_chart_info = ui.label(
                        "Grafik altyapisi secili senaryonun etki verisiyle beslenecek."
                    ).classes("text-sm text-slate-600")
                    change_comparison_chart = ui.echart(
                        {
                            "tooltip": {
                                "trigger": "axis",
                            },
                            "legend": {"data": ["Eski Deger", "Yeni Deger", "Ana Degisim"]},
                            "grid": {"left": 48, "right": 24, "top": 48, "bottom": 90},
                            "xAxis": {
                                "type": "category",
                                "data": [],
                                "axisLabel": {"interval": 0, "rotate": 20},
                            },
                            "yAxis": {"type": "value"},
                            "series": [
                                {"name": "Eski Deger", "type": "bar", "data": []},
                                {"name": "Yeni Deger", "type": "bar", "data": []},
                                {
                                    "name": "Ana Degisim",
                                    "type": "scatter",
                                    "symbolSize": 18,
                                    "data": [],
                                    "itemStyle": {"color": "#dc2626"},
                                    "z": 5,
                                },
                            ],
                        }
                    ).classes("w-full h-80")
                    impact_distribution_chart = ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["Dogrudan", "Dolayli"]},
                            "grid": {"left": 48, "right": 24, "top": 48, "bottom": 90},
                            "xAxis": {
                                "type": "category",
                                "data": [],
                                "axisLabel": {"interval": 0, "rotate": 20},
                            },
                            "yAxis": {"type": "value"},
                            "series": [
                                {
                                    "name": "Dogrudan",
                                    "type": "bar",
                                    "stack": "etki",
                                    "data": [],
                                    "itemStyle": {"color": "#059669"},
                                },
                                {
                                    "name": "Dolayli",
                                    "type": "bar",
                                    "stack": "etki",
                                    "data": [],
                                    "itemStyle": {"color": "#d97706"},
                                },
                            ],
                        }
                    ).classes("w-full h-80")
                    relation_graph = ui.echart(
                        {
                            "tooltip": {
                                "trigger": "item",
                            },
                            "legend": [
                                {
                                    "data": ["Ana Degisim", "Dogrudan Etki", "Dolayli Etki"],
                                    "top": 0,
                                }
                            ],
                            "series": [
                                {
                                    "type": "graph",
                                    "layout": "force",
                                    "roam": True,
                                    "label": {"show": True, "formatter": "{b}"},
                                    "force": {"repulsion": 260, "edgeLength": 150, "gravity": 0.08},
                                    "draggable": True,
                                    "categories": [],
                                    "data": [],
                                    "links": [],
                                    "lineStyle": {"opacity": 0.65, "width": 2},
                                    "emphasis": {"focus": "adjacency"},
                                }
                            ],
                        }
                    ).classes("w-full h-96")

                def refresh_state_sources() -> None:
                    state["csv_files"] = [path.as_posix() for path in collect_csv_files()]
                    state["log_files"] = [path.as_posix() for path in collect_log_files()]
                    state["scenario_files"] = [path.as_posix() for path in collect_scenario_files()]

                    csv_select.options = state["csv_files"]
                    csv_select.update()
                    log_select.options = state["log_files"]
                    log_select.update()
                    scenario_select.options = state["scenario_files"]
                    scenario_select.update()

                    if csv_select.value not in state["csv_files"] and state["csv_files"]:
                        csv_select.set_value(get_initial_csv(state["csv_files"]))
                    if log_select.value not in state["log_files"] and state["log_files"]:
                        log_select.set_value(get_initial_log(state["log_files"]))
                    if scenario_select.value not in state["scenario_files"] and state["scenario_files"]:
                        scenario_select.set_value(get_initial_scenario(state["scenario_files"]))

                    refresh_quick_access()
                    refresh_scenario_cards()
                    refresh_recent_scenarios()

                def focus_output_file() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        ui.notify("Lutfen once bir senaryo secin.", color="warning")
                        return

                    output_path, _, _ = scenario_output_targets(Path(selected_value))
                    normalized = output_path.as_posix()
                    if normalized not in state["csv_files"]:
                        ui.notify("Senaryo cikti veri dosyasi henuz uretilmedi.", color="warning")
                        return

                    csv_select.set_value(normalized)
                    refresh_csv_table()
                    ui.notify("Senaryo cikti veri dosyasi acildi.", color="positive")

                def focus_log_file() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        ui.notify("Lutfen once bir senaryo secin.", color="warning")
                        return

                    _, log_path, _ = scenario_output_targets(Path(selected_value))
                    normalized = log_path.as_posix()
                    if normalized not in state["log_files"]:
                        ui.notify("Senaryo cikti log dosyasi henuz uretilmedi.", color="warning")
                        return

                    log_select.set_value(normalized)
                    refresh_log_table()
                    ui.notify("Senaryo log dosyasi acildi.", color="positive")

                def run_scenario_preparation() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        ui.notify("Lutfen once bir senaryo secin.", color="warning")
                        return

                    try:
                        scenario_path = Path(selected_value)
                        scenario = load_scenario_definition(scenario_path)
                        scenario_copy = deepcopy(scenario)
                        input_path = Path(scenario_copy["input"])

                        data_output, log_output, manifest_output = build_output_paths(
                            scenario_copy["scenario_name"],
                            input_path,
                            SIMULATION_OUTPUT_DIR,
                        )
                        scenario_copy["output"] = str(data_output)
                        scenario_copy["log_output"] = str(log_output)

                        output_path, written_log_output, change_count = run_scenario_definition(scenario_copy)
                        manifest = build_manifest(
                            scenario_copy,
                            scenario_path,
                            input_path,
                            output_path,
                            written_log_output,
                            change_count,
                        )
                        write_manifest(manifest_output, manifest)

                        refresh_state_sources()
                        refresh_metrics()
                        csv_select.set_value(output_path.as_posix())
                        log_select.set_value(written_log_output.as_posix())
                        refresh_csv_table()
                        refresh_log_table()
                        refresh_impact_table()
                        ui.notify(
                            f"Senaryo hazirlik paketi olusturuldu: {scenario_copy['scenario_name']}",
                            color="positive",
                        )
                    except CsvUpdateError as error:
                        ui.notify(f"Hata: {error}", color="negative")

                def refresh_scenario_cards() -> None:
                    scenarios_grid.clear()
                    with scenarios_grid:
                        for scenario_file in state["scenario_files"]:
                            scenario_path = Path(scenario_file)
                            try:
                                scenario = read_json_file(scenario_path)
                            except Exception:
                                continue

                            if not isinstance(scenario, dict):
                                continue

                            with ui.card().classes("w-72"):
                                ui.label(scenario.get("scenario_name", scenario_path.stem)).classes(
                                    "text-base font-medium"
                                )
                                ui.label(scenario.get("description", "-")).classes("text-sm text-slate-600")
                                ui.label(
                                    f"Islem sayisi: {len(scenario.get('operations', []))}"
                                ).classes("text-xs text-slate-500")
                                ui.button(
                                    "Detayi Ac",
                                    on_click=lambda file_path=scenario_file: scenario_select.set_value(file_path),
                                ).props("flat color=primary")

                def refresh_recent_scenarios() -> None:
                    recent_scenarios.set_content(
                        build_recent_scenarios_markdown(read_manifest_entries())
                    )

                def refresh_scenario_detail() -> None:
                    selected_value = scenario_select.value
                    if not selected_value:
                        scenario_summary.set_text("Lutfen bir senaryo secin.")
                        scenario_detail.set_content("")
                        refresh_impact_table()
                        return

                    scenario_path = Path(selected_value)
                    if not scenario_path.exists():
                        scenario_summary.set_text(f"Senaryo bulunamadi: {selected_value}")
                        scenario_detail.set_content("")
                        refresh_impact_table()
                        return

                    scenario = read_json_file(scenario_path)
                    if not isinstance(scenario, dict):
                        scenario_summary.set_text("Senaryo verisi okunamadi.")
                        scenario_detail.set_content("")
                        return

                    scenario_summary.set_text(
                        f"Senaryo: {scenario.get('scenario_name', '-')} | "
                        f"Islem sayisi: {len(scenario.get('operations', []))}"
                    )
                    scenario_detail.set_content(format_scenario_markdown(scenario))
                    refresh_impact_table()

                def refresh_impact_table() -> None:
                    impact_table_container.clear()
                    impact_error.set_text("")

                    def reset_impact_summary(
                        hint_text: str = "Detay listeye girmeden once degisikligin genel etkisi burada gorunecek."
                    ) -> None:
                        summary_hint.set_text(hint_text)
                        changed_field_value.set_text("-")
                        total_impact_value.set_text("0")
                        direct_impact_value.set_text("0")
                        indirect_impact_value.set_text("0")
                        critical_impact_banner.set_text("Kritik etki bilgisi burada gosterilecek.")
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-slate-100 text-slate-700"
                        )

                    def reset_impact_charts(message: str) -> None:
                        impact_chart_info.set_text(message)
                        change_comparison_chart.options["xAxis"]["data"] = []
                        change_comparison_chart.options["series"][0]["data"] = []
                        change_comparison_chart.options["series"][1]["data"] = []
                        change_comparison_chart.options["series"][2]["data"] = []
                        change_comparison_chart.update()

                        impact_distribution_chart.options["xAxis"]["data"] = []
                        impact_distribution_chart.options["series"][0]["data"] = []
                        impact_distribution_chart.options["series"][1]["data"] = []
                        impact_distribution_chart.update()

                        relation_graph.options["series"][0]["data"] = []
                        relation_graph.options["series"][0]["links"] = []
                        relation_graph.options["series"][0]["categories"] = []
                        relation_graph.update()

                    selected_value = scenario_select.value
                    if not selected_value:
                        reset_impact_summary()
                        reset_impact_charts(
                            "Grafik altyapisi secili senaryonun etki verisiyle beslenecek."
                        )
                        impact_summary.set_text("Lutfen once bir senaryo secin.")
                        return

                    scenario_path = Path(selected_value)
                    if not scenario_path.exists():
                        reset_impact_summary("Degisim ozeti hazirlanamadi.")
                        reset_impact_charts("Grafik verisi hazirlanamadi.")
                        impact_summary.set_text("Senaryo dosyasi bulunamadi.")
                        return

                    try:
                        scenario = load_scenario_definition(scenario_path)
                        _, log_path, _ = scenario_output_targets(scenario_path)
                        impact_rows, message = build_impact_rows_for_scenario(
                            scenario_path,
                            scenario,
                            log_path,
                        )
                    except (CsvUpdateError, DependencyAnalysisError) as error:
                        reset_impact_summary("Degisim ozeti hesaplanamadi.")
                        reset_impact_charts("Grafik verisi hesaplanamadi.")
                        impact_summary.set_text("Etkilenen alanlar hesaplanamadi.")
                        impact_error.set_text(str(error))
                        return

                    filtered_impact_rows = filter_impact_rows(
                        impact_rows,
                        query=impact_search_input.value or "",
                        impact_type=impact_type_filter.value or "Tum Etkiler",
                        sort_mode=impact_sort_select.value or "Varsayilan",
                    )

                    impact_totals = build_impact_summary(filtered_impact_rows)
                    summary_hint.set_text(
                        f"Senaryo: {scenario.get('scenario_name', scenario_path.stem)}"
                    )
                    changed_field_value.set_text(impact_totals["changed_fields"])
                    total_impact_value.set_text(str(impact_totals["total_rows"]))
                    direct_impact_value.set_text(str(impact_totals["direct_rows"]))
                    indirect_impact_value.set_text(str(impact_totals["indirect_rows"]))

                    critical_impact_banner.set_text(impact_totals["critical_message"])
                    if impact_totals["critical_tone"] == "critical":
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-red-100 text-red-800"
                        )
                    elif impact_totals["critical_tone"] == "warning":
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-amber-100 text-amber-800"
                        )
                    else:
                        critical_impact_banner.classes(
                            replace="w-full rounded-md px-3 py-2 text-sm bg-slate-100 text-slate-700"
                        )

                    impact_summary.set_text(
                        f"{message} | Filtrelenen kayit: {len(filtered_impact_rows)}"
                    )
                    if not filtered_impact_rows:
                        reset_impact_charts("Secili filtrelere uygun etki kaydi bulunamadi.")
                        with impact_table_container:
                            ui.label("Secili filtrelere uygun etkilenen alan bulunamadi.").classes("text-sm text-slate-500")
                        return

                    chart_model = build_impact_chart_model(filtered_impact_rows)
                    impact_chart_info.set_text(
                        "Bar grafikler once/sonra ve veri seti bazli etkiyi; iliski grafigi ise bagimlilik yayilimini gosterir."
                    )
                    change_comparison_chart.options["xAxis"]["data"] = chart_model["comparison"]["labels"]
                    change_comparison_chart.options["series"][0]["data"] = chart_model["comparison"]["old_values"]
                    change_comparison_chart.options["series"][1]["data"] = chart_model["comparison"]["new_values"]
                    change_comparison_chart.options["series"][2]["data"] = chart_model["comparison"]["highlight_values"]
                    change_comparison_chart.update()

                    impact_distribution_chart.options["xAxis"]["data"] = chart_model["distribution"]["labels"]
                    impact_distribution_chart.options["series"][0]["data"] = chart_model["distribution"]["direct_values"]
                    impact_distribution_chart.options["series"][1]["data"] = chart_model["distribution"]["indirect_values"]
                    impact_distribution_chart.update()

                    relation_graph.options["series"][0]["data"] = chart_model["relations"]["nodes"]
                    relation_graph.options["series"][0]["links"] = chart_model["relations"]["links"]
                    relation_graph.options["series"][0]["categories"] = chart_model["relations"]["categories"]
                    relation_graph.update()

                    with impact_table_container:
                        impact_table = ui.table(
                            columns=[
                                {"name": "degisen_alan", "label": "Alan", "field": "degisen_alan", "sortable": True},
                                {"name": "eski_deger", "label": "Eski Deger", "field": "eski_deger", "sortable": True},
                                {"name": "yeni_deger", "label": "Yeni Deger", "field": "yeni_deger", "sortable": True},
                                {"name": "degisim_miktari", "label": "Degisim", "field": "degisim_miktari", "sortable": True},
                                {"name": "yon", "label": "Yon", "field": "yon", "sortable": True},
                                {"name": "etki_tipi", "label": "Etki", "field": "etki_tipi", "sortable": True},
                                {"name": "etkilenen_veri", "label": "Etkilenen Veri", "field": "etkilenen_veri", "sortable": True},
                                {"name": "etkilenen_satir", "label": "Satir", "field": "etkilenen_satir", "sortable": True},
                                {"name": "kaynak", "label": "Kaynak", "field": "kaynak", "sortable": True},
                            ],
                            rows=filtered_impact_rows,
                            row_key="id",
                            pagination={"rowsPerPage": 10},
                        ).classes("w-full")
                        impact_table.add_slot(
                            "body-cell-etki_tipi",
                            r'''
                            <q-td :props="props">
                              <q-badge
                                :color="props.value === 'Dogrudan' ? 'positive' : (props.value === 'Dolayli' ? 'warning' : 'grey-6')"
                                :label="props.value"
                              />
                            </q-td>
                            ''',
                        )
                        impact_table.add_slot(
                            "body-cell-yon",
                            r'''
                            <q-td :props="props">
                              <q-badge
                                :color="props.value === 'Artis' ? 'positive' : (props.value === 'Azalis' ? 'negative' : 'grey-6')"
                                :label="props.value"
                              />
                            </q-td>
                            ''',
                        )
                        impact_table.on(
                            "rowClick",
                            lambda event: open_row_detail(
                                "Etki Kaydi Detayi",
                                event.args["row"],
                                [
                                    "degisen_alan",
                                    "eski_deger",
                                    "yeni_deger",
                                    "degisim_miktari",
                                    "yon",
                                    "etki_tipi",
                                    "etkilenen_veri",
                                    "etkilenen_satir",
                                    "kaynak",
                                    "neden",
                                ],
                            ),
                        )

                def clear_impact_filters() -> None:
                    impact_search_input.set_value("")
                    impact_type_filter.set_value("Tum Etkiler")
                    impact_sort_select.set_value("Varsayilan")
                    refresh_impact_table()

                open_output_button.on("click", lambda _: focus_output_file())
                open_log_button.on("click", lambda _: focus_log_file())
                run_button.on("click", lambda _: run_scenario_preparation())
                scenario_select.on_value_change(lambda _: refresh_scenario_detail())
                impact_search_input.on_value_change(lambda _: refresh_impact_table())
                impact_type_filter.on_value_change(lambda _: refresh_impact_table())
                impact_sort_select.on_value_change(lambda _: refresh_impact_table())
                clear_impact_filters_button.on("click", lambda _: clear_impact_filters())
                refresh_scenario_cards()
                refresh_scenario_detail()
                refresh_recent_scenarios()

            with ui.tab_panel(analytics_tab):
                with ui.card().classes("w-full"):
                    ui.label("Senaryo Analizi").classes("text-base font-medium")
                    analytics_info = ui.label("").classes("text-sm text-slate-600")
                    changes_chart = ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["Degisen Alan", "Islem Sayisi"]},
                            "xAxis": {"type": "category", "data": []},
                            "yAxis": {"type": "value"},
                            "series": [
                                {"name": "Degisen Alan", "type": "bar", "data": []},
                                {"name": "Islem Sayisi", "type": "line", "data": []},
                            ],
                        }
                    ).classes("w-full h-80")
                    flow_chart = ui.echart(
                        {
                            "tooltip": {"trigger": "axis"},
                            "xAxis": {"type": "category", "data": []},
                            "yAxis": {"type": "value"},
                            "series": [
                                {
                                    "name": "Degisen Alan",
                                    "type": "line",
                                    "smooth": True,
                                    "areaStyle": {},
                                    "data": [],
                                }
                            ],
                        }
                    ).classes("w-full h-72")
                    with ui.row().classes("w-full gap-4"):
                        comparison_left = ui.select(options=[], label="Sol senaryo").classes("w-full")
                        comparison_right = ui.select(options=[], label="Sag senaryo").classes("w-full")
                    comparison_markdown = ui.markdown("").classes("w-full text-sm")

                def refresh_comparison() -> None:
                    manifests_by_name = {
                        item.get("scenario_name"): item for item in read_manifest_entries()
                    }
                    left = manifests_by_name.get(comparison_left.value)
                    right = manifests_by_name.get(comparison_right.value)
                    if not left or not right:
                        comparison_markdown.set_content("Karsilastirma icin iki senaryo secin.")
                        return

                    difference = int(left.get("changed_field_count", 0)) - int(
                        right.get("changed_field_count", 0)
                    )
                    comparison_markdown.set_content(
                        "\n".join(
                            [
                                f"**Sol:** {left.get('scenario_name', '-')}",
                                f"- Degisen alan: {left.get('changed_field_count', 0)}",
                                f"- Islem sayisi: {left.get('operation_count', 0)}",
                                "",
                                f"**Sag:** {right.get('scenario_name', '-')}",
                                f"- Degisen alan: {right.get('changed_field_count', 0)}",
                                f"- Islem sayisi: {right.get('operation_count', 0)}",
                                "",
                                f"**Fark:** {difference}",
                            ]
                        )
                    )

                def refresh_metrics() -> None:
                    manifests = read_manifest_entries()
                    total_scenarios_value.set_text(str(len(manifests)))
                    total_changes_value.set_text(
                        str(sum(int(item.get("changed_field_count", 0)) for item in manifests))
                    )
                    last_scenario_value.set_text(manifests[-1].get("scenario_name", "-") if manifests else "-")

                    analytics_info.set_text(f"Karsilastirilan senaryo sayisi: {len(manifests)}")

                    scenario_names = [item.get("scenario_name", "-") for item in manifests]
                    change_values = [int(item.get("changed_field_count", 0)) for item in manifests]
                    operation_values = [int(item.get("operation_count", 0)) for item in manifests]

                    changes_chart.options["xAxis"]["data"] = scenario_names
                    changes_chart.options["series"][0]["data"] = change_values
                    changes_chart.options["series"][1]["data"] = operation_values
                    changes_chart.update()

                    flow_chart.options["xAxis"]["data"] = scenario_names
                    flow_chart.options["series"][0]["data"] = change_values
                    flow_chart.update()

                    comparison_left.options = scenario_names
                    comparison_left.update()
                    comparison_right.options = scenario_names
                    comparison_right.update()
                    if scenario_names and comparison_left.value not in scenario_names:
                        comparison_left.set_value(scenario_names[0])
                    if len(scenario_names) > 1 and comparison_right.value not in scenario_names:
                        comparison_right.set_value(scenario_names[1])
                    elif scenario_names and comparison_right.value not in scenario_names:
                        comparison_right.set_value(scenario_names[0])

                    refresh_recent_scenarios()
                    refresh_comparison()

                comparison_left.on_value_change(lambda _: refresh_comparison())
                comparison_right.on_value_change(lambda _: refresh_comparison())
                refresh_metrics()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="CSV Izleme Paneli")
