"""Faz 4-7 sonuclarini gosteren arayuz panelleri.

Veri okuma ui_pages/study_data.py icindedir; bu modul yalnizca cizim yapar.
Her panel veri hazir degilken de calisir ve durumu bildirir.
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from ui_pages import study_data

# app.py'deki yardimcilarla ayni gorunumu korumak icin ayni sinif adlari.
CARD = "studio-card"
TABLE = "w-full studio-table"


def tr(value: float, digits: int = 2) -> str:
    """Turkce sayi bicimi: binlik ayraci nokta, ondalik ayraci virgul.

    Python'un varsayilan bicimi ("1,920.5") arayuzun geri kalaniyla
    tutarsizdi; bu binada 1.920 ile 1,920 farkli sayilar gibi okunuyordu.
    """
    text = f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")


def _heading(eyebrow: str, title: str, description: str = "") -> None:
    with ui.column().classes("gap-1"):
        ui.label(eyebrow).classes("eyebrow")
        ui.label(title).classes("section-title")
        if description:
            ui.label(description).classes("section-copy")


def _metric(icon: str, label: str, value: str, note: str, tone: str = "teal") -> None:
    with ui.card().classes("metric-card min-w-0"):
        with ui.row().classes("w-full items-start justify-between no-wrap"):
            with ui.column().classes("gap-1 min-w-0"):
                ui.label(label).classes("metric-label")
                ui.label(value).classes("metric-value")
                ui.label(note).classes("metric-note")
            ui.icon(icon).classes(f"metric-icon tone-{tone}")


def _empty(message: str, hint: str = "") -> None:
    """Veri henuz uretilmemisken gosterilecek durum.

    Parametrik calisma saatler surdugu icin bu bir hata degil, normal bir
    asamadir; panel bunu boyle anlatir.
    """
    with ui.card().classes(CARD):
        with ui.row().classes("items-center gap-3"):
            ui.icon("hourglass_empty").classes("metric-icon tone-slate")
            with ui.column().classes("gap-1"):
                ui.label(message).classes("card-title")
                if hint:
                    ui.label(hint).classes("card-subtitle")


def phase_strip() -> None:
    """Sekiz fazin durumunu tek seritte gosterir."""
    phases = study_data.phase_overview()
    with ui.row().classes("w-full gap-2 no-wrap overflow-x-auto"):
        for item in phases:
            tone = "teal" if item["ready"] else "slate"
            icon = "check_circle" if item["ready"] else "schedule"
            with ui.card().classes("metric-card min-w-0 flex-1"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.icon(icon).classes(f"metric-icon tone-{tone}")
                    with ui.column().classes("gap-0 min-w-0"):
                        ui.label(item["phase"]).classes("metric-label")
                        ui.label(item["title"]).classes("text-sm font-bold")
                        ui.label(item["detail"]).classes("metric-note")


# --------------------------------------------------------------------------
# Faz 3 + 4: parametrik calisma ve vekil model
# --------------------------------------------------------------------------


def surrogate_panel() -> None:
    status = study_data.load_study_status()
    report = study_data.load_surrogate()

    _heading(
        "FAZ 3 ve 4",
        "Parametrik calisma ve vekil model",
        "Gercek EnergyPlus kosularindan egitilen hizli tahmin modeli.",
    )

    if not status.ready:
        _empty(
            "Parametrik calisma henuz sonuc uretmedi.",
            "run_parametric_study.py calistirilmalidir.",
        )
        return

    with ui.grid(columns=4).classes("w-full gap-3"):
        _metric(
            "dataset",
            "KOSU SAYISI",
            f"{status.completed}",
            f"{status.unique_results} benzersiz sonuc",
            "teal" if status.all_unique else "coral",
        )
        _metric(
            "bolt",
            "ENERJI ARALIGI",
            f"{tr(status.site_energy_min_gj, 0)} – {tr(status.site_energy_max_gj, 0)}",
            "GJ/yil (taban 1.920)",
        )
        _metric(
            "casino",
            "ORNEKLEYICI",
            status.sampler,
            f"tohum {status.seed}",
        )
        if status.with_severe_errors:
            _metric(
                "warning",
                "SEVERE UYARISI",
                f"{len(status.with_severe_errors)}",
                "isinma yakinsamasi",
                "gold",
            )
        else:
            _metric("verified", "SEVERE HATA", "0", "tum kosular temiz")

    if not report.ready:
        _empty("Vekil model henuz egitilmedi.", "run_surrogate.py calistirilmalidir.")
        return

    with ui.card().classes(CARD):
        ui.label("Bagimsiz test kumesi").classes("card-title")
        ui.label(
            "Kapi yalnizca amac fonksiyonlarini besleyen hedeflere bakar; "
            "digerleri raporlanir ama kapiyi belirlemez."
        ).classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "target", "label": "Hedef", "field": "target", "align": "left"},
                {"name": "model", "label": "Model", "field": "model", "align": "left"},
                {"name": "r2", "label": "R²", "field": "r2", "align": "right"},
                {"name": "metric", "label": "Olcut", "field": "metric", "align": "left"},
                {"name": "error", "label": "Hata", "field": "error", "align": "right"},
                {"name": "gate", "label": "Kapi", "field": "gate", "align": "center"},
            ],
            rows=report.test_rows(),
            row_key="target",
        ).classes(TABLE)

    with ui.grid(columns=3).classes("w-full gap-3"):
        _metric(
            "speed",
            "HIZLANMA",
            f"{tr(report.speedup_ratio, 0)}x",
            f"{tr(report.seconds_per_call * 1e6, 1)} mikrosaniye / degerlendirme",
        )
        _metric(
            "school",
            "EGITIM KUMESI",
            f"{report.rows}",
            f"{report.features} ozellik",
        )
        _metric(
            "flag",
            "FAZ 4 KAPISI",
            "GECILDI" if report.gate_passed else "GECILMEDI",
            ", ".join(report.gate_targets),
            "teal" if report.gate_passed else "coral",
        )

    if report.sensitivity:
        with ui.card().classes(CARD):
            ui.label("Sobol duyarlilik analizi").classes("card-title")
            ui.label(
                "S1 degiskenin tek basina, ST etkilesimler dahil toplam katkisidir. "
                "Saha enerjisi varyansi uzerinden hesaplanir."
            ).classes("card-subtitle")
            ui.echart(_sensitivity_chart(report.sensitivity)).classes("w-full h-80")


def _sensitivity_chart(indices: list[dict]) -> dict:
    ordered = sorted(indices, key=lambda item: item["total"])
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": ["S1 (tek basina)", "ST (etkilesim dahil)"]},
        "grid": {"left": 180, "right": 24, "top": 40, "bottom": 30},
        "xAxis": {"type": "value", "name": "varyans payi"},
        "yAxis": {
            "type": "category",
            "data": [item["label"] for item in ordered],
            "axisLabel": {"fontSize": 11},
        },
        "series": [
            {
                "name": "S1 (tek basina)",
                "type": "bar",
                "data": [round(item["first_order"], 4) for item in ordered],
            },
            {
                "name": "ST (etkilesim dahil)",
                "type": "bar",
                "data": [round(item["total"], 4) for item in ordered],
            },
        ],
    }


# --------------------------------------------------------------------------
# Faz 6: Pareto cephesi
# --------------------------------------------------------------------------


def pareto_panel() -> None:
    view = study_data.load_pareto()
    _heading(
        "FAZ 6",
        "Cok amacli optimizasyon",
        "EnPI, yatirim maliyeti ve konfor ihlali es zamanli en aza indirilir.",
    )

    if not view.ready:
        _empty("Pareto cephesi henuz uretilmedi.", "run_optimization.py calistirilmalidir.")
        return

    if not view.usable_in_thesis:
        with ui.card().classes(CARD):
            with ui.row().classes("items-center gap-3"):
                ui.icon("science").classes("metric-icon tone-gold")
                with ui.column().classes("gap-1"):
                    ui.label(
                        f"Bu cephe '{view.evaluator}' degerlendiricisiyle uretildi."
                    ).classes("card-title")
                    ui.label(
                        "Yalnizca altyapi sinamasidir; sonuclari tezde kullanilamaz."
                    ).classes("card-subtitle")

    with ui.grid(columns=3).classes("w-full gap-3"):
        _metric("hub", "COZUM SAYISI", f"{view.solution_count}", "Pareto cephesi")
        _metric(
            "trending_up",
            "HIPERVOLUM",
            tr(view.hypervolume_end, 4),
            f"baslangic {tr(view.hypervolume_start, 4)}",
        )
        _metric("verified_user", "KAYNAK", view.evaluator, "degerlendirici")

    with ui.card().classes(CARD):
        ui.label("Cephe: EnPI - yatirim maliyeti").classes("card-title")
        ui.label(
            "Sol alt kose ideal bolgedir; hicbir cozum digerine her uc amacta "
            "birden ustun degildir."
        ).classes("card-subtitle")
        ui.echart(_front_chart(view)).classes("w-full h-96")

    if view.convergence:
        with ui.card().classes(CARD):
            ui.label("Yakinsama").classes("card-title")
            ui.echart(_convergence_chart(view)).classes("w-full h-64")


def _front_chart(view: study_data.ParetoView) -> dict:
    enpi = view.objective_values(0)
    cost = view.objective_values(1)
    comfort = view.objective_values(2)
    points = [
        [round(e, 2), round(c, 0), round(k, 0)]
        for e, c, k in zip(enpi, cost, comfort)
    ]
    return {
        "tooltip": {},
        "grid": {"left": 70, "right": 30, "top": 30, "bottom": 50},
        "xAxis": {"type": "value", "name": "EnPI (kWh/m²·yıl)", "nameLocation": "middle", "nameGap": 30},
        "yAxis": {"type": "value", "name": "Yatirim (TRY)", "nameLocation": "middle", "nameGap": 55},
        "series": [
            {
                "type": "scatter",
                "data": points,
                "symbolSize": 9,
                "encode": {"x": 0, "y": 1, "tooltip": [0, 1, 2]},
            }
        ],
    }


def _convergence_chart(view: study_data.ParetoView) -> dict:
    return {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 60, "right": 30, "top": 30, "bottom": 40},
        "xAxis": {
            "type": "category",
            "name": "nesil",
            "data": [item["generation"] for item in view.convergence],
        },
        "yAxis": {"type": "value", "name": "hipervolum"},
        "series": [
            {
                "type": "line",
                "smooth": True,
                "showSymbol": False,
                "data": [item["hypervolume"] for item in view.convergence],
            }
        ],
    }


# --------------------------------------------------------------------------
# Faz 5: ISO 50001
# --------------------------------------------------------------------------


def iso50001_panel() -> None:
    view = study_data.load_iso50001()
    _heading(
        "FAZ 5",
        "ISO 50001 kapsami",
        "Onemli enerji kullanimi, enerji taban cizgisi ve performans gostergeleri.",
    )

    if not view.ready:
        _empty("ISO 50001 raporu uretilmedi.", "build_iso50001_report.py calistirilmalidir.")
        return

    with ui.card().classes(CARD):
        with ui.row().classes("items-center gap-3"):
            ui.icon("info").classes("metric-icon tone-gold")
            with ui.column().classes("gap-1"):
                ui.label("Enerji taban cizgisi olculmemistir").classes("card-title")
                ui.label(view.notice).classes("card-subtitle")

    with ui.grid(columns=4).classes("w-full gap-3"):
        _metric("speed", "EnPI", tr(view.eui_kwh_m2, 1), "kWh/m²·yıl")
        _metric("bolt", "TABAN CIZGISI", tr(view.baseline_gj, 0), "GJ/yil")
        _metric("ac_unit", "HDD 18", tr(view.hdd, 0), "isitma derece-gun")
        _metric("wb_sunny", "CDD 22", tr(view.cdd, 0), "sogutma derece-gun")

    with ui.card().classes(CARD):
        ui.label("Onemli enerji kullanimi (SEU)").classes("card-title")
        ui.label(
            f"Pareto olcutu: kumulatif pay %80'e ulasana kadar. "
            f"Kapsam: {', '.join(view.significant_uses)}"
        ).classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "label", "label": "Son kullanim", "field": "label", "align": "left"},
                {"name": "energy_gj", "label": "GJ/yil", "field": "energy_gj", "align": "right"},
                {"name": "share_percent", "label": "Pay %", "field": "share_percent", "align": "right"},
                {"name": "cumulative_percent", "label": "Kumulatif %", "field": "cumulative_percent", "align": "right"},
                {"name": "seu", "label": "SEU", "field": "seu", "align": "center"},
            ],
            rows=[
                {
                    "label": item["label"],
                    "energy_gj": tr(float(item["energy_gj"])),
                    "share_percent": tr(float(item["share_percent"]), 1),
                    "cumulative_percent": tr(float(item["cumulative_percent"]), 1),
                    "seu": "EVET" if item["significant"] else "",
                }
                for item in view.uses
            ],
            row_key="label",
        ).classes(TABLE)


# --------------------------------------------------------------------------
# Faz 7: dogrulama
# --------------------------------------------------------------------------


def validation_panel() -> None:
    view = study_data.load_validation()
    _heading(
        "FAZ 7",
        "Simulasyon destekli sayisal dogrulama",
        "Pareto cephesinden secilen noktalar gercek EnergyPlus ile kosulur.",
    )

    if not view.ready:
        _empty("Dogrulama kosusu yapilmadi.", "run_validation.py calistirilmalidir.")
        return

    with ui.grid(columns=3).classes("w-full gap-3"):
        _metric(
            "rule",
            "EN BUYUK SAPMA",
            f"%{tr(view.max_deviation_percent)}",
            "tolerans %5,0",
            "teal" if view.within_tolerance else "coral",
        )
        _metric("straighten", "NOKTA SAYISI", f"{len(view.points)}", "gercek EnergyPlus kosusu")
        _metric(
            "flag",
            "FAZ 7 KAPISI",
            "GECILDI" if view.within_tolerance else "GECILMEDI",
            "her noktada sapma < %5",
            "teal" if view.within_tolerance else "coral",
        )

    with ui.card().classes(CARD):
        ui.label("Vekil model tahmini ile gercek kosu karsilastirmasi").classes("card-title")
        ui.label(
            "Pozitif sapma vekil modelin fazla tahmin ettigini gosterir. "
            "Degerler EnPI cinsindendir (kWh/m²·yıl)."
        ).classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "case_id", "label": "Senaryo", "field": "case_id", "align": "left"},
                {"name": "predicted_enpi_kwh_m2", "label": "Vekil", "field": "predicted_enpi_kwh_m2", "align": "right"},
                {"name": "actual_enpi_kwh_m2", "label": "Gercek", "field": "actual_enpi_kwh_m2", "align": "right"},
                {"name": "deviation_percent", "label": "Sapma %", "field": "deviation_percent", "align": "right"},
                {"name": "reason", "label": "Gerekce", "field": "reason", "align": "left"},
            ],
            rows=[
                {
                    "case_id": item["case_id"],
                    "predicted_enpi_kwh_m2": tr(float(item["predicted_enpi_kwh_m2"])),
                    "actual_enpi_kwh_m2": tr(float(item["actual_enpi_kwh_m2"])),
                    "deviation_percent": tr(float(item["deviation_percent"])),
                    "reason": item["reason"],
                }
                for item in sorted(
                    view.points,
                    key=lambda entry: abs(float(entry.get("deviation_percent", 0))),
                    reverse=True,
                )
            ],
            row_key="case_id",
        ).classes(TABLE)


def render_all(sections: tuple[str, ...] = ("surrogate", "pareto", "iso", "validation")) -> None:
    """Panelleri sirayla cizer; test ve tek sayfa gorunumu icin."""
    builders: dict[str, Callable[[], None]] = {
        "surrogate": surrogate_panel,
        "pareto": pareto_panel,
        "iso": iso50001_panel,
        "validation": validation_panel,
    }
    for name in sections:
        builders[name]()
