"""Proje sonuc raporunun sekillerini uretilmis rapor dosyalarindan cizer.

Hicbir sayi elle yazilmaz; hepsi data/ altindaki JSON raporlarindan okunur.
Boylece analiz yeniden kosuldugunda sekiller de guncellenir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
SURROGATE_REPORT = ROOT / "data/surrogate/surrogate_report.json"
ISO_REPORT = ROOT / "data/iso50001/iso50001_report.json"
PARETO_FRONT = ROOT / "data/optimization/pareto_front.json"
VALIDATION_REPORT = ROOT / "data/validation/validation_report.json"

# Rapor Arial 11 punto ile yazilir; sekil yazilari en kucuk 10 punto olmalidir.
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 10,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.dpi": 200,
        "savefig.bbox": "tight",
    }
)

INK = "#1b1f2a"
ACCENT = "#2f5d9e"
MUTED = "#9aa3b2"
WARN = "#c0562f"

# Veri dosyalarindaki etiketler ASCII'dir (kod icinde Turkce karakter tutulmaz).
# Rapor sekillerinde tam Turkce yazim gerekir.
DISPLAY_LABELS = {
    "Chiller COP": "Chiller COP",
    "Sogutma ayar noktasi": "Soğutma ayar noktası",
    "Cam tipi": "Cam tipi",
    "Aydinlatma - ofis, salon, atolye": "Aydınlatma – ofis, salon, atölye",
    "Isitma ayar noktasi": "Isıtma ayar noktası",
    "Aydinlatma - koridor, merdiven, WC": "Aydınlatma – koridor, merdiven, WC",
    "Asansor motoru gucu": "Asansör motoru gücü",
    "Kazan verimi": "Kazan verimi",
    "EPS isil iletkenligi": "EPS ısıl iletkenliği",
    "Sizdirmazlik carpani": "Sızdırmazlık çarpanı",
    "EPS kalinligi": "EPS kalınlığı",
    "Sogutma": "Soğutma",
    "Ic ekipman": "İç ekipman",
    "Fanlar": "Fanlar",
    "Ic aydinlatma": "İç aydınlatma",
    "Isitma": "Isıtma",
    "Pompalar": "Pompalar",
}


def label_of(raw: str) -> str:
    return DISPLAY_LABELS.get(raw, raw)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tr(value: float, digits: int = 2) -> str:
    """Turkce sayi bicimi: binlik nokta, ondalik virgul."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def sensitivity_figure(destination: Path) -> Path:
    """Sekil 4.1 - Sobol birinci mertebe ve toplam etki indisleri."""
    indices = _load(SURROGATE_REPORT)["sensitivity"]["indices"]
    rows = sorted(indices, key=lambda item: item["total"])
    labels = [label_of(item["label"]) for item in rows]
    first = [item["first_order"] for item in rows]
    total = [item["total"] for item in rows]

    positions = range(len(rows))
    height = 0.38
    figure, axes = plt.subplots(figsize=(6.3, 4.4))
    axes.barh(
        [p + height / 2 for p in positions], total, height=height,
        color=MUTED, label="Toplam etki (S$_T$)",
    )
    axes.barh(
        [p - height / 2 for p in positions], first, height=height,
        color=ACCENT, label="Birinci mertebe (S$_1$)",
    )
    axes.set_yticks(list(positions))
    axes.set_yticklabels(labels)
    axes.set_xlabel("Sobol duyarlılık indisi [–]")
    axes.legend(loc="lower right", frameon=False)
    axes.spines[["top", "right"]].set_visible(False)
    axes.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr(v, 2)))

    # En dusuk siradaki degisken tezin baslangic hipotezidir; isaretlenir.
    axes.annotate(
        "başlangıç hipotezinin değişkeni",
        xy=(rows[0]["total"], 0),
        xytext=(0.18, 1.6),
        color=WARN,
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 0.9},
    )
    figure.savefig(destination)
    plt.close(figure)
    return destination


def seu_figure(destination: Path) -> Path:
    """Sekil 4.2 - Onemli enerji kullanimlari ve kumulatif %80 esigi."""
    seu = _load(ISO_REPORT)["significant_energy_uses"]
    uses = seu["uses"]
    labels = [label_of(item["label"]) for item in uses]
    energy = [item["energy_gj"] for item in uses]
    cumulative = [item["cumulative_percent"] for item in uses]
    significant = [item["significant"] for item in uses]

    figure, axes = plt.subplots(figsize=(6.3, 3.6))
    colors = [ACCENT if flag else MUTED for flag in significant]
    axes.bar(labels, energy, color=colors)
    axes.set_ylabel("Yıllık enerji [GJ]")
    axes.tick_params(axis="x", rotation=20)
    for label in axes.get_xticklabels():
        label.set_horizontalalignment("right")
    axes.spines[["top", "right"]].set_visible(False)
    axes.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr(v, 0)))

    twin = axes.twinx()
    twin.plot(labels, cumulative, color=INK, marker="o", markersize=4, linewidth=1.2)
    twin.axhline(seu["threshold_percent"], color=WARN, linestyle="--", linewidth=1.0)
    twin.set_ylabel("Kümülatif pay [%]")
    twin.set_ylim(0, 105)
    twin.spines[["top"]].set_visible(False)
    twin.annotate(
        f"%{_tr(seu['threshold_percent'], 0)} eşiği",
        xy=(len(labels) - 1, seu["threshold_percent"]),
        xytext=(len(labels) - 1.9, seu["threshold_percent"] - 17),
        color=WARN,
    )
    figure.savefig(destination)
    plt.close(figure)
    return destination


def pareto_figure(destination: Path) -> Path:
    """Sekil 4.3 - Pareto cephesi ve hipervolum yakinsamasi."""
    front = _load(PARETO_FRONT)
    labels = front["objective_labels"]
    solutions = front["solutions"]
    enpi = [item["objectives"][labels[0]] for item in solutions]
    cost = [item["objectives"][labels[1]] / 1e6 for item in solutions]
    comfort = [item["objectives"][labels[2]] for item in solutions]

    figure, (left, right) = plt.subplots(
        1, 2, figsize=(6.9, 3.1), gridspec_kw={"wspace": 0.62}
    )
    scatter = left.scatter(
        enpi, cost, c=comfort, cmap="viridis_r", s=22, edgecolor="white", linewidth=0.3
    )
    left.set_xlabel("EnPİ [kWh/m$^2$·yıl]")
    left.set_ylabel("Yatırım maliyeti [milyon TL]")
    left.spines[["top", "right"]].set_visible(False)
    left.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr(v, 0)))
    left.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr(v, 1)))
    bar = figure.colorbar(scatter, ax=left, pad=0.03, fraction=0.05)
    bar.set_label("Konfor ihlali [bölge·saat]", fontsize=9)
    bar.ax.tick_params(labelsize=8)

    convergence = front["convergence"]
    right.plot(
        [item["generation"] for item in convergence],
        [item["hypervolume"] for item in convergence],
        color=ACCENT,
        linewidth=1.4,
    )
    right.set_xlabel("Nesil")
    right.set_ylabel("Hipervolüm [–]")
    right.spines[["top", "right"]].set_visible(False)
    right.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr(v, 2)))
    figure.savefig(destination)
    plt.close(figure)
    return destination


def validation_figure(destination: Path) -> Path:
    """Sekil 4.4 - Vekil model tahmini ile EnergyPlus sonucunun sapmasi."""
    report = _load(VALIDATION_REPORT)
    points = sorted(report["points"], key=lambda item: item["deviation_percent"])
    labels = [item["case_id"].replace("case_", "") for item in points]
    deviations = [item["deviation_percent"] for item in points]
    tolerance = report["summary"]["tolerance_percent"]

    figure, axes = plt.subplots(figsize=(6.3, 3.2))
    colors = [ACCENT if value >= 0 else WARN for value in deviations]
    axes.bar(labels, deviations, color=colors)
    axes.axhline(tolerance, color=INK, linestyle="--", linewidth=1.0)
    axes.axhline(-tolerance, color=INK, linestyle="--", linewidth=1.0)
    axes.axhline(0, color=INK, linewidth=0.8)
    axes.set_ylabel("Sapma [%]")
    axes.set_xlabel("Doğrulama noktası (case_id)")
    axes.tick_params(axis="x", rotation=45)
    for label in axes.get_xticklabels():
        label.set_horizontalalignment("right")
    axes.set_ylim(-tolerance * 1.5, tolerance * 1.5)
    axes.spines[["top", "right"]].set_visible(False)
    axes.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _tr(v, 0)))
    axes.annotate(
        f"tolerans ± %{_tr(tolerance, 0)}",
        xy=(len(labels) - 1, tolerance),
        xytext=(len(labels) - 3.4, tolerance + 0.6),
        fontsize=9,
    )
    figure.savefig(destination)
    plt.close(figure)
    return destination


FIGURES = {
    "sekil_4_1_duyarlilik.png": sensitivity_figure,
    "sekil_4_2_seu.png": seu_figure,
    "sekil_4_3_pareto.png": pareto_figure,
    "sekil_4_4_dogrulama.png": validation_figure,
}


def build_all(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return [builder(output_dir / name) for name, builder in FIGURES.items()]


if __name__ == "__main__":
    for path in build_all(ROOT / "data/rapor/sekiller"):
        print("uretildi:", path)


def architecture_figure(destination: Path) -> Path:
    """Sekil 3.1 - yazilim aracinin katmanli mimarisi."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    layers = [
        ("Kullanici arayuzu", "NiceGUI", "Gorsellestirme ve etkilesim", ACCENT),
        ("Uygulama arayuzu", "FastAPI", "Model kimligi, dogrulama", "#4a7fb5"),
        ("Servis katmani", "OpenStudio SDK", "Model okuma, is akisi uretimi", "#6f9a63"),
        ("Simulasyon", "EnergyPlus", "Yillik enerji hesabi", "#b08a3e"),
        ("Analiz", "scikit-learn / pymoo", "Vekil model ve optimizasyon", "#8d6a9f"),
    ]
    display = {
        "Kullanici arayuzu": "Kullanıcı arayüzü",
        "Uygulama arayuzu": "Uygulama arayüzü",
        "Servis katmani": "Servis katmanı",
        "Simulasyon": "Simülasyon",
        "Analiz": "Analiz",
        "Gorsellestirme ve etkilesim": "Görselleştirme ve etkileşim",
        "Model kimligi, dogrulama": "Model kimliği, doğrulama",
        "Model okuma, is akisi uretimi": "Model okuma, iş akışı üretimi",
        "Yillik enerji hesabi": "Yıllık enerji hesabı",
        "Vekil model ve optimizasyon": "Vekil model ve optimizasyon",
    }

    figure, axes = plt.subplots(figsize=(6.4, 4.6))
    axes.set_xlim(0, 10)
    axes.set_ylim(0, len(layers) * 1.5 + 0.4)
    axes.axis("off")

    for index, (name, tech, role, color) in enumerate(reversed(layers)):
        y = index * 1.5 + 0.4
        axes.add_patch(
            FancyBboxPatch(
                (0.6, y), 8.8, 1.05,
                boxstyle="round,pad=0.04,rounding_size=0.12",
                linewidth=1.1, edgecolor=color, facecolor=color + "1a",
            )
        )
        axes.text(1.0, y + 0.68, display.get(name, name), fontsize=10,
                  fontweight="bold", color=INK, va="center")
        axes.text(1.0, y + 0.30, display.get(role, role), fontsize=8.5,
                  color="#5b6472", va="center")
        axes.text(9.0, y + 0.52, tech, fontsize=9, color=color,
                  va="center", ha="right", fontweight="bold")
        if index < len(layers) - 1:
            axes.add_patch(
                FancyArrowPatch(
                    (5.0, y + 1.12), (5.0, y + 1.42),
                    arrowstyle="-|>", mutation_scale=11,
                    linewidth=1.0, color=MUTED,
                )
            )
    figure.savefig(destination)
    plt.close(figure)
    return destination


FIGURES["sekil_3_1_mimari.png"] = architecture_figure
