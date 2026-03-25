import csv
from pathlib import Path

from nicegui import ui


CSV_SEARCH_DIRS = [Path("csv_output"), Path("simulation_outputs")]
MAX_ROWS = 200


def collect_csv_files() -> list[Path]:
    files = []
    for directory in CSV_SEARCH_DIRS:
        if not directory.exists():
            continue
        files.extend(sorted(directory.rglob("*.csv")))
    return files


def read_csv_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            return [], []
        rows = list(reader)
        return rows, reader.fieldnames


csv_files = collect_csv_files()
file_options = [path.as_posix() for path in csv_files]


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
