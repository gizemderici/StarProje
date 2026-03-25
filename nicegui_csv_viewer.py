import csv
from copy import deepcopy
import json
from pathlib import Path

from nicegui import ui

from apply_scenario_definition import load_scenario_definition, run_scenario_definition
from build_simulation_output import build_manifest, build_output_paths, write_manifest
from update_csv_fields import CsvUpdateError


CSV_SEARCH_DIRS = [Path("csv_output"), Path("simulation_outputs")]
SCENARIO_DIR = Path("scenario_definitions")
MAX_ROWS = 200


def collect_csv_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if not directory.exists():
            continue
        files.extend(sorted(directory.rglob("*.csv")))
    return files


def collect_log_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if not directory.exists():
            continue
        files.extend(sorted(directory.rglob("*changes.json")))
        files.extend(sorted(directory.rglob("*changes.csv")))
    return files


def collect_manifest_files() -> list[Path]:
    simulation_dir = Path("simulation_outputs")
    if not simulation_dir.exists():
        return []
    return sorted(simulation_dir.rglob("*__manifest.json"))


def read_csv_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            return [], []
        rows = list(reader)
        return rows, reader.fieldnames


def read_log_rows(log_path: Path) -> tuple[list[dict], list[str]]:
    if log_path.suffix.lower() == ".json":
        with log_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            return [], []
        rows = [
            {key: value for key, value in item.items()}
            for item in data
            if isinstance(item, dict)
        ]
        fieldnames = []
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        return rows, fieldnames

    return read_csv_rows(log_path)


def read_manifest_rows() -> list[dict]:
    manifests = []
    for manifest_path in collect_manifest_files():
        with manifest_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            manifests.append(data)
    return manifests


def collect_scenario_files() -> list[Path]:
    if not SCENARIO_DIR.exists():
        return []
    return sorted(SCENARIO_DIR.rglob("*.json"))


def read_scenario_preview(scenario_path: Path) -> dict:
    with scenario_path.open("r", encoding="utf-8") as file:
        return json.load(file)


csv_files = collect_csv_files()
file_options = [path.as_posix() for path in csv_files]
scenario_files = collect_scenario_files()
scenario_options = [path.as_posix() for path in scenario_files]
log_files = collect_log_files()
log_options = [path.as_posix() for path in log_files]
manifest_rows = read_manifest_rows()


def get_initial_value(options: list[str]) -> str | None:
    for option in options:
        if option.endswith("materials.csv"):
            return option
    return options[0] if options else None


initial_value = get_initial_value(file_options)


@ui.page("/")
def main_page() -> None:
    ui.page_title("CSV Izleme Paneli")

    with ui.header().classes("items-center justify-between bg-slate-800 text-white"):
        ui.label("CSV Izleme Paneli").classes("text-lg font-medium")
        ui.label("NiceGUI ilk surum").classes("text-sm opacity-80")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-4"):
        ui.label("CSV verilerini ve senaryo ciktilarini hizli incelemek icin baslangic arayuzu.").classes(
            "text-base text-slate-700"
        )

        with ui.row().classes("w-full gap-4"):
            total_scenarios_card = ui.card().classes("w-full")
            with total_scenarios_card:
                ui.label("Toplam Senaryo Ciktisi").classes("text-sm text-slate-500")
                total_scenarios_value = ui.label("0").classes("text-3xl font-bold")

            total_changes_card = ui.card().classes("w-full")
            with total_changes_card:
                ui.label("Toplam Degisen Alan").classes("text-sm text-slate-500")
                total_changes_value = ui.label("0").classes("text-3xl font-bold")

            latest_scenario_card = ui.card().classes("w-full")
            with latest_scenario_card:
                ui.label("Son Senaryo").classes("text-sm text-slate-500")
                latest_scenario_value = ui.label("-").classes("text-lg font-medium")

        with ui.card().classes("w-full"):
            ui.label("Senaryo Karsilastirma").classes("text-base font-medium")
            comparison_info = ui.label("").classes("text-sm text-slate-600")
            comparison_chart = ui.echart(
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

        def refresh_metrics() -> None:
            current_manifests = read_manifest_rows()
            total_scenarios_value.set_text(str(len(current_manifests)))
            total_changes_value.set_text(
                str(sum(int(item.get("changed_field_count", 0)) for item in current_manifests))
            )
            latest_scenario_value.set_text(
                current_manifests[-1]["scenario_name"] if current_manifests else "-"
            )

            comparison_info.set_text(
                f"Karsilastirilan senaryo sayisi: {len(current_manifests)}"
            )
            comparison_chart.options["xAxis"]["data"] = [
                item.get("scenario_name", "-") for item in current_manifests
            ]
            comparison_chart.options["series"][0]["data"] = [
                int(item.get("changed_field_count", 0)) for item in current_manifests
            ]
            comparison_chart.options["series"][1]["data"] = [
                int(item.get("operation_count", 0)) for item in current_manifests
            ]
            comparison_chart.update()

        refresh_metrics()

        with ui.card().classes("w-full"):
            ui.label("Veri Dosyasi Sec").classes("text-base font-medium")
            file_select = ui.select(
                options=file_options,
                value=initial_value,
                label="CSV dosyasi",
            ).classes("w-full")
            search_input = ui.input(
                label="Tabloda ara",
                placeholder="Bir deger veya kolon icigi ara",
            ).classes("w-full")
            info_label = ui.label("").classes("text-sm text-slate-600")

        table_container = ui.column().classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Degisiklik Gecmisi").classes("text-base font-medium")
            log_select = ui.select(
                options=log_options,
                value=log_options[0] if log_options else None,
                label="Log dosyasi",
            ).classes("w-full")
            log_info = ui.label("").classes("text-sm text-slate-600")
            log_container = ui.column().classes("w-full")

            def refresh_log_table() -> None:
                log_container.clear()
                selected_log = log_select.value
                if not selected_log:
                    log_info.set_text("Goruntulenecek bir log dosyasi secin.")
                    return

                log_path = Path(selected_log)
                if not log_path.exists():
                    log_info.set_text(f"Log dosyasi bulunamadi: {selected_log}")
                    return

                rows, fieldnames = read_log_rows(log_path)
                log_info.set_text(
                    f"Log dosyasi: {log_path.as_posix()} | Toplam kayit: {len(rows)} | Gosterilen: {min(len(rows), MAX_ROWS)}"
                )

                with log_container:
                    if not fieldnames:
                        ui.label("Log icinde gosterilecek kayit bulunamadi.").classes("text-red-600")
                        return

                    ui.table(
                        columns=[
                            {"name": name, "label": name, "field": name, "sortable": True}
                            for name in fieldnames
                        ],
                        rows=rows[:MAX_ROWS],
                        row_key=fieldnames[0],
                        pagination={"rowsPerPage": 10},
                    ).classes("w-full")

            log_select.on_value_change(lambda _: refresh_log_table())
            ui.button("Log Tablosunu Yenile", on_click=refresh_log_table).props("outline")
            refresh_log_table()

        with ui.card().classes("w-full"):
            ui.label("Simulasyon Senaryolari").classes("text-base font-medium")
            scenario_select = ui.select(
                options=scenario_options,
                value=scenario_options[0] if scenario_options else None,
                label="Senaryo dosyasi",
            ).classes("w-full")
            scenario_info = ui.label("").classes("text-sm text-slate-600")
            scenario_detail = ui.markdown("").classes("w-full text-sm")

            def refresh_scenario_detail() -> None:
                selected_scenario = scenario_select.value
                if not selected_scenario:
                    scenario_info.set_text("Goruntulenecek bir senaryo dosyasi secin.")
                    scenario_detail.set_content("")
                    return

                scenario_path = Path(selected_scenario)
                if not scenario_path.exists():
                    scenario_info.set_text(f"Senaryo dosyasi bulunamadi: {selected_scenario}")
                    scenario_detail.set_content("")
                    return

                try:
                    scenario = read_scenario_preview(scenario_path)
                except Exception as error:
                    scenario_info.set_text(f"Senaryo okunamadi: {error}")
                    scenario_detail.set_content("")
                    return

                operations = scenario.get("operations", [])
                scenario_info.set_text(
                    f"Senaryo: {scenario.get('scenario_name', '-') } | Islem sayisi: {len(operations)}"
                )

                operation_lines = []
                for operation in operations:
                    match = operation.get("match", {})
                    updates = operation.get("updates", {})
                    update_text = ", ".join(f"{key}={value}" for key, value in updates.items())
                    operation_lines.append(
                        f"- **{operation.get('name', 'islem')}**: "
                        f"`{match.get('column', '-')}` = `{match.get('value', '-')}` -> {update_text}"
                    )

                scenario_detail.set_content(
                    "\n".join(
                        [
                            f"**Aciklama:** {scenario.get('description', '-')}",
                            f"**Girdi:** `{scenario.get('input', '-')}`",
                            f"**Varsayilan cikti:** `{scenario.get('output', '-')}`",
                            "",
                            "**Degisiklikler:**",
                            *operation_lines,
                        ]
                    )
                )

            def run_scenario_preparation() -> None:
                selected_scenario = scenario_select.value
                if not selected_scenario:
                    ui.notify("Lutfen once bir senaryo secin.", color="warning")
                    return

                try:
                    scenario_path = Path(selected_scenario)
                    scenario = load_scenario_definition(scenario_path)
                    scenario_copy = deepcopy(scenario)
                    input_path = Path(scenario_copy["input"])
                    data_output, log_output, manifest_output = build_output_paths(
                        scenario_copy["scenario_name"],
                        input_path,
                        Path("simulation_outputs"),
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
                    ui.notify(
                        f"Senaryo hazirlik cikti paketi olusturuldu: {scenario_copy['scenario_name']}",
                        color="positive",
                    )
                    refresh_table()
                    updated_logs = collect_log_files()
                    log_select.options = [path.as_posix() for path in updated_logs]
                    if str(written_log_output).replace("\\", "/") in log_select.options:
                        log_select.value = str(written_log_output).replace("\\", "/")
                    refresh_log_table()
                    refresh_scenario_detail()
                    refresh_metrics()
                except CsvUpdateError as error:
                    ui.notify(f"Hata: {error}", color="negative")

            scenario_select.on_value_change(lambda _: refresh_scenario_detail())
            ui.button("Hazirlik Akisini Baslat", on_click=run_scenario_preparation).props("color=primary")
            refresh_scenario_detail()

        def refresh_table() -> None:
            table_container.clear()
            selected_value = file_select.value
            if not selected_value:
                info_label.set_text("Goruntulenecek bir CSV dosyasi secin.")
                return

            csv_path = Path(selected_value)
            if not csv_path.exists():
                info_label.set_text(f"Dosya bulunamadi: {selected_value}")
                return

            rows, fieldnames = read_csv_rows(csv_path)
            search_query = (search_input.value or "").strip().lower()
            filtered_rows = rows
            if search_query:
                filtered_rows = [
                    row
                    for row in rows
                    if any(search_query in str(value).lower() for value in row.values())
                ]

            info_label.set_text(
                f"Dosya: {csv_path.as_posix()} | Toplam satir: {len(rows)} | "
                f"Filtrelenen: {len(filtered_rows)} | Gosterilen: {min(len(filtered_rows), MAX_ROWS)}"
            )

            with table_container:
                if not fieldnames:
                    ui.label("CSV baslik satiri bulunamadi.").classes("text-red-600")
                    return

                ui.table(
                    columns=[{"name": name, "label": name, "field": name, "sortable": True} for name in fieldnames],
                    rows=filtered_rows[:MAX_ROWS],
                    row_key=fieldnames[0],
                    pagination={"rowsPerPage": 20},
                ).classes("w-full")

                if len(filtered_rows) > MAX_ROWS:
                    ui.label(
                        f"Performans icin ilk {MAX_ROWS} satir gosteriliyor."
                    ).classes("text-sm text-amber-700")

        file_select.on_value_change(lambda _: refresh_table())
        search_input.on_value_change(lambda _: refresh_table())
        ui.button("Tabloyu Yenile", on_click=refresh_table).props("outline")

        refresh_table()


ui.run(title="CSV Izleme Paneli")
