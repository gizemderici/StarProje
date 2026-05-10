from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayMetricRule:
    metric_id: str
    label: str
    suitable_for_overlay_line: bool
    reason: str
    preferred_visual: str


OVERLAY_METRIC_RULES: tuple[OverlayMetricRule, ...] = (
    OverlayMetricRule(
        metric_id="monthly_heating",
        label="Monthly Heating",
        suitable_for_overlay_line=True,
        reason="Aylik sirali zaman serisidir; eski-yeni farki ay bazinda trend olarak izlenir.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="monthly_cooling",
        label="Monthly Cooling",
        suitable_for_overlay_line=True,
        reason="Aylik sirali zaman serisidir; mevsimsel sogutma davranisini iki seriyle karsilastirir.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="zone_temperatures",
        label="Zone Temperature",
        suitable_for_overlay_line=True,
        reason="Zone bazli saatlik/zamansal sicaklik noktalarindan olusur; iki cizgi yorumlamayi kolaylastirir.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="selected_zone_operative_temperature",
        label="Selected Zone Operative Temperature",
        suitable_for_overlay_line=True,
        reason="Secilen zone icin surekli seri verir; konfor bandi ile birlikte overlay cizgi en uygun gosterimdir.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="surface_temperature",
        label="Surface Temperature",
        suitable_for_overlay_line=True,
        reason="Yuzey sicakligi zaman ekseninde degisir; degisiklik oncesi/sonrasi profil farki cizgi ile gorulur.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="hourly_temperature_profile",
        label="Hourly Temperature Data",
        suitable_for_overlay_line=True,
        reason="Saatlik profil dogrudan sirali seri oldugu icin overlay line chart ile acik sekilde karsilastirilir.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="daily_temperature_profile",
        label="Daily Temperature Data",
        suitable_for_overlay_line=True,
        reason="Gunluk seri zaman boyutludur; oncesi-sonrasi dagilim trend olarak okunur.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="unmet_hours_trend",
        label="Unmet Hours Trend",
        suitable_for_overlay_line=True,
        reason="Unmet hours zaman dilimlerine dagitilmis ise trend cizgisi ile degisim gorulur.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="total_energy_trend",
        label="Total Energy Trend",
        suitable_for_overlay_line=True,
        reason="Toplam enerji sadece tek sayi degil de periyot bazli trend ise overlay line uygundur.",
        preferred_visual="overlay_line",
    ),
    OverlayMetricRule(
        metric_id="annual_heating",
        label="Annual Heating",
        suitable_for_overlay_line=False,
        reason="Tek yillik KPI degeridir; zaman serisi olmadigi icin line overlay anlamsizdir.",
        preferred_visual="kpi_or_bar",
    ),
    OverlayMetricRule(
        metric_id="annual_cooling",
        label="Annual Cooling",
        suitable_for_overlay_line=False,
        reason="Tek yillik KPI degeridir; bar/KPI kutusu daha okunaklidir.",
        preferred_visual="kpi_or_bar",
    ),
    OverlayMetricRule(
        metric_id="total_annual_cost",
        label="Total Annual Cost",
        suitable_for_overlay_line=False,
        reason="Tekil finansal ozet degerdir; line yerine KPI ve fark karti tercih edilir.",
        preferred_visual="kpi_or_bar",
    ),
)


def get_overlay_metric_rules() -> tuple[OverlayMetricRule, ...]:
    return OVERLAY_METRIC_RULES


def get_overlay_suitable_metrics() -> list[OverlayMetricRule]:
    return [rule for rule in OVERLAY_METRIC_RULES if rule.suitable_for_overlay_line]


def get_overlay_unsuitable_metrics() -> list[OverlayMetricRule]:
    return [rule for rule in OVERLAY_METRIC_RULES if not rule.suitable_for_overlay_line]


def build_overlay_metric_catalog_markdown() -> str:
    suitable_lines = [
        f"- {rule.label} (`{rule.metric_id}`): {rule.reason}"
        for rule in get_overlay_suitable_metrics()
    ]
    unsuitable_lines = [
        f"- {rule.label} (`{rule.metric_id}`): {rule.reason}"
        for rule in get_overlay_unsuitable_metrics()
    ]

    return "\n".join(
        [
            "# EPIC 13.1 Overlay Grafik Metrik Siniflandirma",
            "",
            "## Overlay Line Chart Icin Uygun",
            *suitable_lines,
            "",
            "## Overlay Icin Uygun Olmayanlar",
            *unsuitable_lines,
        ]
    )
