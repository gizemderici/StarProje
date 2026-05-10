from __future__ import annotations

from typing import Iterable

from nicegui import ui


def build_status_panel_markdown(title: str, items: Iterable[str]) -> str:
    lines = [f"**{title}**"]
    normalized_items = [str(item).strip() for item in items if str(item).strip()]
    if not normalized_items:
        lines.append("- Ek durum bilgisi yok.")
    else:
        lines.extend(f"- {item}" for item in normalized_items)
    return "\n".join(lines)


def build_commentary_panel_markdown(title: str, items: Iterable[str]) -> str:
    lines = [f"**{title}**"]
    normalized_items = [str(item).strip() for item in items if str(item).strip()]
    if not normalized_items:
        lines.append("- Henuz yorum olusturulamadi.")
    else:
        lines.extend(f"- {item}" for item in normalized_items)
    return "\n".join(lines)


def build_card_action_row(source_text: str) -> dict[str, object]:
    with ui.row().classes("w-full items-center justify-between gap-3"):
        source_label = ui.label(f"Veri Kaynagi: {source_text}").classes("text-xs text-slate-500")
        with ui.row().classes("items-center gap-2"):
            status_badge = ui.label("BEKLENIYOR").classes(
                "text-[10px] font-bold tracking-wide px-2 py-1 rounded bg-slate-200 text-slate-700"
            )
            refresh_button = ui.button("Yenile").props("outline dense size=sm")
            why_empty_button = ui.button("Neden Bos?").props("flat dense size=sm")
    why_empty_label = ui.label("").classes("text-xs text-slate-600")
    return {
        "source_label": source_label,
        "status_badge": status_badge,
        "refresh_button": refresh_button,
        "why_empty_button": why_empty_button,
        "why_empty_label": why_empty_label,
    }


def build_selected_analysis_signature(
    comparison_entries: list[dict[str, object]],
    selected_name: str,
) -> tuple[tuple[tuple[str, float], ...], str]:
    return (
        tuple(
            (
                str(item.get("scenario_name", "")),
                float(item.get("report_mtime", 0) or 0),
            )
            for item in comparison_entries
        ),
        str(selected_name or "").strip(),
    )


def build_missing_metrics_markdown(
    *,
    title: str,
    selected_name: str,
    missing_metric_ids: Iterable[str],
    null_metric_ids: Iterable[str],
    report_path: str,
) -> str:
    missing_values = [str(item).strip() for item in missing_metric_ids if str(item).strip()]
    null_values = [str(item).strip() for item in null_metric_ids if str(item).strip()]
    if not missing_values and not null_values:
        return ""

    lines = [
        f"**{title} veri durumu**",
        f"- Senaryo: {selected_name or '-'}",
    ]
    if missing_values:
        lines.append("- Eksik metric_id: " + ", ".join(missing_values))
    if null_values:
        lines.append("- Degeri bos metric_id: " + ", ".join(null_values))
    if report_path:
        lines.append(f"- Rapor: `{report_path}`")
    lines.append("- Not: Bu durumda grafik eksik veya bos gorunebilir.")
    return "\n".join(lines)


def build_run_artifacts_markdown(
    *,
    title: str,
    artifacts: list[tuple[str, str | None]],
    lead: str = "",
) -> str:
    lines: list[str] = [f"**{title}**"]
    if lead:
        lines.append(f"- {lead}")
    for label, path in artifacts:
        if not path:
            continue
        lines.append(f"- {label}: `{path}`")
    return "\n".join(lines)


def build_analytics_tab_section(
    *,
    monthly_labels_tr: list[str],
    monthly_tooltip_formatter: str,
    zone_tooltip_formatter: str,
    comfort_band_min_c: float,
    comfort_band_max_c: float,
) -> dict[str, object]:
    with ui.card().classes("w-full dashboard-panel"):
        ui.label("Senaryo Analizi").classes("text-lg font-semibold text-slate-900")
        ui.label("Bolum 7 - Aciklama ve Yorum Paneli").classes("text-sm font-medium text-slate-700")
        analytics_info = ui.label("").classes("text-sm text-slate-600")
        with ui.card().classes("w-full dashboard-summary-card bg-slate-50 border border-slate-200"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("tune").classes("text-slate-700")
                ui.label("Analiz Kontrol Cubugu").classes("text-sm font-medium text-slate-800")
            with ui.row().classes("w-full items-end gap-3"):
                analysis_scenario_select = ui.select(options=[], label="Senaryo Secimi").classes("w-full dashboard-input")
                refresh_all_button = ui.button("Analizi Yenile").props("color=primary icon=refresh unelevated")
            with ui.row().classes("w-full gap-3 items-center"):
                last_refresh_label = ui.label("Son Guncelleme: -").classes("text-sm text-slate-600")
                analysis_data_status = ui.label("Durum: veri bekleniyor").classes("text-sm text-slate-600")
                analysis_status_badge = ui.label("VERI BEKLENIYOR").classes(
                    "text-[10px] font-bold tracking-wide px-2 py-1 rounded bg-slate-200 text-slate-700"
                )
            analysis_workflow_markdown = ui.markdown("").classes("w-full text-sm")
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
        with ui.card().classes("w-full dashboard-panel bg-amber-50 border border-amber-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("psychology").classes("text-amber-800")
                ui.label("Beklenen Etki / Parametre Ozeti").classes("text-sm font-medium text-amber-900")
            ui.label(
                "Bu bolum secilen parametrelerin degisim desenini ve beklenen etki baglamini gosterir; gercek simulasyon sonucu degildir."
            ).classes("text-sm text-amber-800")
            expected_effect_info = ui.label(
                "Parametre degisim yogunlugu ve secim akisinin ozeti burada gorunur."
            ).classes("text-sm text-amber-900")
        with ui.card().classes("w-full dashboard-panel bg-emerald-50 border border-emerald-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("bolt").classes("text-emerald-800")
                ui.label("Gercek Simulasyon Sonucu / Enerji Performansi").classes("text-sm font-medium text-emerald-900")
            energy_actions = build_card_action_row("comparison report")
            energy_performance_status = ui.markdown("").classes("w-full text-sm")
            energy_performance_commentary = ui.markdown("").classes("w-full text-sm")
            energy_performance_info = ui.label(
                "Bu grafik baz ve guncellenmis senaryonun annual heating, cooling ve total energy degerlerini ayni alanda karsilastirir."
            ).classes("text-sm text-slate-700")
            analytics_missing_metrics = ui.markdown("").classes("w-full text-sm")
            energy_performance_chart = ui.echart(
                {
                    "tooltip": {"trigger": "item"},
                    "legend": {"data": ["Base Scenario", "Updated Scenario"], "top": 8},
                    "xAxis": {"type": "value", "name": "kWh"},
                    "yAxis": {
                        "type": "category",
                        "data": ["Annual Heating", "Annual Cooling", "Total Energy"],
                    },
                    "series": [
                        {
                            "name": "Baglanti",
                            "type": "line",
                            "data": [],
                            "showSymbol": False,
                            "lineStyle": {"width": 1, "color": "#94a3b8", "opacity": 0.8},
                            "tooltip": {"show": False},
                            "silent": True,
                        },
                        {
                            "name": "Base Scenario",
                            "type": "scatter",
                            "data": [],
                            "itemStyle": {"color": "#94a3b8"},
                            "symbolSize": 12,
                        },
                        {
                            "name": "Scenario",
                            "type": "scatter",
                            "data": [],
                            "itemStyle": {"color": "#0f766e"},
                            "symbolSize": 12,
                        },
                    ],
                }
            ).classes("w-full h-72")
        with ui.row().classes("items-center gap-2"):
            ui.icon("timeline").classes("text-slate-700")
            ui.label("Run-to-Run Trend").classes("text-sm font-medium")
        run_trend_actions = build_card_action_row("comparison report serisi")
        run_trend_status = ui.markdown("").classes("w-full text-sm")
        run_trend_commentary = ui.markdown("").classes("w-full text-sm")
        run_trend_info = ui.label(
            "Secili metrik icin senaryolar arasi zaman icindeki iyilesme/kotulesme trendi."
        ).classes("text-sm text-slate-600")
        run_trend_metric_select = ui.select(
            options={
                "total_energy": "Total Energy",
                "annual_heating": "Annual Heating",
                "annual_cooling": "Annual Cooling",
                "annual_cost": "Annual Cost",
                "peak_heating": "Peak Heating",
                "peak_cooling": "Peak Cooling",
            },
            value="total_energy",
            label="Trend Metrigi",
        ).classes("w-full")
        run_trend_chart = ui.echart(
            {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["Deger", "Adim Degisimi"], "top": 8},
                "xAxis": {"type": "category", "data": []},
                "yAxis": [
                    {"type": "value", "name": "Deger"},
                    {"type": "value", "name": "Delta", "position": "right"},
                ],
                "series": [
                    {
                        "name": "Deger",
                        "type": "line",
                        "smooth": True,
                        "data": [],
                        "lineStyle": {"color": "#1f2937", "width": 3},
                        "itemStyle": {"color": "#1f2937"},
                    },
                    {
                        "name": "Adim Degisimi",
                        "type": "bar",
                        "yAxisIndex": 1,
                        "data": [],
                        "itemStyle": {"color": "#0f766e"},
                    },
                ],
            }
        ).classes("w-full h-72")
        with ui.card().classes("w-full dashboard-panel bg-sky-50 border border-sky-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("monitoring").classes("text-sky-800")
                ui.label("Gercek Simulasyon Sonucu").classes("text-sm font-medium text-sky-900")
            real_output_actions = build_card_action_row("comparison report")
            real_output_status = ui.markdown("").classes("w-full text-sm")
            real_output_commentary = ui.markdown("").classes("w-full text-sm")
            real_output_info = ui.label(
                "Bu grafik secili senaryonun gercek old/new ciktilarini tek cizgide toplar."
            ).classes("text-sm text-slate-700")
            real_output_chart = ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["Base Scenario", "Updated Scenario"], "top": 8},
                    "grid": {
                        "left": "3%",
                        "right": "4%",
                        "bottom": "14%",
                        "containLabel": True,
                    },
                    "xAxis": {
                        "type": "category",
                        "data": [],
                        "axisLabel": {"interval": 0, "rotate": 25},
                    },
                    "yAxis": {"type": "value", "name": "Normalized Output"},
                    "series": [
                        {
                            "name": "Base Scenario",
                            "type": "line",
                            "smooth": True,
                            "data": [],
                            "lineStyle": {"color": "#1f2937", "width": 3, "type": "solid"},
                            "itemStyle": {"color": "#1f2937"},
                        },
                        {
                            "name": "Updated Scenario",
                            "type": "line",
                            "smooth": True,
                            "data": [],
                            "lineStyle": {"color": "#0f766e", "width": 3, "type": "dashed"},
                            "itemStyle": {"color": "#0f766e"},
                        },
                    ],
                }
            ).classes("w-full h-80")
            ui.label("Delta Ozeti").classes("text-xs font-medium text-sky-900")
            real_output_delta_chart = ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "grid": {
                        "left": "3%",
                        "right": "4%",
                        "bottom": "14%",
                        "containLabel": True,
                    },
                    "xAxis": {
                        "type": "category",
                        "data": [],
                        "axisLabel": {"interval": 0, "rotate": 25},
                    },
                    "yAxis": {"type": "value", "name": "Yeni - Eski"},
                    "series": [
                        {
                            "name": "Delta",
                            "type": "bar",
                            "data": [],
                            "itemStyle": {"color": "#0f766e"},
                        }
                    ],
                }
            ).classes("w-full h-64")
        with ui.card().classes("w-full dashboard-panel bg-orange-50 border border-orange-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("calendar_view_month").classes("text-orange-800")
                ui.label("Aylik Enerji Overlay").classes("text-sm font-medium text-orange-900")
            monthly_actions = build_card_action_row("comparison report / monthly_heating_cooling")
            monthly_energy_status = ui.markdown("").classes("w-full text-sm")
            monthly_energy_commentary = ui.markdown("").classes("w-full text-sm")
            monthly_energy_info = ui.label(
                "Aylik etkiler small-multiples olarak iki ayri panelde gosterilir: Heating ve Cooling."
            ).classes("text-sm text-slate-700")
            with ui.row().classes("w-full gap-4 items-stretch"):
                monthly_heating_chart = ui.echart(
                    {
                        "tooltip": {
                            "trigger": "axis",
                            "formatter": monthly_tooltip_formatter,
                        },
                        "legend": {"data": [], "top": 8},
                        "title": {"text": "Monthly Heating", "left": "center", "textStyle": {"fontSize": 12}},
                        "xAxis": {"type": "category", "data": monthly_labels_tr},
                        "yAxis": {"type": "value", "name": "kWh"},
                        "series": [],
                    }
                ).classes("w-full h-72")
                monthly_cooling_chart = ui.echart(
                    {
                        "tooltip": {
                            "trigger": "axis",
                            "formatter": monthly_tooltip_formatter,
                        },
                        "legend": {"data": [], "top": 8},
                        "title": {"text": "Monthly Cooling", "left": "center", "textStyle": {"fontSize": 12}},
                        "xAxis": {"type": "category", "data": monthly_labels_tr},
                        "yAxis": {"type": "value", "name": "kWh"},
                        "series": [],
                    }
                ).classes("w-full h-72")
        with ui.card().classes("w-full dashboard-panel bg-cyan-50 border border-cyan-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("device_thermostat").classes("text-cyan-800")
                ui.label("Zone Sicaklik Overlay").classes("text-sm font-medium text-cyan-900")
            zone_temperature_actions = build_card_action_row("comparison report / zone_temperatures")
            zone_temperature_status = ui.markdown("").classes("w-full text-sm")
            zone_temperature_commentary = ui.markdown("").classes("w-full text-sm")
            zone_temperature_info = ui.label(
                "Bu grafik secilen zone icin degisiklik oncesi ve sonrasi sicaklik egirilerini ayni overlay grafikte gosterir."
            ).classes("text-sm text-slate-700")
            zone_temperature_select = ui.select(
                options=[],
                label="Zone Secimi",
            ).classes("w-full dashboard-input")
            zone_temperature_chart = ui.echart(
                {
                    "tooltip": {
                        "trigger": "axis",
                        "formatter": zone_tooltip_formatter,
                    },
                    "legend": {"data": ["Base Scenario", "Updated Scenario"], "top": 8},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "C"},
                    "series": [
                        {
                            "name": "Base Scenario",
                            "type": "line",
                            "smooth": True,
                            "data": [],
                            "lineStyle": {"color": "#1f2937", "width": 3},
                            "itemStyle": {"color": "#94a3b8"},
                            "markArea": {
                                "silent": True,
                                "itemStyle": {"color": "rgba(16,185,129,0.12)"},
                                "data": [
                                    [
                                        {"yAxis": comfort_band_min_c},
                                        {"yAxis": comfort_band_max_c},
                                    ]
                                ],
                            },
                        },
                        {
                            "name": "Scenario",
                            "type": "line",
                            "smooth": True,
                            "data": [],
                            "lineStyle": {"color": "#0f766e"},
                            "itemStyle": {"color": "#0f766e"},
                        },
                    ],
                }
            ).classes("w-full h-80")
        with ui.card().classes("w-full dashboard-panel bg-violet-50 border border-violet-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("grid_view").classes("text-violet-800")
                ui.label("Zone Heatmap").classes("text-sm font-medium text-violet-900")
            zone_heatmap_actions = build_card_action_row("zone portfolio / comparison report")
            zone_heatmap_status = ui.markdown("").classes("w-full text-sm")
            zone_heatmap_commentary = ui.markdown("").classes("w-full text-sm")
            zone_heatmap_metric_select = ui.select(
                options={
                    "temperature_vs_comfort": "Sicaklik vs Konfor",
                    "overheat_vs_cold": "Asiri Sicak vs Asiri Soguk",
                    "stability_vs_peak": "Stabilite vs Tepe Sicaklik",
                },
                value="temperature_vs_comfort",
                label="Heatmap metrik cifti",
            ).classes("w-full max-w-sm dashboard-input")
            zone_heatmap_info = ui.label(
                "Zone bazinda sicaklik sapmasi ve konfor saatleri isi haritasi."
            ).classes("text-sm text-slate-700")
            zone_heatmap_chart = ui.echart(
                {
                    "tooltip": {"trigger": "item"},
                    "grid": {"left": 90, "right": 18, "top": 20, "bottom": 36},
                    "xAxis": {"type": "category", "data": [], "axisLabel": {"interval": 0, "rotate": 20}},
                    "yAxis": {"type": "category", "data": ["Avg Delta (C)", "Comfort Hours"]},
                    "visualMap": {
                        "min": 0,
                        "max": 100,
                        "calculable": True,
                        "orient": "horizontal",
                        "left": "center",
                        "bottom": 0,
                        "inRange": {"color": ["#eff6ff", "#93c5fd", "#1d4ed8"]},
                    },
                    "series": [
                        {
                            "name": "Zone Heatmap",
                            "type": "heatmap",
                            "data": [],
                            "label": {"show": True, "formatter": "{c}"},
                            "emphasis": {"itemStyle": {"shadowBlur": 6, "shadowColor": "rgba(0, 0, 0, 0.35)"}},
                        }
                    ],
                }
            ).classes("w-full h-72")
        with ui.card().classes("w-full dashboard-panel bg-fuchsia-50 border border-fuchsia-100"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("insights").classes("text-fuchsia-800")
                ui.label("Advanced Analysis").classes("text-sm font-medium text-fuchsia-900")
            advanced_actions = build_card_action_row("peak + zone + seasonal derived metrics")
            advanced_analysis_status = ui.markdown("").classes("w-full text-sm")
            advanced_analysis_commentary = ui.markdown("").classes("w-full text-sm")
            advanced_analysis_info = ui.label(
                "Zone bazli, peak load, konfor ve sezon ozeti bu alanda gosterilir."
            ).classes("text-sm text-slate-700")
            advanced_analysis_markdown = ui.markdown("").classes("w-full text-sm")
        with ui.row().classes("w-full gap-4"):
            overlay_scenarios_select = ui.select(
                options=[],
                value=[],
                label="Overlay senaryolari",
                multiple=True,
            ).classes("w-full dashboard-input")
        ui.label(
            "Overlay grafikler ayni anda 1 base cizgisi ve en fazla 3 ek senaryo cizgisi gosterir."
        ).classes("text-xs text-slate-600")
        with ui.row().classes("w-full gap-4"):
            comparison_left = ui.select(options=[], label="Sol senaryo").classes("w-full dashboard-input")
            comparison_right = ui.select(options=[], label="Sag senaryo").classes("w-full dashboard-input")
        ui.label(
            "Bu panel ne degisti, etkisi ne oldu ve en dikkat cekici fark ne sorularini kisa yorumlarla ozetler."
        ).classes("text-xs text-slate-600")
        comparison_markdown = ui.markdown("").classes("w-full text-sm")

    return {
        "analytics_info": analytics_info,
        "analysis_scenario_select": analysis_scenario_select,
        "refresh_all_button": refresh_all_button,
        "last_refresh_label": last_refresh_label,
        "analysis_data_status": analysis_data_status,
        "analysis_status_badge": analysis_status_badge,
        "analysis_workflow_markdown": analysis_workflow_markdown,
        "changes_chart": changes_chart,
        "flow_chart": flow_chart,
        "expected_effect_info": expected_effect_info,
        "energy_performance_info": energy_performance_info,
        "energy_performance_status": energy_performance_status,
        "energy_performance_commentary": energy_performance_commentary,
        "energy_actions": energy_actions,
        "analytics_missing_metrics": analytics_missing_metrics,
        "energy_performance_chart": energy_performance_chart,
        "run_trend_info": run_trend_info,
        "run_trend_status": run_trend_status,
        "run_trend_commentary": run_trend_commentary,
        "run_trend_actions": run_trend_actions,
        "run_trend_metric_select": run_trend_metric_select,
        "run_trend_chart": run_trend_chart,
        "real_output_info": real_output_info,
        "real_output_status": real_output_status,
        "real_output_commentary": real_output_commentary,
        "real_output_actions": real_output_actions,
        "real_output_chart": real_output_chart,
        "real_output_delta_chart": real_output_delta_chart,
        "monthly_energy_info": monthly_energy_info,
        "monthly_energy_status": monthly_energy_status,
        "monthly_energy_commentary": monthly_energy_commentary,
        "monthly_actions": monthly_actions,
        "monthly_heating_chart": monthly_heating_chart,
        "monthly_cooling_chart": monthly_cooling_chart,
        "zone_temperature_info": zone_temperature_info,
        "zone_temperature_status": zone_temperature_status,
        "zone_temperature_commentary": zone_temperature_commentary,
        "zone_temperature_actions": zone_temperature_actions,
        "zone_temperature_select": zone_temperature_select,
        "zone_temperature_chart": zone_temperature_chart,
        "zone_heatmap_metric_select": zone_heatmap_metric_select,
        "zone_heatmap_info": zone_heatmap_info,
        "zone_heatmap_status": zone_heatmap_status,
        "zone_heatmap_commentary": zone_heatmap_commentary,
        "zone_heatmap_actions": zone_heatmap_actions,
        "zone_heatmap_chart": zone_heatmap_chart,
        "advanced_analysis_info": advanced_analysis_info,
        "advanced_analysis_status": advanced_analysis_status,
        "advanced_analysis_commentary": advanced_analysis_commentary,
        "advanced_actions": advanced_actions,
        "advanced_analysis_markdown": advanced_analysis_markdown,
        "overlay_scenarios_select": overlay_scenarios_select,
        "comparison_left": comparison_left,
        "comparison_right": comparison_right,
        "comparison_markdown": comparison_markdown,
    }
