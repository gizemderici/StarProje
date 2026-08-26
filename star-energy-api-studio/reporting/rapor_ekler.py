"""Proje Sonuc Raporu: Ekler."""

from __future__ import annotations

from typing import Any

from reporting import docx_kit as kit
from reporting.figures import label_of


def tr(value: float, digits: int = 2) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def appendices(document, facts: dict[str, Any]) -> None:
    kit.heading1(document, "Ekler")

    kit.heading2(document, "Ek A. Önerilen Uzlaşı Çözümünün Parametreleri")
    kit.body(
        document,
        "Bölüm 4.6'da doğrulanan TOPSIS uzlaşı çözümünün karar değişkeni değerleri "
        "Tablo A.1'de verilmiştir. Değerler taban çizgisiyle birlikte sunulmuştur.",
    )
    kit.table_caption(
        document,
        "Tablo A.1. Önerilen uzlaşı çözümünün karar değişkeni değerleri",
    )
    baseline = facts["front"]["baseline_parameters"]
    proposed = facts["topsis_parameters"]
    label_by_key = {
        item["key"]: label_of(item["label"]) for item in facts["design_space"]
    }
    rows = []
    for key, base_value in baseline.items():
        new_value = proposed.get(key, base_value)
        if isinstance(base_value, str):
            rows.append([label_by_key.get(key, key), base_value, str(new_value)])
        else:
            rows.append([
                label_by_key.get(key, key),
                tr(float(base_value), 3),
                tr(float(new_value), 3),
            ])
    kit.data_table(
        document,
        ["Karar değişkeni", "Taban çizgisi", "Önerilen çözüm"],
        rows,
        widths=[6.4, 4.5, 4.6],
    )
    kit.body(
        document,
        "Tabloda dikkat çeken nokta, önerilen çözümün EPS kalınlığını taban "
        "çizgisinin altına indirmesidir. Bu, duyarlılık analizinin sonucuyla "
        "tutarlıdır: yalıtım kalınlığı enerji üzerinde ölçülebilir bir etki "
        "üretmediği için optimizasyon, söz konusu kalemi maliyet açısından "
        "azaltmaktadır.",
    )

    kit.heading2(document, "Ek B. Yazılım ve Veri Erişilebilirliği")
    kit.body(
        document,
        "Çalışmada kullanılan tüm kod, üretilen ara çıktılar ve rapor dosyaları "
        "sürüm kontrolü altındadır. Simülasyon motoru olarak OpenStudio 3.11.0 ve "
        "bununla gelen EnergyPlus sürümü kullanılmıştır. Vekil model kurulumunda "
        "scikit-learn, çok amaçlı optimizasyonda pymoo kütüphaneleri "
        "kullanılmıştır. Analiz adımlarının her biri ayrı bir komut satırı betiği "
        "olarak yürütülebilir durumdadır.",
    )
    kit.table_caption(document, "Tablo B.1. Analiz adımları ve karşılık gelen betikler")
    kit.data_table(
        document,
        ["Adım", "Betik", "Üretilen çıktı"],
        [
            ["Model onarımı", "model_repair_worker.py", "onarilmis model, onarim raporu"],
            ["Parametrik koşu", "run_parametric_study.py", "tasarım matrisi, sonuç tablosu"],
            ["Vekil model ve duyarlılık", "run_surrogate.py", "surrogate_report.json"],
            ["ISO 50001 raporu", "build_iso50001_report.py", "iso50001_report.json"],
            ["Çok amaçlı optimizasyon", "run_optimization.py", "pareto_front.json"],
            ["Sayısal doğrulama", "run_validation.py", "validation_report.json"],
            ["Rapor şekilleri ve metni", "reporting/sonuc_raporu.py", "bu rapor"],
        ],
        widths=[4.4, 5.4, 5.7],
    )
    kit.body(
        document,
        "Raporun tüm sayısal değerleri, yukarıdaki betiklerin ürettiği JSON "
        "dosyalarından okunarak yerleştirilmektedir; metinde elle yazılmış sonuç "
        "değeri bulunmamaktadır. Analiz yeniden koşulduğunda rapor da yeniden "
        "üretilmelidir.",
    )

    kit.heading2(document, "Ek C. Varsayımlar ve Doğrulanması Gereken Girdiler")
    kit.body(
        document,
        "Aşağıdaki girdiler ölçüme değil kabule dayanmaktadır ve raporun "
        "sonuçları yorumlanırken göz önünde bulundurulmalıdır.",
    )
    kit.table_caption(document, "Tablo C.1. Varsayıma dayalı girdiler")
    kit.data_table(
        document,
        ["Girdi", "Kabul", "Etkilediği sonuç"],
        [
            ["Enerji taban çizgisi", "Simülasyon kaynaklı, faturaya kalibre değil",
             "Mutlak tüketim değerleri"],
            ["Yatırım birim fiyatları", "Piyasa araştırmasına dayanmayan kabul",
             "Pareto cephesinin maliyet ekseni"],
            ["TS 825 iklim bölgesi", "Üçüncü bölge kabulü",
             "Duvar ve cam ısı geçirgenlik kısıtları"],
            ["Bina kullanıcı sayısı", "Model içindeki kullanım yoğunluğundan türetildi",
             "Kişi başına enerji göstergesi"],
            ["Asansör motor gücü", "Onarım sırasında tek mekâna bağlandı",
             "İç ekipman enerjisi"],
        ],
        widths=[4.0, 6.2, 5.3],
    )
