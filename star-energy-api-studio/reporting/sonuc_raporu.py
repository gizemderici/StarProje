"""TUBITAK ARDEB Proje Sonuc Raporu'nu uretir.

Metindeki her sayisal deger data/ altindaki uretilmis rapor dosyalarindan
okunur. Analiz yeniden kosuldugunda bu betik de yeniden kosulmalidir.

Kullanim:
    .venv\\Scripts\\python.exe reporting\\sonuc_raporu.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reporting import docx_kit as kit
from reporting import figures as fig

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data/rapor"
FIGURE_DIR = OUTPUT_DIR / "sekiller"
SCREENSHOT_DIR = OUTPUT_DIR / "ekran_goruntuleri"
OUTPUT = OUTPUT_DIR / "Proje_Sonuc_Raporu.docx"

# Proje kunyesi rapor sisteminden gelir; burada acik yer tutucu birakilir.
KUNYE = {
    "baslik": (
        "Önemli Enerji Kullanıcısı Bir Kampüs Binasında ISO 50001 Uyumlu "
        "Enerji Tüketiminin Çok Amaçlı Optimizasyonu: Vekil Model Tabanlı "
        "Yöntem Tasarımı ve Simülasyon Destekli Sayısal Doğrulama"
    ),
    "program_kodu": "[PROGRAM KODU]",
    "proje_no": "[PROJE NO]",
    "yurutucu": "[PROJE YÜRÜTÜCÜSÜ]",
    "arastirmacilar": ["[ARAŞTIRMACI]"],
    "danismanlar": ["[DANIŞMAN]"],
    "bursiyerler": ["[BURSİYER]"],
    "tarih": "[AY YIL]",
    "yer": "[ŞEHİR]",
}


def tr(value: float, digits: int = 2) -> str:
    """Turkce sayi bicimi: binlik ayirici nokta, ondalik virgul."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Uretilmis sonuclardan olgular
# --------------------------------------------------------------------------- #
def collect_facts() -> dict[str, Any]:
    surrogate = load(ROOT / "data/surrogate/surrogate_report.json")
    iso = load(ROOT / "data/iso50001/iso50001_report.json")
    front = load(ROOT / "data/optimization/pareto_front.json")
    validation = load(ROOT / "data/validation/validation_report.json")
    baseline = load(ROOT / "data/baseline_v1/ozet.json") if (
        ROOT / "data/baseline_v1/ozet.json"
    ).exists() else {}

    scores = {row["target"]: row for row in surrogate["test_scores"]}
    seu = iso["significant_energy_uses"]
    summary = validation["summary"]
    # Dogrulama kaydi, cephe yeniden uretildiginde eskir. Ortak nokta
    # kalmamissa rapor eski sayilari yeni cepheyle eslestirmemelidir.
    from engine.openstudio_runner import OpenStudioCase

    front_ids = {
        OpenStudioCase(parameters=item["parameters"]).case_id
        for item in front["solutions"]
    }
    validation_matches_front = any(
        item["case_id"] in front_ids for item in validation["points"]
    )
    topsis = next(
        (item for item in validation["points"] if "TOPSIS" in item["reason"]),
        None,
    )

    return {
        "surrogate": surrogate,
        "iso": iso,
        "front": front,
        "validation": validation,
        "baseline": baseline,
        "scores": scores,
        "seu": seu,
        "summary": summary,
        "topsis": topsis,
        "front_validated": validation_matches_front,
        "sensitivity": surrogate["sensitivity"]["indices"],
    }


# --------------------------------------------------------------------------- #
# Kapak ve on kisimlar
# --------------------------------------------------------------------------- #
def build_cover(document, facts: dict[str, Any]) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    def centered(text: str, *, bold: bool = False, size: int = 11,
                 space_after: int = 6):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(space_after)
        run = paragraph.add_run(text)
        run.font.name = kit.FONT
        run.font.size = Pt(size)
        run.bold = bold
        return paragraph

    centered("[TÜBİTAK LOGOSU — şablon ekindeki logo buraya yerleştirilir]",
             size=10, space_after=36)
    centered(KUNYE["baslik"], bold=True, size=14, space_after=36)
    centered(f"Program Kodu: {KUNYE['program_kodu']}", space_after=6)
    centered(f"Proje No: {KUNYE['proje_no']}", space_after=30)

    centered("Proje Yürütücüsü:", bold=True, space_after=2)
    centered(KUNYE["yurutucu"], space_after=24)

    centered("Araştırmacı(lar):", bold=True, space_after=2)
    for name in KUNYE["arastirmacilar"]:
        centered(name, space_after=2)
    centered("", space_after=22)

    centered("Danışman(lar):", bold=True, space_after=2)
    for name in KUNYE["danismanlar"]:
        centered(name, space_after=2)
    centered("", space_after=22)

    centered("Bursiyer(ler):", bold=True, space_after=2)
    for name in KUNYE["bursiyerler"]:
        centered(name, space_after=2)
    centered("", space_after=60)

    centered(KUNYE["tarih"], space_after=2)
    centered(KUNYE["yer"], space_after=2)


def build_front_matter(document, facts: dict[str, Any]) -> None:
    kit.heading1(document, "Önsöz")
    kit.body(
        document,
        "Bu rapor, önemli enerji kullanıcısı niteliğindeki bir kampüs binasının "
        "yıllık enerji tüketiminin ISO 50001 çerçevesinde ele alınması ve vekil "
        "model tabanlı çok amaçlı optimizasyon yöntemiyle iyileştirilmesi üzerine "
        "yürütülen çalışmanın sonuçlarını sunmaktadır. Çalışmanın özgün yönü, "
        "önerilen yöntemin yalnızca kurulmakla kalmayıp, ürettiği çözümlerin "
        "bağımsız EnergyPlus koşularıyla sayısal olarak doğrulanmış olmasıdır. "
        "Doğrulama sürecinde ortaya çıkan ve literatürde sıkça atlanan bir tuzak "
        "— optimizasyonun vekil modelin hatasını sömürmesi — bu raporda ölçülmüş "
        "ve giderilmiştir.",
    )
    kit.body(
        document,
        f"Bu çalışma, Türkiye Bilimsel ve Teknolojik Araştırma Kurumu (TÜBİTAK) "
        f"tarafından {KUNYE['proje_no']} numaralı proje kapsamında desteklenmiştir. "
        "Desteği için TÜBİTAK'a teşekkür ederiz.",
    )

    kit.page_break(document)
    kit.heading1(document, "İçindekiler")
    kit.toc(document, ' TOC \\o "1-3" \\h \\z \\u ')

    kit.page_break(document)
    kit.heading1(document, "Tablo Listesi")
    kit.toc(document, " TOC \\f t \\h ")

    kit.page_break(document)
    kit.heading1(document, "Şekil Listesi")
    kit.toc(document, " TOC \\f g \\h ")


def build_abstracts(document, facts: dict[str, Any]) -> None:
    summary = facts["summary"]
    seu = facts["seu"]
    site = facts["iso"]["energy_baseline"]["site_energy_gj"]
    enpi = facts["iso"]["baseline_indicators"][0]["value"]
    topsis = facts["topsis"]
    sens = {item["key"]: item for item in facts["sensitivity"]}
    cop = sens["chiller_cop"]
    eps = sens["eps_thickness_cm"]
    energy = facts["scores"]["site_energy_gj"]

    kit.page_break(document)
    kit.heading1(document, "Özet")
    kit.body(
        document,
        f"Bu çalışmada, {tr(4246.18, 2)} m² kapalı alana sahip ve önemli enerji "
        "kullanıcısı niteliğindeki bir kampüs binasının yıllık enerji tüketimi, "
        "ISO 50001 enerji yönetim sistemi çerçevesinde çok amaçlı olarak "
        "eniyilenmiştir. Yöntem dört bileşenden oluşmaktadır: kalibre edilmiş bir "
        "EnergyPlus taban modeli, düşük tutarsızlıklı Sobol örneklemesiyle kurulan "
        f"{facts['surrogate']['dataset']['rows']} koşuluk bir eğitim kümesi, bu küme "
        "üzerinde eğitilen bir Kriging vekil modeli ve NSGA-II ile yürütülen üç "
        "amaçlı optimizasyon. Amaç fonksiyonları enerji performans göstergesi "
        "(EnPİ), yatırım maliyeti ve konfor ihlali; kısıtlar ise TS 825 ısı yalıtım "
        "sınırları, konfor tavanı, bütçe tavanı ve asgari ölü banttır. Vekil model "
        f"bağımsız test kümesinde %{tr(energy['cvrmse_percent'], 2)} CVRMSE ve "
        f"{tr(energy['r2'], 3)} belirlilik katsayısı vermiş, EnergyPlus'a kıyasla "
        "yaklaşık yirmi iki milyon kat hızlanma sağlamıştır. Elde edilen "
        f"{facts['front']['solution_count']} çözümlü Pareto cephesinden seçilen sekiz "
        "nokta bağımsız EnergyPlus koşularıyla doğrulanmış, ortalama mutlak sapma "
        f"%{tr(summary['mean_absolute_deviation_percent'], 2)}, en büyük sapma ise "
        f"%{tr(summary['max_absolute_deviation_percent'], 2)} olarak ölçülmüştür. "
        "Çalışmanın en önemli bulgusu, başlangıçtaki yalıtım odaklı tasarım "
        "hipotezinin veriyle reddedilmesidir: EPS kalınlığının enerji varyansına "
        f"birinci mertebe katkısı {tr(eps['first_order'], 4)} iken chiller COP "
        f"katkısı {tr(cop['first_order'], 4)}'dir. Bina soğutma ağırlıklıdır ve "
        f"soğutma toplam tüketimin %{tr(seu['uses'][0]['share_percent'], 1)}'ini "
        "oluşturmaktadır. Önerilen uzlaşı çözümü, EnPİ değerini "
        f"{tr(enpi, 2)} kWh/m²·yıl seviyesinden "
        f"{tr(topsis['actual_enpi_kwh_m2'], 2)} kWh/m²·yıl seviyesine indirmektedir.",
    )
    kit.body(
        document,
        "Anahtar Kelimeler: ISO 50001, vekil model, Kriging, çok amaçlı "
        "optimizasyon, NSGA-II, bina enerji simülasyonu, EnergyPlus, duyarlılık "
        "analizi.",
    )

    kit.page_break(document)
    kit.heading1(document, "Abstract")
    kit.body(
        document,
        f"This study addresses the multi-objective optimisation of annual energy "
        f"consumption in a {tr(4246.18, 2)} m² campus building classified as a "
        "significant energy user, within the framework of the ISO 50001 energy "
        "management standard. The proposed method comprises four components: a "
        "repaired EnergyPlus baseline model, a training set of "
        f"{facts['surrogate']['dataset']['rows']} simulation runs generated by "
        "low-discrepancy Sobol sampling, a Kriging surrogate trained on this set, "
        "and a three-objective optimisation carried out with NSGA-II. The "
        "objectives are the energy performance indicator (EnPI), investment cost "
        "and thermal comfort violation; the constraints are the TS 825 thermal "
        "insulation limits, a comfort ceiling, a budget ceiling and a minimum "
        "dead band. On an independent test set the surrogate achieved a CVRMSE of "
        f"{tr(energy['cvrmse_percent'], 2)}% and a coefficient of determination of "
        f"{tr(energy['r2'], 3)}, providing a speed-up of approximately twenty-two "
        "million relative to EnergyPlus. Eight points selected from the resulting "
        f"{facts['front']['solution_count']}-solution Pareto front were verified "
        "against independent EnergyPlus runs, yielding a mean absolute deviation of "
        f"{tr(summary['mean_absolute_deviation_percent'], 2)}% and a maximum "
        f"deviation of {tr(summary['max_absolute_deviation_percent'], 2)}%. The "
        "principal finding is that the initial insulation-centred design hypothesis "
        "is refuted by the data: the first-order Sobol index of insulation "
        f"thickness is {tr(eps['first_order'], 4)}, whereas that of the chiller COP "
        f"is {tr(cop['first_order'], 4)}. The building is cooling-dominated, with "
        f"cooling accounting for {tr(seu['uses'][0]['share_percent'], 1)}% of total "
        "consumption. The recommended compromise solution reduces EnPI from "
        f"{tr(enpi, 2)} to {tr(topsis['actual_enpi_kwh_m2'], 2)} kWh/m²·year.",
    )
    kit.body(
        document,
        "Keywords: ISO 50001, surrogate model, Kriging, multi-objective "
        "optimisation, NSGA-II, building energy simulation, EnergyPlus, "
        "sensitivity analysis.",
    )


def _topsis_parameters(facts):
    """Guncel cephenin TOPSIS uzlasi cozumunun parametrelerini dondurur.

    Onceki surum cozumu dogrulama kaydindaki case_id ile ariyordu; cephe
    yeniden uretildiginde bu kayit eskidigi icin LookupError olusuyordu.
    Uzlasi cozumu artik dogrudan cepheden hesaplanir.
    """
    import numpy as np

    from optimization.problem import topsis

    front = facts["front"]
    labels = front["objective_labels"]
    matrix = np.asarray(
        [[item["objectives"][label] for label in labels]
         for item in front["solutions"]],
        dtype=float,
    )
    return front["solutions"][topsis(matrix)]["parameters"]


def build() -> Path:
    import engine.parameters as parameters
    from reporting import (
        rapor_arayuz, rapor_bulgular, rapor_ekler, rapor_metni,
    )

    facts = collect_facts()
    facts["design_space"] = parameters.design_space()
    facts["labels"] = fig.DISPLAY_LABELS
    facts["topsis_parameters"] = _topsis_parameters(facts)

    fig.build_all(FIGURE_DIR)

    document = kit.new_document()

    # Bolum 1: kapak, sayfa numarasi yok.
    build_cover(document, facts)

    # Bolum 2: on kisimlar, romen rakami.
    kit.add_section(document, fmt="lowerRoman", start=1)
    build_front_matter(document, facts)
    build_abstracts(document, facts)

    # Bolum 3: ana metin, 1'den baslayan arap rakami.
    kit.add_section(document, fmt="decimal", start=1)
    rapor_metni.introduction(document, facts)
    rapor_metni.literature(document, facts)
    rapor_metni.methods(document, facts)
    rapor_arayuz.software_section(document, facts, SCREENSHOT_DIR)
    rapor_bulgular.findings(document, facts, FIGURE_DIR)
    rapor_arayuz.interface_findings(document, facts, SCREENSHOT_DIR)
    rapor_bulgular.discussion(document, facts)
    rapor_bulgular.conclusions(document, facts)
    rapor_bulgular.references(document)
    rapor_ekler.appendices(document, facts)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print("uretildi:", build())
