"""Faz 4-7 sonuclarini gosteren arayuz panelleri.

Veri okuma ui_pages/study_data.py icindedir; bu modul yalnizca cizim yapar.
Her panel veri hazir degilken de calisir ve durumu bildirir.
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from ui_pages import study_data

# app.py'deki yardimcilarla ayni gorunumu korumak icin ayni sinif adlari.
# app.py icinde tanimli olan sinif panel-card'tir; studio-card diye bir
# stil yoktur ve kullanilirsa kartlar Quasar varsayilanina dusup
# genisligi doldurmaz.
CARD = "panel-card w-full"
TABLE = "w-full studio-table"


def tr(value: float, digits: int = 2) -> str:
    """Turkce sayi bicimi: binlik ayraci nokta, ondalik ayraci virgul.

    Python'un varsayilan bicimi ("1,920.5") arayuzun geri kalaniyla
    tutarsizdi; bu binada 1.920 ile 1,920 farkli sayilar gibi okunuyordu.
    """
    text = f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")



# Dogrulama raporundaki gerekce metinleri ASCII uretilir (kod icinde Turkce
# karakter tutulmaz); arayuzde ve raporda tam Turkce gosterilir.
REASON_TEXT = {
    "uc nokta": "uç nokta",
    "cephe dagilimi": "cephe dağılımı",
    "TOPSIS uzlasi cozumu": "TOPSIS uzlaşı çözümü",
    "Konfor ihlali (bolge-saat)": "konfor ihlali",
    "EnPI (kWh/m2-yil)": "EnPİ",
    "Yatirim maliyeti (TRY)": "yatırım maliyeti",
}


def reason_label(raw: str) -> str:
    text = raw
    for source, target in REASON_TEXT.items():
        text = text.replace(source, target)
    return text


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
    """Sekiz fazın durumunu tek şeritte gösterir."""
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
        "Parametrik çalışma ve vekil model",
        "Gerçek EnergyPlus koşularından eğitilen hızlı tahmin modeli.",
    )

    if not status.ready:
        _empty(
            "Parametrik çalışma henüz sonuç üretmedi.",
            "run_parametric_study.py çalıştırılmalıdır.",
        )
        return

    with ui.grid(columns=4).classes("w-full gap-3"):
        _metric(
            "dataset",
            "KOŞU SAYISI",
            f"{status.completed}",
            f"{status.unique_results} benzersiz sonuç",
            "teal" if status.all_unique else "coral",
        )
        _metric(
            "bolt",
            "ENERJİ ARALIĞI",
            f"{tr(status.site_energy_min_gj, 0)} – {tr(status.site_energy_max_gj, 0)}",
            "GJ/yıl (taban 1.920)",
        )
        _metric(
            "casino",
            "ÖRNEKLEYİCİ",
            status.sampler,
            f"tohum {status.seed}",
        )
        if status.with_severe_errors:
            _metric(
                "warning",
                "CİDDİ HATA UYARISI",
                f"{len(status.with_severe_errors)}",
                "ısınma yakınsaması",
                "gold",
            )
        else:
            _metric("verified", "CİDDİ HATA", "0", "tüm koşular temiz")

    if not report.ready:
        _empty("Vekil model henüz eğitilmedi.", "run_surrogate.py çalıştırılmalıdır.")
        return

    with ui.card().classes(CARD):
        ui.label("Bağımsız test kümesi").classes("card-title")
        ui.label(
            "Kapı yalnızca amaç fonksiyonlarını besleyen hedeflere bakar; "
            "diğerleri raporlanır ama kapıyı belirlemez."
        ).classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "target", "label": "Hedef", "field": "target", "align": "left"},
                {"name": "model", "label": "Model", "field": "model", "align": "left"},
                {"name": "r2", "label": "R²", "field": "r2", "align": "right"},
                {"name": "metric", "label": "Ölçüt", "field": "metric", "align": "left"},
                {"name": "error", "label": "Hata", "field": "error", "align": "right"},
                {"name": "gate", "label": "Kapı", "field": "gate", "align": "center"},
            ],
            rows=report.test_rows(),
            row_key="target",
        ).classes(TABLE)

    with ui.grid(columns=3).classes("w-full gap-3"):
        _metric(
            "speed",
            "HIZLANMA",
            f"{tr(report.speedup_ratio, 0)}x",
            f"{tr(report.seconds_per_call * 1e6, 1)} mikrosaniye / değerlendirme",
        )
        _metric(
            "school",
            "EĞİTİM KÜMESİ",
            f"{report.rows}",
            f"{report.features} öznitelik",
        )
        _metric(
            "flag",
            "FAZ 4 KAPISI",
            "GEÇİLDİ" if report.gate_passed else "GEÇİLMEDİ",
            ", ".join(report.gate_targets),
            "teal" if report.gate_passed else "coral",
        )

    if report.sensitivity:
        with ui.card().classes(CARD):
            ui.label("Sobol duyarlılık analizi").classes("card-title")
            ui.label(
                "S₁ değişkenin tek başına, S_T etkileşimler dâhil toplam katkısıdır. "
                "Saha enerjisi varyansı üzerinden hesaplanır."
            ).classes("card-subtitle")
            ui.echart(_sensitivity_chart(report.sensitivity)).classes("w-full h-80")


def _sensitivity_chart(indices: list[dict]) -> dict:
    ordered = sorted(indices, key=lambda item: item["total"])
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": ["S₁ (tek başına)", "S_T (etkileşim dâhil)"]},
        "grid": {"left": 180, "right": 24, "top": 40, "bottom": 30},
        "xAxis": {"type": "value", "name": "varyans payı"},
        "yAxis": {
            "type": "category",
            "data": [item["label"] for item in ordered],
            "axisLabel": {"fontSize": 11},
        },
        "series": [
            {
                "name": "S₁ (tek başına)",
                "type": "bar",
                "data": [round(item["first_order"], 4) for item in ordered],
            },
            {
                "name": "S_T (etkileşim dâhil)",
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
        "Çok amaçlı optimizasyon",
        "EnPİ, yatırım maliyeti ve konfor ihlali eş zamanlı en aza indirilir.",
    )

    if not view.ready:
        _empty("Pareto cephesi henüz üretilmedi.", "run_optimization.py çalıştırılmalıdır.")
        return

    if not view.usable_in_thesis:
        with ui.card().classes(CARD):
            with ui.row().classes("items-center gap-3"):
                ui.icon("science").classes("metric-icon tone-gold")
                with ui.column().classes("gap-1"):
                    ui.label(
                        f"Bu cephe '{view.evaluator}' değerlendiricisiyle üretildi."
                    ).classes("card-title")
                    ui.label(
                        "Yalnızca altyapı sınamasıdır; sonuçları tezde kullanılamaz."
                    ).classes("card-subtitle")

    if not view.validated:
        with ui.element("div").classes("quality-alert w-full"):
            ui.icon("pending_actions").classes("metric-icon tone-gold")
            with ui.column().classes("gap-0"):
                ui.label("Bu cephe doğrulanmadı").classes("font-semibold")
                ui.label(
                    view.validation_status
                    or "Cephe yeniden üretildi; Faz 7 doğrulaması bu cephe için "
                       "henüz işletilmedi."
                ).classes("text-sm opacity-80")

    with ui.grid(columns=3).classes("w-full gap-3"):
        _metric("hub", "ÇÖZÜM SAYISI", f"{view.solution_count}", "Pareto cephesi")
        _metric(
            "trending_up",
            "HİPERVOLÜM",
            tr(view.hypervolume_end, 4),
            f"başlangıç {tr(view.hypervolume_start, 4)}",
        )
        _metric("verified_user", "KAYNAK", view.evaluator, "değerlendirici")

    with ui.card().classes(CARD):
        ui.label("Cephe: EnPİ – yatırım maliyeti").classes("card-title")
        ui.label(
            "Sol alt köşe ideal bölgedir; hiçbir çözüm diğerine her üç amaçta "
            "birden üstün değildir."
        ).classes("card-subtitle")
        ui.echart(_front_chart(view)).classes("w-full h-96")

    if view.convergence:
        with ui.card().classes(CARD):
            ui.label("Yakınsama").classes("card-title")
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
        "xAxis": {"type": "value", "name": "EnPİ (kWh/m²·yıl)", "nameLocation": "middle", "nameGap": 30},
        "yAxis": {"type": "value", "name": "Yatırım (TL)", "nameLocation": "middle", "nameGap": 55},
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
        "yAxis": {"type": "value", "name": "hipervolüm"},
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
        "ISO 50001 kapsamı",
        "Önemli enerji kullanımı, enerji taban çizgisi ve performans göstergeleri.",
    )

    if not view.ready:
        _empty("ISO 50001 raporu üretilmedi.", "build_iso50001_report.py çalıştırılmalıdır.")
        return

    with ui.card().classes(CARD):
        with ui.row().classes("items-center gap-3"):
            ui.icon("info").classes("metric-icon tone-gold")
            with ui.column().classes("gap-1"):
                ui.label("Enerji taban çizgisi ölçülmemiştir").classes("card-title")
                ui.label(view.notice).classes("card-subtitle")

    with ui.grid(columns=4).classes("w-full gap-3"):
        _metric("speed", "EnPİ", tr(view.eui_kwh_m2, 1), "kWh/m²·yıl")
        _metric("bolt", "TABAN ÇİZGİSİ", tr(view.baseline_gj, 0), "GJ/yıl")
        _metric("ac_unit", "HDD 18", tr(view.hdd, 0), "ısıtma derece-gün")
        _metric("wb_sunny", "CDD 22", tr(view.cdd, 0), "soğutma derece-gün")

    with ui.card().classes(CARD):
        ui.label("Önemli enerji kullanımı (SEU)").classes("card-title")
        ui.label(
            f"Pareto ölçütü: kümülatif pay %80'e ulaşana kadar. "
            f"Kapsam: {', '.join(view.significant_uses)}"
        ).classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "label", "label": "Son kullanım", "field": "label", "align": "left"},
                {"name": "energy_gj", "label": "GJ/yıl", "field": "energy_gj", "align": "right"},
                {"name": "share_percent", "label": "Pay %", "field": "share_percent", "align": "right"},
                {"name": "cumulative_percent", "label": "Kümülatif %", "field": "cumulative_percent", "align": "right"},
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
    pareto = study_data.load_pareto()
    _heading(
        "FAZ 7",
        "Simülasyon destekli sayısal doğrulama",
        "Pareto cephesinden seçilen noktalar gerçek EnergyPlus ile koşulur.",
    )

    if not view.ready:
        _empty("Doğrulama koşusu yapılmadı.", "run_validation.py çalıştırılmalıdır.")
        return

    with ui.grid(columns=3).classes("w-full gap-3"):
        _metric(
            "rule",
            "EN BÜYÜK SAPMA",
            f"%{tr(view.max_deviation_percent)}",
            "tolerans %5,0",
            "teal" if view.within_tolerance else "coral",
        )
        _metric("straighten", "NOKTA SAYISI", f"{len(view.points)}", "gerçek EnergyPlus koşusu")
        _metric(
            "flag",
            "FAZ 7 KAPISI",
            "GEÇİLDİ" if view.within_tolerance else "GEÇİLMEDİ",
            "her noktada sapma < %5",
            "teal" if view.within_tolerance else "coral",
        )

    if pareto.ready and not pareto.validated:
        with ui.element("div").classes("quality-alert w-full"):
            ui.icon("history").classes("metric-icon tone-gold")
            with ui.column().classes("gap-0"):
                ui.label(
                    "Bu sonuçlar önceki cepheye aittir"
                ).classes("font-semibold")
                ui.label(
                    "Pareto sekmesindeki güncel cephe TS 825 düzeltmesinden "
                    "sonra yeniden üretildi; buradaki noktalar o cepheden "
                    "seçilmemiştir. Yöntemin kurulumunu belgeler."
                ).classes("text-sm opacity-80")

    with ui.card().classes(CARD):
        ui.label("Vekil model tahmini ile gerçek koşu karşılaştırması").classes("card-title")
        ui.label(
            "Pozitif sapma vekil modelin fazla tahmin ettiğini gösterir. "
            "Değerler EnPİ cinsindendir (kWh/m²·yıl)."
        ).classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "case_id", "label": "Senaryo", "field": "case_id", "align": "left"},
                {"name": "predicted_enpi_kwh_m2", "label": "Vekil", "field": "predicted_enpi_kwh_m2", "align": "right"},
                {"name": "actual_enpi_kwh_m2", "label": "Gerçek", "field": "actual_enpi_kwh_m2", "align": "right"},
                {"name": "deviation_percent", "label": "Sapma %", "field": "deviation_percent", "align": "right"},
                {"name": "reason", "label": "Gerekçe", "field": "reason", "align": "left"},
            ],
            rows=[
                {
                    "case_id": item["case_id"],
                    "predicted_enpi_kwh_m2": tr(float(item["predicted_enpi_kwh_m2"])),
                    "actual_enpi_kwh_m2": tr(float(item["actual_enpi_kwh_m2"])),
                    "deviation_percent": tr(float(item["deviation_percent"])),
                    "reason": reason_label(item["reason"]),
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
    """Panelleri sırayla çizer; test ve tek sayfa görünümü için."""
    builders: dict[str, Callable[[], None]] = {
        "surrogate": surrogate_panel,
        "pareto": pareto_panel,
        "iso": iso50001_panel,
        "validation": validation_panel,
    }
    for name in sections:
        builders[name]()
