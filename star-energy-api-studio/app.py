from __future__ import annotations

import csv
import io
import os
from typing import Any

from nicegui import run, ui

from client import ApiArchivedScenario, ApiMaterial, EnergyApiClient, EnergyApiError
from engine.estimator import balance_point


API_BASE_URL = os.getenv("ENERJI_API_URL", "http://127.0.0.1:8091")
api_client = EnergyApiClient(API_BASE_URL)
api_health = api_client.status()
model_catalog = api_client.list_models()
active_model_state = {"id": "main-building"}
osm_model = api_client.get_model("main-building")
repository = api_client.get_archived_results("main-building")
baseline = repository.scenarios[5]
star_study = api_client.get_study_results("star-baseline")
star_model = api_client.get_model("star-baseline")
stored_api_runs = api_client.list_simulations("main-building").get("runs", [])
default_quick_study = api_client.quick_study(
    "main-building", [3, 5, 8, 10, 12, 15, 20, 25, 30]
)

MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
END_USE_LABELS = {
    "Cooling": "Soğutma",
    "Heating": "Isıtma",
    "Fans": "Fanlar",
    "Pumps": "Pompalar",
    "Interior Equipment": "İç ekipman",
    "Interior Lighting": "İç aydınlatma",
}


def number(value: float, digits: int = 1) -> str:
    rendered = f"{value:,.{digits}f}"
    return rendered.replace(",", "X").replace(".", ",").replace("X", ".")


def metric_card(icon: str, label: str, value: str, note: str, tone: str = "teal") -> None:
    with ui.card().classes("metric-card min-w-0"):
        with ui.row().classes("w-full items-start justify-between no-wrap"):
            with ui.column().classes("gap-1 min-w-0"):
                ui.label(label).classes("metric-label")
                ui.label(value).classes("metric-value")
                ui.label(note).classes("metric-note")
            ui.icon(icon).classes(f"metric-icon tone-{tone}")


def section_heading(eyebrow: str, title: str, description: str = "") -> None:
    with ui.column().classes("gap-1"):
        ui.label(eyebrow).classes("eyebrow")
        ui.label(title).classes("section-title")
        if description:
            ui.label(description).classes("section-copy")


def energy_pie(scenario: ApiArchivedScenario) -> dict[str, Any]:
    data = [
        {"name": END_USE_LABELS.get(name, name), "value": round(value, 2)}
        for name, value in scenario.end_uses_gj.items()
    ]
    return {
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} GJ ({d}%)"},
        "legend": {"orient": "vertical", "right": 8, "top": "center", "textStyle": {"color": "#68707d"}},
        "series": [{
            "name": "Son kullanım",
            "type": "pie",
            "radius": ["50%", "76%"],
            "center": ["37%", "50%"],
            "avoidLabelOverlap": True,
            "itemStyle": {"borderRadius": 7, "borderColor": "#fffffc", "borderWidth": 3},
            "label": {"show": False},
            "data": data,
        }],
        "color": ["#6657ff", "#ff715b", "#33b9ff", "#101522", "#86be35", "#9b8fff"],
    }


def monthly_chart(scenario: ApiArchivedScenario) -> dict[str, Any]:
    electricity = scenario.monthly_gj.get("Electricity:Facility", [0.0] * 12)
    gas = scenario.monthly_gj.get("NaturalGas:Facility", [0.0] * 12)
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Elektrik", "Doğal gaz"], "top": 0, "textStyle": {"color": "#68707d"}},
        "grid": {"left": 48, "right": 20, "top": 42, "bottom": 36},
        "xAxis": {"type": "category", "data": MONTHS, "axisLabel": {"color": "#68707d"}, "axisLine": {"lineStyle": {"color": "#c9cdc3"}}},
        "yAxis": {"type": "value", "name": "GJ", "nameTextStyle": {"color": "#68707d"}, "axisLabel": {"color": "#68707d"}, "splitLine": {"lineStyle": {"color": "rgba(16,21,34,.08)"}}},
        "series": [
            {"name": "Elektrik", "type": "bar", "data": electricity, "barMaxWidth": 22, "itemStyle": {"color": "#6657ff", "borderRadius": [5, 5, 0, 0]}},
            {"name": "Doğal gaz", "type": "line", "data": gas, "smooth": True, "symbolSize": 7, "lineStyle": {"width": 3, "color": "#ff715b"}, "itemStyle": {"color": "#ff715b"}},
        ],
    }


def comparison_chart() -> dict[str, Any]:
    thicknesses = sorted(repository.scenarios)
    actual = [repository.scenarios[value].site_energy_gj for value in thicknesses]
    quick_by_thickness = {
        point.thickness_cm: point.site_energy_gj
        for point in default_quick_study.results
    }
    estimated = [quick_by_thickness[float(value)] for value in thicknesses]
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Arşiv EnergyPlus", "Düzeltilmiş hızlı tahmin"], "top": 0, "textStyle": {"color": "#68707d"}},
        "grid": {"left": 62, "right": 24, "top": 44, "bottom": 40},
        "xAxis": {"type": "category", "name": "EPS", "data": [f"{value} cm" for value in thicknesses], "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}},
        "yAxis": {"type": "value", "name": "GJ/yıl", "min": 1800, "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}, "splitLine": {"lineStyle": {"color": "rgba(16,21,34,.08)"}}},
        "series": [
            {"name": "Arşiv EnergyPlus", "type": "line", "data": actual, "symbolSize": 10, "lineStyle": {"width": 3, "type": "dashed", "color": "#8a909b"}, "itemStyle": {"color": "#8a909b"}},
            {"name": "Düzeltilmiş hızlı tahmin", "type": "line", "data": estimated, "smooth": True, "symbolSize": 10, "lineStyle": {"width": 4, "color": "#6657ff"}, "itemStyle": {"color": "#6657ff"}, "areaStyle": {"color": "rgba(102,87,255,.10)"}},
        ],
    }


scenario_state = {"value": 5}


@ui.refreshable
def dashboard_content() -> None:
    scenario = repository.scenarios[scenario_state["value"]]
    with ui.element("div").classes("metric-grid w-full"):
        metric_card("bolt", "TOPLAM SAHA ENERJİSİ", f"{number(scenario.site_energy_gj, 1)} GJ", "EnergyPlus yıllık sonuç", "teal")
        metric_card("speed", "ENERJİ YOĞUNLUĞU", f"{number(scenario.eui_mj_m2, 1)} MJ/m²", "Toplam bina alanına göre", "gold")
        metric_card("apartment", "TOPLAM ALAN", f"{number(scenario.total_area_m2, 0)} m²", f"{number(scenario.conditioned_area_m2, 0)} m² iklimlendirilmiş", "blue")
        metric_card("device_thermostat", "KONFOR AŞIMI", f"{number(scenario.unmet_cooling_hours, 2)} saat", "Soğutma set değeri aşımı", "coral")

    with ui.element("div").classes("chart-grid w-full"):
        with ui.card().classes("panel-card"):
            ui.label("Son kullanımlara göre enerji").classes("card-title")
            ui.label(f"EPS {scenario.thickness_cm} cm · arşiv EnergyPlus koşusu").classes("card-subtitle")
            ui.echart(energy_pie(scenario)).classes("w-full h-80")
        with ui.card().classes("panel-card"):
            ui.label("Aylık tüketim profili").classes("card-title")
            ui.label("Tasarım günleri hariç yıllık çalışma dönemi").classes("card-subtitle")
            ui.echart(monthly_chart(scenario)).classes("w-full h-80")

    with ui.card().classes("panel-card w-full"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-1"):
                ui.label("Senaryo karşılaştırması").classes("card-title")
                ui.label("Arşiv sonucu ile düzeltilmiş hızlı tahmin yan yana").classes("card-subtitle")
            ui.badge("VERİ KALİTESİ KONTROLÜ", color="amber-8").props("outline")
        ui.echart(comparison_chart()).classes("w-full h-80")


parametric_state: dict[str, Any] = {
    "points": default_quick_study.results,
    "assumptions": default_quick_study.assumptions,
}


def download_parametric_csv() -> None:
    points = parametric_state["points"]
    if not points:
        ui.notify("İndirilecek senaryo sonucu bulunamadı.", type="warning")
        return
    buffer = io.StringIO()
    rows = [point.to_dict() for point in points]
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    ui.download(
        buffer.getvalue().encode("utf-8-sig"),
        "parametrik_sonuclar.csv",
        "text/csv",
    )


def parametric_chart() -> dict[str, Any]:
    points = parametric_state["points"]
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Saha enerjisi", "U değeri"], "top": 0, "textStyle": {"color": "#68707d"}},
        "grid": {"left": 64, "right": 64, "top": 46, "bottom": 42},
        "xAxis": {"type": "category", "name": "EPS (cm)", "data": [point.thickness_cm for point in points], "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}},
        "yAxis": [
            {"type": "value", "name": "GJ/yıl", "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}, "splitLine": {"lineStyle": {"color": "rgba(16,21,34,.08)"}}},
            {"type": "value", "name": "W/m²K", "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}, "splitLine": {"show": False}},
        ],
        "series": [
            {"name": "Saha enerjisi", "type": "line", "smooth": True, "data": [point.site_energy_gj for point in points], "symbolSize": 9, "lineStyle": {"width": 4, "color": "#6657ff"}, "itemStyle": {"color": "#6657ff"}, "areaStyle": {"color": "rgba(102,87,255,.10)"}},
            {"name": "U değeri", "type": "line", "yAxisIndex": 1, "smooth": True, "data": [point.wall_u_w_m2k for point in points], "lineStyle": {"width": 3, "color": "#ff715b"}, "itemStyle": {"color": "#ff715b"}},
        ],
    }


def star_actual_chart() -> dict[str, Any]:
    colors = {0.03: "#6657ff", 0.035: "#33b9ff", 0.04: "#86be35", 0.05: "#ff715b"}
    series = []
    for conductivity in sorted({item.conductivity_w_mk for item in star_study.tested_scenarios if item.conductivity_w_mk is not None}):
        points = sorted(
            [item for item in star_study.tested_scenarios if item.conductivity_w_mk == conductivity],
            key=lambda item: item.thickness_cm or 0,
        )
        series.append({
            "name": f"λ {conductivity:g}",
            "type": "line",
            "smooth": True,
            "symbolSize": 10,
            "data": [[item.thickness_cm, item.hvac_gj] for item in points],
            "lineStyle": {"width": 3, "color": colors.get(conductivity, "#9b8fff")},
            "itemStyle": {"color": colors.get(conductivity, "#9b8fff")},
        })
    series.append({
        "name": "Referans 10 cm · λ 0,020",
        "type": "scatter",
        "symbol": "diamond",
        "symbolSize": 18,
        "data": [[10, star_study.baseline.hvac_gj]],
        "itemStyle": {"color": "#101522", "borderColor": "#fffffc", "borderWidth": 2},
    })
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0, "textStyle": {"color": "#68707d"}},
        "grid": {"left": 62, "right": 30, "top": 66, "bottom": 44},
        "xAxis": {"type": "value", "name": "Kalınlık (cm)", "min": 1, "max": 11, "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}, "splitLine": {"lineStyle": {"color": "rgba(16,21,34,.08)"}}},
        "yAxis": {"type": "value", "name": "HVAC (GJ)", "min": 30, "axisLabel": {"color": "#68707d"}, "nameTextStyle": {"color": "#68707d"}, "splitLine": {"lineStyle": {"color": "rgba(16,21,34,.08)"}}},
        "series": series,
    }


def star_study_panel() -> None:
    best = star_study.best_tested
    reference = star_study.baseline
    with ui.row().classes("w-full items-start justify-between gap-4"):
        section_heading(
            "STAR.ZIP · GERÇEK PARAMETRİK VERİ",
            "20 EnergyPlus koşusu, ayrı bir 176 m² model",
            "Kalınlık ve iletkenlik birlikte değiştirilmiş; özet veriler iki SQL koşusuyla doğrulanmıştır.",
        )
        ui.badge("GERÇEK ENERGYPLUS", color="teal-8").props("outline").classes("mt-2")
    with ui.element("div").classes("metric-grid w-full"):
        metric_card("play_circle", "TOPLAM KOŞU", str(len(star_study.scenarios)), f"{len(star_study.unique_scenarios)} benzersiz", "teal")
        metric_card("home_work", "MODEL ALANI", "176 m²", f"{star_model.spaces} mekân · {star_model.surfaces} yüzey", "blue")
        metric_card("shield", "REFERANS YALITIM", "10 cm · λ 0,020", "R = 5,00 m²K/W", "gold")
        metric_card("energy_savings_leaf", "EN İYİ TEST", f"{number(best.thickness_cm or 0, 0)} cm · λ {number(best.conductivity_w_mk or 0, 3)}", f"HVAC {number(best.hvac_gj, 2)} GJ", "coral")
    if star_study.baseline_beats_all_tested:
        with ui.element("div").classes("quality-alert w-full"):
            ui.icon("verified", size="24px")
            with ui.column().classes("gap-0"):
                ui.label("Referans senaryo bütün testlerden daha iyi").classes("font-semibold")
                ui.label(
                    f"Referans HVAC {number(reference.hvac_gj, 2)} GJ; en iyi alternatif {number(best.hvac_gj, 2)} GJ. Bunun nedeni referans EPS'nin 10 cm ve λ=0,020 W/mK ile test aralığından daha güçlü olmasıdır."
                ).classes("text-sm opacity-80")
    with ui.card().classes("panel-card w-full"):
        ui.label("Gerçek EnergyPlus sonuç yüzeyi").classes("card-title")
        ui.label("Aynı λ değerindeki noktalar kalınlığa göre bağlanmıştır; elmas işaret referanstır.").classes("card-subtitle")
        ui.echart(star_actual_chart()).classes("w-full h-96")
    rows = []
    for item in star_study.unique_scenarios:
        rows.append({
            "scenario": item.scenario,
            "thickness": "Referans (10)" if item.thickness_cm is None else f"{item.thickness_cm:g}",
            "conductivity": "Referans (0,020)" if item.conductivity_w_mk is None else f"{item.conductivity_w_mk:.3f}",
            "r": "5.000" if item.insulation_r_m2k_w is None else f"{item.insulation_r_m2k_w:.3f}",
            "heating": f"{item.heating_gj:.2f}",
            "cooling": f"{item.cooling_gj:.2f}",
            "hvac": f"{item.hvac_gj:.2f}",
            "site": f"{item.site_energy_gj:.2f}",
        })
    with ui.card().classes("panel-card w-full"):
        ui.label("Benzersiz Star senaryoları").classes("card-title")
        ui.label(f"Tekrarlanan {star_study.duplicate_count} koşu tabloda bir kez gösterilir.").classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "scenario", "label": "Senaryo", "field": "scenario", "align": "left"},
                {"name": "thickness", "label": "cm", "field": "thickness", "align": "right", "sortable": True},
                {"name": "conductivity", "label": "λ", "field": "conductivity", "align": "right", "sortable": True},
                {"name": "r", "label": "R", "field": "r", "align": "right", "sortable": True},
                {"name": "heating", "label": "Isıtma", "field": "heating", "align": "right", "sortable": True},
                {"name": "cooling", "label": "Soğutma", "field": "cooling", "align": "right", "sortable": True},
                {"name": "hvac", "label": "HVAC (GJ)", "field": "hvac", "align": "right", "sortable": True},
                {"name": "site", "label": "Saha (GJ)", "field": "site", "align": "right", "sortable": True},
            ],
            rows=rows,
            row_key="scenario",
            pagination={"rowsPerPage": 15},
        ).classes("w-full studio-table")


@ui.refreshable
def parametric_results() -> None:
    points = parametric_state["points"]
    optimum = balance_point(points)
    with ui.element("div").classes("metric-grid w-full"):
        metric_card("straighten", "DENGE NOKTASI", f"{number(optimum.thickness_cm, 0)} cm", "Marjinal kazanç yavaşlıyor", "gold")
        metric_card("shield", "DUVAR U DEĞERİ", f"{number(optimum.wall_u_w_m2k, 3)} W/m²K", f"R = {number(optimum.wall_r_m2k_w, 2)} m²K/W", "teal")
        metric_card("energy_savings_leaf", "TAHMİNİ TASARRUF", f"%{number(optimum.savings_percent, 2)}", f"{number(optimum.savings_gj, 1)} GJ/yıl", "blue")
        metric_card("monitoring", "TAHMİNİ ENERJİ", f"{number(optimum.site_energy_gj, 1)} GJ", "5 cm arşiv koşusuna göre", "coral")
    with ui.card().classes("panel-card w-full"):
        ui.label("EPS kalınlığı · enerji · U değeri").classes("card-title")
        ui.label("Hesap yalnızca duvar iletimine duyarlı payı değiştirir; diğer yükleri korur.").classes("card-subtitle")
        ui.echart(parametric_chart()).classes("w-full h-96")
    rows = [
        {
            "thickness": f"{point.thickness_cm:g}",
            "u": f"{point.wall_u_w_m2k:.3f}",
            "energy": f"{point.site_energy_gj:.2f}",
            "eui": f"{point.eui_mj_m2:.2f}",
            "savings": f"%{point.savings_percent:.2f}",
        }
        for point in points
    ]
    with ui.card().classes("panel-card w-full"):
        ui.label("Senaryo sonuçları").classes("card-title")
        ui.table(
            columns=[
                {"name": "thickness", "label": "EPS (cm)", "field": "thickness", "align": "left", "sortable": True},
                {"name": "u", "label": "U (W/m²K)", "field": "u", "align": "right", "sortable": True},
                {"name": "energy", "label": "Enerji (GJ/yıl)", "field": "energy", "align": "right", "sortable": True},
                {"name": "eui", "label": "EUI (MJ/m²)", "field": "eui", "align": "right", "sortable": True},
                {"name": "savings", "label": "Tasarruf", "field": "savings", "align": "right", "sortable": True},
            ],
            rows=rows,
            row_key="thickness",
            pagination={"rowsPerPage": 12},
        ).classes("w-full studio-table")


construction_state = {"name": "duvr_std_eps"}


def api_run_rows(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "thickness": f"{item['case']['thickness_cm']:g} cm",
            "status": "Başarılı" if item["success"] else "Başarısız",
            "energy": f"{item['summary']['site_energy_gj']:.2f}"
            if item.get("summary")
            else "—",
            "eui": f"{item['summary']['eui_mj_m2']:.2f}"
            if item.get("summary")
            else "—",
            "sql": "Hazır" if item["sql_available"] else "Yok",
        }
        for item in results
    ]


real_run_state: dict[str, list[dict[str, str]]] = {
    "rows": api_run_rows(stored_api_runs)
}


def activate_model(model_id: str) -> None:
    global osm_model, model_catalog

    selected = api_client.get_model(model_id)
    runs = api_client.list_simulations(model_id).get("runs", [])
    osm_model = selected
    active_model_state["id"] = model_id
    model_catalog = api_client.list_models()
    construction_names = [item.name for item in selected.constructions]
    construction_state["name"] = (
        "duvr_std_eps"
        if "duvr_std_eps" in construction_names
        else (construction_names[0] if construction_names else "")
    )
    real_run_state["rows"] = api_run_rows(runs)


@ui.refreshable
def construction_details() -> None:
    construction = osm_model.find_construction(construction_state["name"])
    if construction is None:
        ui.label("Konstrüksiyon bulunamadı.").classes("text-negative")
        return
    with ui.element("div").classes("metric-grid w-full"):
        metric_card("layers", "KATMAN SAYISI", str(len(construction.layers)), "Dıştan içe OSM sırası", "teal")
        metric_card("thermostat", "U DEĞERİ", f"{number(construction.u_value_w_m2k, 3)} W/m²K", "Yüzey dirençleri dahil", "gold")
        metric_card("view_in_ar", "TOPLAM R", f"{number(construction.r_total_with_films_m2k_w, 3)} m²K/W", "Rsi 0,13 + Rse 0,04", "blue")
        metric_card("format_list_numbered", "AÇIK ATAMA", str(construction.surface_count), "Doğrudan bağlı yüzey", "coral")
    layer_rows = []
    r_series = []
    for index, layer in enumerate(construction.layers, start=1):
        if isinstance(layer, ApiMaterial):
            data = layer.to_dict()
            layer_rows.append({
                "index": index,
                "name": data["name"],
                "thickness": "—" if data["thickness_cm"] is None else f"{data['thickness_cm']:.1f}",
                "conductivity": "—" if data["conductivity_w_mk"] is None else f"{data['conductivity_w_mk']:.3f}",
                "r": "—" if data["r_value_m2k_w"] is None else f"{data['r_value_m2k_w']:.3f}",
            })
            if data["r_value_m2k_w"]:
                r_series.append({"name": data["name"], "value": data["r_value_m2k_w"]})
        else:
            layer_rows.append({"index": index, "name": layer["name"], "thickness": "—", "conductivity": "—", "r": "—"})
    with ui.element("div").classes("chart-grid w-full"):
        with ui.card().classes("panel-card"):
            ui.label("Katmanlar").classes("card-title")
            ui.table(
                columns=[
                    {"name": "index", "label": "#", "field": "index", "align": "left"},
                    {"name": "name", "label": "Malzeme", "field": "name", "align": "left"},
                    {"name": "thickness", "label": "cm", "field": "thickness", "align": "right"},
                    {"name": "conductivity", "label": "λ", "field": "conductivity", "align": "right"},
                    {"name": "r", "label": "R", "field": "r", "align": "right"},
                ], rows=layer_rows, row_key="index"
            ).classes("w-full studio-table")
        with ui.card().classes("panel-card"):
            ui.label("Isıl direnç katkısı").classes("card-title")
            ui.label("Her malzeme katmanının toplam R içindeki payı").classes("card-subtitle")
            ui.echart({
                "tooltip": {"trigger": "item"},
                "series": [{"type": "pie", "radius": ["48%", "74%"], "itemStyle": {"borderColor": "#fffffc", "borderWidth": 3, "borderRadius": 6}, "data": r_series}],
                "color": ["#6657ff", "#ff715b", "#33b9ff", "#101522", "#86be35", "#9b8fff"],
            }).classes("w-full h-80")


@ui.refreshable
def real_run_results() -> None:
    rows = real_run_state["rows"]
    if not rows:
        return
    with ui.card().classes("panel-card w-full"):
        ui.label("Yeni API simülasyon sonuçları").classes("card-title")
        ui.label("Bu oturumda OpenStudio SDK + EnergyPlus ile üretilen sonuçlar").classes("card-subtitle")
        ui.table(
            columns=[
                {"name": "thickness", "label": "EPS", "field": "thickness", "align": "left"},
                {"name": "status", "label": "Durum", "field": "status", "align": "left"},
                {"name": "energy", "label": "Saha enerjisi (GJ)", "field": "energy", "align": "right"},
                {"name": "eui", "label": "EUI (MJ/m²)", "field": "eui", "align": "right"},
                {"name": "sql", "label": "SQL", "field": "sql", "align": "center"},
            ],
            rows=rows,
            row_key="thickness",
        ).classes("w-full studio-table")


def page_header(drawer) -> None:
    with ui.header().classes("studio-header"):
        with ui.row().classes("w-full items-center justify-between px-4 lg:px-7"):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="menu", on_click=drawer.toggle).props("flat round").classes("mobile-menu")
                ui.label("STAR Enerji Simülasyonu").classes("header-title")
            with ui.row().classes("items-center gap-3"):
                with ui.row().classes("system-pill items-center gap-2"):
                    ui.element("span").classes("live-dot")
                    ui.label("HTTP API çevrimiçi").classes("text-xs")
                ui.badge(f"OPENSTUDIO {osm_model.openstudio_version}").classes("api-badge hidden sm:flex")


@ui.page("/")
def main_page() -> None:
    ui.colors(primary="#6657ff", secondary="#b8ff52", accent="#ff715b", positive="#4f8f22", negative="#c94836")

    async def scroll_navigation(distance: int) -> None:
        await ui.run_javascript(
            "document.querySelector('.aurora-tabs .q-tabs__content')"
            f"?.scrollBy({{left:{distance},behavior:'smooth'}})"
        )

    upload_state: dict[str, Any] = {
        "osm_name": None,
        "osm_bytes": None,
        "weather_name": None,
        "weather_bytes": None,
    }

    async def receive_osm(event) -> None:
        upload_state["osm_name"] = event.file.name
        upload_state["osm_bytes"] = await event.file.read()
        osm_upload_status.text = f"Hazır: {event.file.name}"

    async def receive_weather(event) -> None:
        upload_state["weather_name"] = event.file.name
        upload_state["weather_bytes"] = await event.file.read()
        weather_upload_status.text = f"Hazır: {event.file.name}"

    async def import_uploaded_model() -> None:
        model_name = str(model_name_input.value or "").strip()
        if not model_name:
            ui.notify("Model adını girin.", type="warning")
            return
        if upload_state["osm_bytes"] is None:
            ui.notify("Bir .osm dosyası seçin ve yükleyin.", type="warning")
            return
        import_status.text = "OSM, HTTP API üzerinden OpenStudio ile doğrulanıyor…"
        import_button.disable()
        try:
            imported = await run.io_bound(
                api_client.upload_model,
                name=model_name,
                osm_filename=str(upload_state["osm_name"]),
                osm_bytes=upload_state["osm_bytes"],
                weather_filename=upload_state["weather_name"],
                weather_bytes=upload_state["weather_bytes"],
            )
            if imported is None:
                raise EnergyApiError("API model yanıtı alınamadı.")
            activate_model(imported.model_id)
        except EnergyApiError as exc:
            import_status.text = str(exc)
            ui.notify(str(exc), type="negative")
            import_button.enable()
            return
        model_dialog.close()
        ui.notify(
            f"{imported.name} API model deposuna eklendi ve seçildi.",
            type="positive",
        )
        ui.navigate.reload()

    def choose_model(event) -> None:
        try:
            activate_model(str(event.value))
        except EnergyApiError as exc:
            ui.notify(str(exc), type="negative")
            return
        ui.notify(f"{osm_model.name} seçildi.", type="positive")
        ui.navigate.reload()

    with ui.dialog() as model_dialog, ui.card().classes("model-upload-dialog"):
        with ui.row().classes("w-full items-start justify-between no-wrap"):
            with ui.column().classes("gap-1"):
                ui.label("Yeni OpenStudio modeli").classes("card-title")
                ui.label(
                    "OSM ve isteğe bağlı EPW, HTTP API'ye yüklenir; OpenStudio doğrulamasından sonra model kimliği üretilir."
                ).classes("card-subtitle")
            ui.button(icon="close", on_click=model_dialog.close).props("flat round dense")
        model_name_input = ui.input("Model adı", placeholder="Örn. Ofis binası").classes("w-full")
        with ui.row().classes("w-full gap-4 items-start flex-wrap"):
            with ui.column().classes("upload-column gap-2 flex-1"):
                ui.label("OSM model dosyası · zorunlu").classes("text-sm font-bold")
                ui.upload(
                    label=".osm seç",
                    on_upload=receive_osm,
                    auto_upload=True,
                    max_file_size=100 * 1024 * 1024,
                ).props("accept=.osm flat bordered").classes("w-full")
                osm_upload_status = ui.label("Henüz OSM seçilmedi").classes("upload-status")
            with ui.column().classes("upload-column gap-2 flex-1"):
                ui.label("EPW hava dosyası · isteğe bağlı").classes("text-sm font-bold")
                ui.upload(
                    label=".epw seç",
                    on_upload=receive_weather,
                    auto_upload=True,
                    max_file_size=50 * 1024 * 1024,
                ).props("accept=.epw flat bordered").classes("w-full")
                weather_upload_status = ui.label("Hava dosyası seçilmedi").classes("upload-status")
        with ui.element("div").classes("api-flow-note w-full"):
            ui.icon("account_tree", size="22px")
            ui.label("Tarayıcı → NiceGUI yükleme geçidi → HTTP API → güvenli model deposu → OpenStudio SDK")
        import_status = ui.label("").classes("text-sm text-slate-600")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Vazgeç", on_click=model_dialog.close).props("flat")
            import_button = ui.button(
                "API ile doğrula ve ekle",
                icon="cloud_upload",
                on_click=import_uploaded_model,
            ).props("unelevated").classes("action-button")

    with ui.row().classes("floating-nav items-center gap-2 no-wrap"):
        with ui.row().classes("items-center gap-3 brand-block no-wrap"):
            with ui.element("div").classes("brand-cube"):
                ui.icon("bolt", size="23px")
            with ui.column().classes("brand-copy gap-0"):
                ui.label("STAR").classes("brand-name")
                ui.label("BUILDING ENERGY OS").classes("brand-kicker")
        with ui.row().classes("tab-scroll-shell items-center no-wrap"):
            left_nav = ui.button(
                icon="chevron_left", on_click=lambda: scroll_navigation(-280)
            ).props("flat round dense").classes("nav-scroll-button")
            with left_nav:
                ui.tooltip("Menüyü sola kaydır")
            with ui.tabs().props("inline-label dense no-caps indicator-color=transparent") .classes("aurora-tabs") as tabs:
                overview_tab = ui.tab("overview", label="Enerji Merkezi", icon="blur_circular")
                parametric_tab = ui.tab("build", label="Senaryo Kurucu", icon="tune")
                runner_tab = ui.tab("live", label="Canlı Akış", icon="graphic_eq")
                model_tab = ui.tab("assets", label="Model ve Varlıklar", icon="widgets")
                diagnostics_tab = ui.tab("history", label="Geçmiş ve Tanılama", icon="history")
            right_nav = ui.button(
                icon="chevron_right", on_click=lambda: scroll_navigation(280)
            ).props("flat round dense").classes("nav-scroll-button")
            with right_nav:
                ui.tooltip("Menüyü sağa kaydır")
        ui.space()
        with ui.row().classes("desktop-actions items-center gap-2 no-wrap"):
            with ui.row().classes("system-active items-center gap-2"):
                ui.element("span").classes("status-dot")
                ui.label("HTTP API aktif").classes("text-xs font-bold")
            ui.badge(f"OS {osm_model.openstudio_version}").classes("version-chip")
    with ui.column().classes("star-shell w-full pb-12 gap-6"):
        with ui.element("section").classes("hero w-full") as hero_section:
            with ui.column().classes("gap-4 max-w-4xl"):
                ui.label("OPENSTUDIO · ENERGYPLUS · GERÇEK PROJE VERİSİ").classes("hero-eyebrow")
                ui.label("Bina enerjisini, tek bir akışta simüle et.").classes("hero-title")
                ui.label(
                    "Modeli HTTP API üzerinden inceleyin; EPS senaryolarını karşılaştırın ve gerçek OpenStudio koşularını aynı çalışma alanından yönetin."
                ).classes("hero-copy")
                with ui.row().classes("gap-3 flex-wrap"):
                    ui.badge(
                        f"{len(repository.scenarios) + len(star_study.scenarios)} GERÇEK KOŞU",
                        color="white",
                        text_color="teal-9",
                    ).classes("hero-badge")
                    ui.badge(f"{osm_model.spaces} MEKÂN", color="white", text_color="teal-9").classes("hero-badge")
                    ui.badge(f"{osm_model.surfaces} YÜZEY", color="white", text_color="teal-9").classes("hero-badge")
            with ui.element("div").classes("hero-orbit"):
                with ui.column().classes("items-center gap-0"):
                    ui.icon("home_work", size="48px")
                    ui.label(f"{number(baseline.site_energy_gj, 0)} GJ").classes("font-extrabold text-lg")
                    ui.label("REFERANS KOŞU").classes("orbit-caption")

        with ui.row().classes("architecture-strip w-full items-center justify-center gap-2") as architecture_bar:
            for index, (icon, label) in enumerate([
                ("dashboard", "NiceGUI"),
                ("api", "HTTP API"),
                ("memory", "OpenStudio servis katmanı"),
                ("inventory_2", "Model deposu"),
            ]):
                with ui.row().classes("architecture-node items-center gap-2"):
                    ui.icon(icon).classes("text-cyan")
                    ui.label(label).classes("text-xs font-bold")
                if index < 3:
                    ui.icon("arrow_forward").classes("architecture-arrow")

        def update_intro(event) -> None:
            visible = event.value == "overview"
            hero_section.set_visibility(visible)
            architecture_bar.set_visibility(visible)

        tabs.on_value_change(update_intro)

        with ui.tab_panels(tabs, value=overview_tab).classes("w-full bg-transparent p-0"):
            with ui.tab_panel(overview_tab).classes("p-0"):
                with ui.column().classes("w-full gap-6"):
                    with ui.row().classes("w-full justify-between items-end gap-4"):
                        section_heading("01 · GENEL BAKIŞ", "Arşivlenmiş EnergyPlus sonuçları", "Gerçek SQL çıktıları doğrudan okunur; ekran görüntülerinden veri kopyalanmaz.")
                        ui.select(
                            options={5: "EPS 5 cm", 10: "EPS 10 cm", 15: "EPS 15 cm"},
                            value=5,
                            label="Arşiv senaryosu",
                            on_change=lambda event: (
                                scenario_state.update(value=int(event.value)),
                                dashboard_content.refresh(),
                            ),
                        ).classes("scenario-select w-48")
                    if repository.archived_runs_are_identical:
                        with ui.element("div").classes("quality-alert w-full"):
                            ui.icon("warning_amber", size="24px")
                            with ui.column().classes("gap-0"):
                                ui.label("Üç arşiv koşusunun enerji sonuçları aynı").classes("font-semibold")
                                ui.label("Eski kod alternatif konstrüksiyonu oluşturmuş fakat modele uygulamamış. Düzeltilmiş akış, konstrüksiyonu yerinde güncelliyor.").classes("text-sm opacity-80")
                    dashboard_content()

            with ui.tab_panel(parametric_tab).classes("p-0"):
                with ui.column().classes("w-full gap-6"):
                    section_heading("02 · PARAMETRİK STÜDYO", "EPS kalınlığını saniyeler içinde tarayın", "5 cm EnergyPlus koşusuna kalibre edilen hızlı model, olası eğilimi gösterir; nihai doğrulama gerçek OpenStudio koşusudur.")
                    with ui.card().classes("control-card w-full"):
                        with ui.row().classes("w-full items-end gap-4 flex-wrap"):
                            start_input = ui.number("Başlangıç (cm)", value=3, min=1, max=50, step=1).classes("w-40")
                            end_input = ui.number("Bitiş (cm)", value=30, min=2, max=60, step=1).classes("w-40")
                            step_input = ui.number("Adım (cm)", value=2, min=1, max=10, step=1).classes("w-36")
                            conductivity_input = ui.number("EPS λ (W/mK)", value=0.039, min=0.02, max=0.08, step=0.001, format="%.3f").classes("w-48")

                            def calculate() -> None:
                                start = float(start_input.value or 3)
                                end = float(end_input.value or 30)
                                step = float(step_input.value or 2)
                                conductivity = float(conductivity_input.value or 0.039)
                                if end < start:
                                    ui.notify("Bitiş kalınlığı başlangıçtan küçük olamaz.", type="negative")
                                    return
                                values = []
                                current = start
                                while current <= end + 1e-9 and len(values) < 80:
                                    values.append(round(current, 4))
                                    current += step
                                if 5.0 not in values:
                                    values.append(5.0)
                                try:
                                    quick_study = api_client.quick_study(
                                        "main-building", values, conductivity
                                    )
                                except EnergyApiError as exc:
                                    ui.notify(str(exc), type="negative")
                                    return
                                points = quick_study.results
                                parametric_state.update(
                                    points=points,
                                    assumptions=quick_study.assumptions,
                                )
                                parametric_results.refresh()
                                ui.notify(
                                    f"{len(points)} senaryo HTTP API tarafından hesaplandı.",
                                    type="positive",
                                )

                            ui.button("Hızlı simülasyonu çalıştır", icon="auto_graph", on_click=calculate).props("unelevated").classes("action-button")
                            ui.button(
                                "CSV indir", icon="download", on_click=download_parametric_csv
                            ).props("flat")
                    parametric_results()
                    with ui.expansion("Hızlı modelin varsayımları", icon="science").classes("assumption-panel w-full"):
                        ui.markdown(
                            """
- Referans: arşivdeki **5 cm EPS EnergyPlus koşusu** (1.941,59 GJ/yıl).
- EPS dışındaki duvar katmanları ve yüzey dirençleri sabit tutulur.
- Isıtmanın %55'i, soğutmanın %18'i duvar iletimine duyarlı kabul edilir.
- Fan ve pompa yükleri HVAC değişimini sınırlı oranda izler; aydınlatma ve ekipman sabittir.
- Sonuçlar **mühendislik ön tahmini**dir; ruhsat, yatırım veya kesin tasarım hesabı değildir.
                            """
                        ).classes("prose max-w-none")
                    ui.separator().classes("my-5 opacity-40")
                    star_study_panel()

            with ui.tab_panel(model_tab).classes("p-0"):
                with ui.column().classes("w-full gap-6"):
                    with ui.row().classes("w-full justify-between items-end gap-4 flex-wrap"):
                        section_heading(
                            "03 · MODEL GEZGİNİ",
                            "OSM yapısını ve katmanlarını inceleyin",
                            f"Seçili model: {osm_model.name} · {osm_model.model_id}. NiceGUI yalnızca model kimliğiyle HTTP API'ye bağlanır; OSM yalnızca OpenStudio {osm_model.openstudio_version} SDK servisinde açılır.",
                        )
                        with ui.row().classes("items-end gap-2 flex-wrap"):
                            ui.select(
                                options={
                                    str(item["id"]): str(item["name"])
                                    for item in model_catalog
                                },
                                value=active_model_state["id"],
                                label="API model deposu",
                                on_change=choose_model,
                            ).classes("w-72")
                            ui.button(
                                "Yeni OSM yükle",
                                icon="add_circle",
                                on_click=model_dialog.open,
                            ).props("outline no-caps").classes("model-upload-button")
                    with ui.row().classes("w-full justify-between items-center gap-4 flex-wrap"):
                        with ui.row().classes("api-source-chip items-center gap-2"):
                            ui.icon("verified_user", size="18px")
                            ui.label("Kaynak: HTTP API · OpenStudio SDK").classes("text-xs font-bold")
                        ui.select(
                            options=[item.name for item in osm_model.constructions],
                            value=construction_state["name"],
                            label="Konstrüksiyon",
                            on_change=lambda event: (
                                construction_state.update(name=str(event.value)),
                                construction_details.refresh(),
                            ),
                        ).classes("w-72")
                    with ui.element("div").classes("metric-grid w-full"):
                        metric_card("meeting_room", "MEKÂNLAR", str(osm_model.spaces), "OS:Space nesnesi", "teal")
                        metric_card("device_hub", "ISIL BÖLGELER", str(osm_model.thermal_zones), "OS:ThermalZone nesnesi", "gold")
                        metric_card("dashboard_customize", "YÜZEYLER", str(osm_model.surfaces), f"+ {osm_model.subsurfaces} alt yüzey", "blue")
                        metric_card("layers", "KONSTRÜKSİYON", str(len(osm_model.constructions)), f"{len(osm_model.materials)} malzeme kaydı", "coral")
                    construction_details()
                    with ui.card().classes("panel-card w-full"):
                        ui.label("Isıl bölge özeti").classes("card-title")
                        ui.label("Seçili modelin OpenStudio SDK projeksiyonundan").classes("card-subtitle")
                        ui.table(
                            columns=[
                                {"name": "zone", "label": "Bölge", "field": "zone", "align": "left", "sortable": True},
                                {"name": "conditioned", "label": "İklimlendirilmiş", "field": "conditioned", "align": "center"},
                                {"name": "area_m2", "label": "Alan (m²)", "field": "area_m2", "align": "right", "sortable": True},
                                {"name": "volume_m3", "label": "Hacim (m³)", "field": "volume_m3", "align": "right", "sortable": True},
                                {"name": "window_area_m2", "label": "Cam (m²)", "field": "window_area_m2", "align": "right", "sortable": True},
                                {"name": "lighting_w_m2", "label": "Aydınlatma (W/m²)", "field": "lighting_w_m2", "align": "right"},
                            ],
                            rows=osm_model.zones,
                            row_key="zone",
                            pagination={"rowsPerPage": 10},
                        ).classes("w-full studio-table")

            with ui.tab_panel(runner_tab).classes("p-0"):
                with ui.column().classes("w-full gap-6"):
                    section_heading(
                        "04 · OPENSTUDIO KOŞUSU",
                        "Düzeltilmiş modeli EnergyPlus ile çalıştırın",
                        f"Aktif model: {osm_model.name} · {osm_model.model_id}. NiceGUI isteği HTTP API'ye gönderir; servis OpenStudio SDK ile modeli hazırlar ve EnergyPlus koşusunu yönetir.",
                    )
                    openstudio_status = api_health.get("openstudio", {})
                    cli_path = openstudio_status.get("executable")
                    cli_version = openstudio_status.get("version")
                    with ui.element("div").classes("runner-status w-full"):
                        ui.icon("check_circle" if cli_path else "info", size="28px").classes("text-positive" if cli_path else "text-amber-9")
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(f"OpenStudio {cli_version} API hazır" if cli_path else "OpenStudio CLI bu bilgisayarda bulunamadı").classes("font-bold text-lg")
                            ui.label(str(cli_path) if cli_path else "Gerçek koşu için OpenStudio kurulmalı veya OPENSTUDIO_EXE ayarlanmalı.").classes("text-sm opacity-75 break-all")
                    with ui.card().classes("control-card w-full"):
                        with ui.row().classes("w-full items-end gap-4 flex-wrap"):
                            cases_input = ui.input("EPS kalınlıkları (cm)", value="5, 10, 15").classes("w-72")
                            real_conductivity = ui.number("EPS λ (W/mK)", value=0.039, min=0.02, max=0.08, step=0.001, format="%.3f").classes("w-48")
                            status_label = ui.label("").classes("text-sm font-medium")

                            def parse_cases() -> list[float]:
                                values = [float(item.strip()) for item in str(cases_input.value).replace(";", ",").split(",") if item.strip()]
                                if not values:
                                    raise ValueError("En az bir kalınlık girin.")
                                return values

                            def prepare() -> None:
                                try:
                                    response = api_client.prepare_simulations(
                                        active_model_state["id"],
                                        parse_cases(),
                                        float(real_conductivity.value or 0.039),
                                        construction_state["name"],
                                    )
                                except (ValueError, EnergyApiError) as exc:
                                    ui.notify(str(exc), type="negative")
                                    return
                                status_label.text = f"{len(response['runs'])} OSW iş akışı API tarafından hazırlandı."
                                ui.notify("OpenStudio iş akışları HTTP API üzerinden hazırlandı.", type="positive")

                            async def execute() -> None:
                                if not cli_path:
                                    ui.notify("OpenStudio CLI bulunamadı.", type="warning")
                                    return
                                try:
                                    cases = parse_cases()
                                except ValueError as exc:
                                    ui.notify(str(exc), type="negative")
                                    return
                                status_label.text = "Simülasyon çalışıyor; bu işlem birkaç dakika sürebilir…"
                                try:
                                    response = await run.io_bound(
                                        api_client.run_simulations,
                                        active_model_state["id"],
                                        cases,
                                        float(real_conductivity.value or 0.039),
                                        construction_state["name"],
                                    )
                                except EnergyApiError as exc:
                                    status_label.text = str(exc)
                                    ui.notify(str(exc), type="negative")
                                    return
                                results = response["runs"]
                                success_count = sum(bool(item["success"]) for item in results)
                                real_run_state["rows"] = api_run_rows(results)
                                real_run_results.refresh()
                                status_label.text = f"{success_count}/{len(results)} koşu API üzerinden başarılı."
                                ui.notify(status_label.text, type="positive" if success_count == len(results) else "warning")

                            ui.button("OSW dosyalarını hazırla", icon="description", on_click=prepare).props("outline")
                            real_button = ui.button("Gerçek simülasyonu başlat", icon="play_arrow", on_click=execute).props("unelevated").classes("action-button")
                            if cli_path is None:
                                real_button.props("disable")
                    real_run_results()
                    with ui.card().classes("panel-card w-full"):
                        ui.label("Arşiv koşuları").classes("card-title")
                        ui.label("12 Mayıs 2026 tarihli EnergyPlus 25.1 sonuçları").classes("card-subtitle")
                        archive_rows = [
                            {
                                "case": f"EPS {value} cm",
                                "status": item.run_status,
                                "energy": f"{item.site_energy_gj:.2f}",
                                "warnings": item.warnings,
                                "severe": item.severe_errors,
                            }
                            for value, item in repository.scenarios.items()
                        ]
                        ui.table(
                            columns=[
                                {"name": "case", "label": "Senaryo", "field": "case", "align": "left"},
                                {"name": "status", "label": "Durum", "field": "status", "align": "left"},
                                {"name": "energy", "label": "Enerji (GJ)", "field": "energy", "align": "right"},
                                {"name": "warnings", "label": "Uyarı", "field": "warnings", "align": "right"},
                                {"name": "severe", "label": "Ciddi", "field": "severe", "align": "right"},
                            ], rows=archive_rows, row_key="case"
                        ).classes("w-full studio-table")

            with ui.tab_panel(diagnostics_tab).classes("p-0"):
                with ui.column().classes("w-full gap-6"):
                    section_heading("05 · TANILAMA", "Veri kalitesi ve model uyarıları", "Başarılı tamamlanma, modelin hatasız olduğu anlamına gelmez; ciddi uyarılar burada görünür tutulur.")
                    with ui.element("div").classes("metric-grid w-full"):
                        metric_card("warning", "UYARI", str(baseline.warnings), "EnergyPlus mesajı", "gold")
                        metric_card("error_outline", "CİDDİ HATA", str(baseline.severe_errors), "Boyutlandırma aşaması", "coral")
                        metric_card("window", "TOPLAM WWR", f"%{number(baseline.window_wall_ratio.get('Total', 0), 1)}", "Pencere/duvar oranı", "blue")
                        metric_card("schedule", "SİMÜLASYON", baseline.general.get("Hours Simulated", "—"), "Yıllık çalışma dönemi", "teal")
                    with ui.card().classes("panel-card w-full"):
                        ui.label("Öncelikli EnergyPlus mesajları").classes("card-title")
                        issue_rows = [
                            {"severity": issue.severity, "count": issue.occurrences, "message": issue.message}
                            for issue in baseline.issues
                        ]
                        ui.table(
                            columns=[
                                {"name": "severity", "label": "Seviye", "field": "severity", "align": "left", "sortable": True},
                                {"name": "count", "label": "Adet", "field": "count", "align": "right", "sortable": True},
                                {"name": "message", "label": "Mesaj", "field": "message", "align": "left"},
                            ], rows=issue_rows, row_key="message", pagination={"rowsPerPage": 10}
                        ).classes("w-full issue-table")
                    with ui.card().classes("panel-card w-full"):
                        ui.label("Birleştirilen kaynaklar").classes("card-title")
                        ui.label("Her kaynağın projedeki karşılığı").classes("card-subtitle")
                        source_rows = [
                            {"source": "openstudio_api_projesi", "used": "4.246 m² ana OSM + EPW + üç SQL koşusu + eski Python/NiceGUI fikri", "state": "Birleştirildi"},
                            {"source": "Star.zip", "used": "176 m² ikinci model + 20 gerçek parametrik EnergyPlus koşusu + beş Python betiği", "state": "Birleştirildi ve SQL ile doğrulandı"},
                            {"source": "parametric_simulation.py", "used": "OSW üretme ve CLI çalıştırma yaklaşımı", "state": "Taşınabilir hale getirildi"},
                            {"source": "OpenStudio.zip", "used": "JSON dışa/içe aktarma measure'ları", "state": "Entegrasyon klasöründe"},
                            {"source": "123 ekran görüntüsü", "used": "Karşılaştırma, grafik, malzeme ve tanılama ihtiyaçları", "state": "Arayüz tasarımına işlendi"},
                            {"source": "enerji.zip", "used": "Boş proje.py ve taşınamayan eski sanal ortam", "state": "Kod katkısı yok"},
                            {"source": "Unconfirmed .crdownload", "used": "Aktif ve kilitli kısmi indirme", "state": "Tamamlanmış dosya olmadığı için dışarıda"},
                        ]
                        ui.table(
                            columns=[
                                {"name": "source", "label": "Kaynak", "field": "source", "align": "left"},
                                {"name": "used", "label": "Projeye katkısı", "field": "used", "align": "left"},
                                {"name": "state", "label": "Durum", "field": "state", "align": "left"},
                            ], rows=source_rows, row_key="source"
                        ).classes("w-full studio-table")

        with ui.row().classes("w-full justify-between items-center pt-4 text-xs text-slate-500"):
            ui.label("Enerji Optimizasyon Stüdyosu · NiceGUI + OpenStudio + EnergyPlus")
            ui.label("Veri kaynağı: 12.05.2026 arşiv koşuları")


ui.add_head_html(
    """
<style>
  :root { --ink:#102a2e; --muted:#65737e; --paper:#f3f1eb; --card:#ffffff; --teal:#0f766e; --gold:#e8a23a; --blue:#315d79; --coral:#d96b55; }
  body { background: var(--paper); color: var(--ink); font-family: Inter, "Segoe UI", Arial, sans-serif; }
  .q-page { min-height: 100vh; }
  .studio-header { background: rgba(243,241,235,.92)!important; color:var(--ink)!important; border-bottom:1px solid rgba(16,42,46,.09); backdrop-filter: blur(18px); box-shadow:none!important; }
  .brand-mark { width:38px; height:38px; border-radius:12px; display:flex; align-items:center; justify-content:center; color:white; background:linear-gradient(145deg,#0f766e,#155b57); box-shadow:0 8px 20px rgba(15,118,110,.24); }
  .brand-name { font-size:16px; line-height:1.1; font-weight:900; letter-spacing:.14em; }
  .brand-kicker { font-size:9px; line-height:1.1; color:#718087; letter-spacing:.12em; font-weight:700; }
  .hero { min-height:330px; margin-top:26px; padding:48px 52px; border-radius:28px; color:white; overflow:hidden; position:relative; display:flex; align-items:center; justify-content:space-between; background:radial-gradient(circle at 80% 20%,rgba(232,162,58,.22),transparent 30%),linear-gradient(118deg,#0b4745,#0f766e 55%,#17645e); box-shadow:0 22px 56px rgba(15,78,75,.18); }
  .hero:after { content:""; position:absolute; inset:0; opacity:.16; background-image:linear-gradient(rgba(255,255,255,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.12) 1px,transparent 1px); background-size:36px 36px; mask-image:linear-gradient(90deg,transparent,black); pointer-events:none; }
  .hero > * { position:relative; z-index:1; }
  .hero-eyebrow,.eyebrow { font-size:11px; font-weight:900; letter-spacing:.16em; }
  .hero-eyebrow { color:#f3c470; }
  .hero-title { font-size:clamp(34px,5vw,64px); line-height:1.02; font-weight:800; max-width:900px; letter-spacing:-.045em; }
  .hero-copy { max-width:760px; color:rgba(255,255,255,.78); font-size:17px; line-height:1.65; }
  .hero-badge { padding:8px 12px; border-radius:999px; font-weight:800; letter-spacing:.06em; }
  .hero-orbit { width:160px; height:160px; border:1px solid rgba(255,255,255,.24); border-radius:50%; align-items:center; justify-content:center; color:#f3c470; box-shadow:0 0 0 28px rgba(255,255,255,.04),0 0 0 56px rgba(255,255,255,.03); margin-right:60px; }
  .studio-tabs { background:white; border:1px solid rgba(16,42,46,.08); border-radius:16px; padding:5px; box-shadow:0 8px 26px rgba(39,60,65,.06); }
  .studio-tabs .q-tab { border-radius:11px; color:#63747a; min-height:48px; }
  .studio-tabs .q-tab--active { color:var(--teal); background:#e8f3f1; }
  .section-title { font-size:clamp(24px,3vw,36px); font-weight:800; letter-spacing:-.025em; }
  .section-copy { color:var(--muted); max-width:830px; font-size:14px; line-height:1.55; }
  .eyebrow { color:var(--teal); }
  .metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }
  .chart-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
  .metric-card,.panel-card,.control-card { border:1px solid rgba(16,42,46,.08)!important; box-shadow:0 10px 30px rgba(40,60,64,.055)!important; border-radius:18px!important; background:var(--card)!important; }
  .metric-card { padding:20px!important; }
  .panel-card { padding:24px!important; }
  .control-card { padding:20px!important; background:#fbfaf7!important; }
  .metric-label { font-size:10px; font-weight:900; color:#77848b; letter-spacing:.11em; }
  .metric-value { font-size:clamp(22px,2.5vw,31px); line-height:1.15; font-weight:850; letter-spacing:-.035em; white-space:nowrap; }
  .metric-note,.card-subtitle { color:#829097; font-size:12px; }
  .metric-icon { padding:10px; border-radius:12px; }
  .tone-teal { color:#0f766e; background:#e7f3f0; }.tone-gold { color:#b56a00;background:#fff1d6;}.tone-blue {color:#315d79;background:#e7eef3;}.tone-coral{color:#c05640;background:#fdebe6;}
  .card-title { font-size:18px; font-weight:800; letter-spacing:-.015em; }
  .quality-alert,.runner-status { display:flex; align-items:flex-start; gap:13px; padding:17px 20px; border-radius:15px; }
  .quality-alert { color:#6f4a08; background:#fff2d8; border:1px solid #f0d495; }
  .runner-status { color:#1f4043; background:#e7f3f0; border:1px solid #c2ded9; }
  .action-button { min-height:44px; padding:0 18px; font-weight:750; border-radius:11px; }
  .scenario-select .q-field__control,.control-card .q-field__control { border-radius:11px!important; }
  .studio-table thead tr,.issue-table thead tr { background:#f4f7f6; color:#54646a; }
  .studio-table th,.issue-table th { font-size:11px!important; letter-spacing:.04em; font-weight:850!important; }
  .studio-table td,.issue-table td { border-color:#edf0ef!important; }
  .issue-table td:last-child { white-space:normal!important; min-width:520px; line-height:1.45; }
  .assumption-panel { background:white; border:1px solid rgba(16,42,46,.08); border-radius:16px; }
  @media (max-width:1100px) { .metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.chart-grid{grid-template-columns:1fr;}.hero{padding:38px 34px;} }
  @media (max-width:640px) { .metric-grid{grid-template-columns:1fr;}.hero{min-height:390px;padding:34px 24px;border-radius:20px;}.studio-tabs .q-tab__label{font-size:10px}.studio-tabs .q-tab{padding:0 6px}.panel-card{padding:18px!important}.issue-table td:last-child{min-width:300px}.metric-value{white-space:normal;} }
</style>
    """,
    shared=True,
)

ui.add_head_html(
    """
<style>
  :root {
    --aurora-paper:#f2f3ed; --aurora-paper-2:#e8eae2; --aurora-ink:#101522;
    --aurora-muted:#68707d; --aurora-line:rgba(16,21,34,.11);
    --aurora-lime:#b8ff52; --aurora-violet:#6657ff; --aurora-coral:#ff715b; --aurora-blue:#33b9ff;
  }
  html,body,#app,.q-layout,.q-page-container,.q-page {
    min-height:100%; color:var(--aurora-ink)!important; background:transparent!important;
    font-family:"Plus Jakarta Sans","Segoe UI",Arial,sans-serif;
  }
  body {
    margin:0; background:radial-gradient(circle at 8% 14%,rgba(184,255,82,.20),transparent 24%),
      radial-gradient(circle at 92% 9%,rgba(102,87,255,.13),transparent 25%),
      radial-gradient(circle at 72% 94%,rgba(255,113,91,.12),transparent 26%),var(--aurora-paper)!important;
    background-attachment:fixed!important;
  }
  .nicegui-content { padding:0!important; }
  * { scrollbar-width:thin; scrollbar-color:rgba(16,21,34,.26) transparent; }
  @keyframes aurora-page-in { from{opacity:0;transform:translateY(16px) scale(.992)} to{opacity:1;transform:translateY(0) scale(1)} }
  @keyframes aurora-ping { 0%{box-shadow:0 0 0 0 rgba(96,153,42,.52)} 70%{box-shadow:0 0 0 8px rgba(96,153,42,0)} 100%{box-shadow:0 0 0 0 rgba(96,153,42,0)} }
  @keyframes aurora-core { 0%,100%{transform:rotate(-3deg) scale(1)} 50%{transform:rotate(2deg) scale(1.035)} }
  .floating-nav {
    position:sticky!important; top:16px; z-index:80; width:calc(100% - 56px); max-width:1540px;
    margin:16px auto 0; padding:10px 12px; border-radius:22px;
    background:rgba(255,255,252,.82)!important; border:1px solid rgba(16,21,34,.09);
    box-shadow:0 18px 55px rgba(16,21,34,.10); backdrop-filter:blur(22px); overflow-x:auto;
  }
  .brand-block { padding-right:8px; }
  .brand-cube { width:42px;height:42px;display:grid;place-items:center;border-radius:14px;color:var(--aurora-ink);background:var(--aurora-lime);box-shadow:inset 0 -5px 12px rgba(16,21,34,.12);transform:rotate(-5deg); }
  .brand-name { color:var(--aurora-ink);font-size:18px;line-height:1;font-weight:900;letter-spacing:.12em; }
  .brand-kicker { color:#657064;font:700 8px "Segoe UI",sans-serif;letter-spacing:.12em; }
  .tab-scroll-shell { flex:1;min-width:0;gap:4px;padding:2px 4px;border-radius:16px;background:rgba(242,243,237,.62); }
  .aurora-tabs { flex:1;min-width:0;color:#717887;overflow:hidden; }
  .aurora-tabs .q-tabs__content { gap:3px;justify-content:flex-start; }
  .aurora-tabs .q-tab { min-height:40px;padding:0 12px;border-radius:13px;transition:.2s ease; }
  .aurora-tabs .q-tab__content { flex-direction:row!important;gap:7px;min-width:0; }
  .aurora-tabs .q-tab__label { font-size:11px;font-weight:750;text-transform:none;white-space:nowrap; }
  .aurora-tabs .q-tab:hover { color:var(--aurora-ink);background:#f0f1eb;transform:translateY(-1px); }
  .aurora-tabs .q-tab--active { color:white!important;background:var(--aurora-ink)!important;box-shadow:0 8px 20px rgba(16,21,34,.14); }
  .aurora-tabs .q-tabs__arrow { display:none!important; }
  .nav-scroll-button { flex:0 0 34px;width:34px;height:34px;min-height:34px!important;border-radius:11px!important;color:var(--aurora-ink)!important;background:linear-gradient(145deg,#f8f9f4,#e7e9e1)!important;border:1px solid rgba(16,21,34,.10);box-shadow:0 5px 14px rgba(16,21,34,.10); }
  .nav-scroll-button:hover { background:var(--aurora-lime)!important;transform:translateY(-1px); }
  .tab-scroll-shell:not(:has(.q-tabs--scrollable)) .nav-scroll-button { opacity:.24;pointer-events:none;box-shadow:none; }
  .aurora-tabs.q-tabs--scrollable .q-tabs__content { border-radius:13px;mask-image:linear-gradient(90deg,transparent 0,#000 12px,#000 calc(100% - 12px),transparent 100%); }
  .system-active { padding:7px 10px;border-radius:999px;background:#eef0e9;color:var(--aurora-ink); }
  .status-dot { width:8px;height:8px;border-radius:50%;background:#70b933;animation:aurora-ping 1.8s infinite; }
  .version-chip { padding:6px 9px;border-radius:999px;background:rgba(102,87,255,.09)!important;color:var(--aurora-violet)!important;border:1px solid rgba(102,87,255,.12); }
  .star-shell { width:100%;max-width:1540px;margin:0 auto;padding:22px 28px 54px!important;gap:22px;animation:aurora-page-in .45s cubic-bezier(.22,.9,.22,1) both; }
  .hero { min-height:330px;margin:0;padding:40px 44px;border-radius:28px;color:var(--aurora-ink)!important;background:linear-gradient(130deg,#b8ff52,#d5ff93 72%,#c6ff73)!important;border:1px solid rgba(16,21,34,.08);box-shadow:0 20px 55px rgba(16,21,34,.09); }
  .hero:after { opacity:.075;background-image:linear-gradient(rgba(16,21,34,.18) 1px,transparent 1px),linear-gradient(90deg,rgba(16,21,34,.18) 1px,transparent 1px); }
  .hero-eyebrow,.eyebrow { color:#596255!important;font-size:10px;font-weight:850;letter-spacing:.14em; }
  .hero-title { color:var(--aurora-ink);font-size:clamp(34px,4.3vw,60px);line-height:.98;max-width:930px; }
  .hero-copy { color:rgba(16,21,34,.68);max-width:800px; }
  .hero-badge { background:rgba(255,255,255,.46)!important;color:var(--aurora-ink)!important;border:1px solid rgba(16,21,34,.09); }
  .hero-orbit { display:flex!important;width:178px;height:178px;margin-right:46px;border:0;border-radius:48px;color:white;background:var(--aurora-ink);box-shadow:0 0 0 28px rgba(16,21,34,.045),0 24px 45px rgba(16,21,34,.16);animation:aurora-core 4s ease-in-out infinite; }
  .orbit-caption { color:var(--aurora-lime);font-size:9px;font-weight:800;letter-spacing:.12em; }
  .architecture-strip { padding:12px 16px;border:1px solid var(--aurora-line);border-radius:20px;background:rgba(255,255,252,.74);box-shadow:0 12px 34px rgba(16,21,34,.05); }
  .architecture-node { padding:8px 12px;color:var(--aurora-ink);border:1px solid rgba(16,21,34,.08);background:#f8f9f4;border-radius:999px; }
  .architecture-node .q-icon { color:var(--aurora-violet)!important; }
  .architecture-arrow { color:#a2a89e; }
  .q-tab-panels,.q-tab-panel,.q-panel { background:transparent!important;color:var(--aurora-ink)!important; }
  .section-title,.card-title,.metric-value { color:var(--aurora-ink)!important; }
  .section-copy,.muted,.metric-note,.card-subtitle { color:var(--aurora-muted)!important; }
  .metric-card,.panel-card,.control-card { color:var(--aurora-ink)!important;background:rgba(255,255,252,.82)!important;border:1px solid var(--aurora-line)!important;box-shadow:0 18px 48px rgba(16,21,34,.07)!important;border-radius:26px!important;backdrop-filter:blur(18px);transition:transform .23s ease,box-shadow .23s ease,border-color .23s ease; }
  .metric-card:hover,.panel-card:hover { transform:translateY(-3px);box-shadow:0 26px 64px rgba(16,21,34,.105)!important;border-color:rgba(102,87,255,.22)!important; }
  .metric-card { padding:21px!important; }
  .panel-card { padding:23px!important; }
  .control-card { padding:21px!important;background:rgba(246,247,241,.88)!important; }
  .metric-label { color:#717887; }
  .tone-teal { color:#4c3ee5;background:rgba(102,87,255,.10); }
  .tone-gold { color:#a75410;background:rgba(255,113,91,.13); }
  .tone-blue { color:#087bad;background:rgba(51,185,255,.13); }
  .tone-coral { color:#a73726;background:rgba(255,113,91,.13); }
  .quality-alert { color:#694810;background:#fff4ca;border:1px solid #ead58a; }
  .runner-status { color:#253c16;background:#e6ffc5;border:1px solid #bade87; }
  .assumption-panel { color:var(--aurora-ink)!important;background:rgba(255,255,252,.82)!important;border:1px solid var(--aurora-line);border-radius:20px; }
  .q-field--outlined .q-field__control { border-radius:15px!important;background:rgba(255,255,255,.58); }
  .q-field--outlined .q-field__control:before { border-color:rgba(16,21,34,.15)!important; }
  .q-field--outlined .q-field__control:hover:before { border-color:rgba(102,87,255,.42)!important; }
  .q-field__native,.q-field__input,.q-field__label,.q-field__marginal { color:var(--aurora-ink)!important; }
  .q-field--focused .q-field__label { color:var(--aurora-violet)!important; }
  .q-slider__selection,.q-linear-progress__model { background:var(--aurora-violet)!important; }
  .q-slider__thumb { color:var(--aurora-violet)!important; }
  .q-menu { color:var(--aurora-ink)!important;background:#fffffc!important;border:1px solid var(--aurora-line); }
  .q-item { color:var(--aurora-ink)!important; }
  .q-table__container { color:var(--aurora-ink)!important;background:transparent!important;box-shadow:none!important; }
  .studio-table thead tr,.issue-table thead tr { background:rgba(16,21,34,.035);color:var(--aurora-muted); }
  .studio-table th,.issue-table th { color:#6d7480!important; }
  .studio-table td,.issue-table td { border-color:rgba(16,21,34,.07)!important; }
  .studio-table tbody tr:hover,.issue-table tbody tr:hover { background:rgba(184,255,82,.12)!important; }
  .q-table__bottom { color:var(--aurora-muted); }
  .q-btn.action-button { color:white!important;background:var(--aurora-ink)!important;box-shadow:0 10px 24px rgba(16,21,34,.14); }
  .model-upload-button { min-height:48px;border-radius:14px;color:var(--aurora-ink)!important;border-color:rgba(16,21,34,.18)!important;background:rgba(255,255,252,.70)!important; }
  .model-upload-dialog { width:min(760px,calc(100vw - 30px));max-width:760px;padding:26px!important;gap:18px;border-radius:28px!important;color:var(--aurora-ink)!important;background:#fffffc!important;border:1px solid var(--aurora-line);box-shadow:0 30px 90px rgba(16,21,34,.20)!important; }
  .model-upload-dialog .q-uploader { min-height:164px;border-radius:18px!important;background:#f7f8f2!important;border:1px dashed rgba(16,21,34,.20)!important;box-shadow:none!important; }
  .model-upload-dialog .q-uploader__header { color:var(--aurora-ink)!important;background:rgba(184,255,82,.70)!important; }
  .upload-column { min-width:260px; }
  .upload-status { color:var(--aurora-muted);font-size:11px; }
  .api-flow-note { display:flex;align-items:center;gap:10px;padding:13px 15px;border-radius:15px;color:#463cb0;background:rgba(102,87,255,.08);border:1px solid rgba(102,87,255,.14);font-size:12px;font-weight:650; }
  .api-source-chip { padding:9px 12px;border-radius:999px;color:#3c611f;background:#e9ffd0;border:1px solid #c9eba3; }
  .text-cyan { color:var(--aurora-violet)!important; }
  .text-slate-500 { color:var(--aurora-muted)!important; }
  @media(max-width:1100px) {
    .aurora-tabs .q-tab__label { display:none; }
    .aurora-tabs .q-tab { min-width:40px;padding:0 9px; }
    .hero { padding:36px 32px; }
    .hero-orbit { display:none!important; }
  }
  @media(max-width:720px) {
    .floating-nav { top:8px;width:calc(100% - 28px);margin-top:8px;border-radius:18px;padding:8px; }
    .brand-copy,.desktop-actions { display:none!important; }
    .brand-block { padding-right:0; }
    .brand-cube { width:38px;height:38px;border-radius:12px; }
    .star-shell { padding:14px 14px 38px!important; }
    .hero { min-height:360px;padding:30px 23px;border-radius:24px; }
    .architecture-strip { flex-direction:column; }
    .architecture-arrow { transform:rotate(90deg); }
    .model-upload-dialog { padding:21px!important;max-height:92vh;overflow-y:auto; }
    .upload-column { width:100%;min-width:0;flex-basis:100%; }
  }
  @media(prefers-reduced-motion:reduce) {
    *,*::before,*::after { animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important; }
  }
</style>
    """,
    shared=True,
)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Enerji Simülasyon Stüdyosu",
        favicon="⚡",
        host="127.0.0.1",
        port=int(os.getenv("ENERJI_PORT", "8090")),
        reload=False,
        show=os.getenv("ENERJI_SHOW", "1") != "0",
    )
