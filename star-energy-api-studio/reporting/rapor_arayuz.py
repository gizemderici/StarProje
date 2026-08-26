"""Proje Sonuc Raporu: yazilim arayuzu bolumu ve ekran goruntuleri.

Ekran goruntuleri reporting/ekran_goruntuleri.py tarafindan uretilir.
Gorsel eksikse ilgili sekil atlanir ve rapor yine de uretilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reporting import docx_kit as kit


@dataclass(frozen=True, slots=True)
class ScreenFigure:
    filename: str
    caption: str
    lead: str


SCREENS = (
    ScreenFigure(
        "ekran_1_enerji_merkezi.png",
        "Şekil 3.2. Enerji Merkezi ekranı: onarılmış taban koşusunun özet "
        "göstergeleri, son kullanım dağılımı ve aylık tüketim profili",
        "Enerji Merkezi ekranı, taban çizgisinin doğrudan EnergyPlus SQL "
        "çıktısından okunan göstergelerini sunar. Ekranın üst bandındaki koşu "
        "seçicisi, onarılmış taban çizgisi ile tarihsel referans niteliğindeki "
        "eski arşiv koşuları arasında geçiş yapmayı sağlar; arşiv koşusu "
        "seçildiğinde bu koşuların parametrik veri olarak kullanılamayacağını "
        "belirten bir veri kalitesi uyarısı görüntülenir.",
    ),
    ScreenFigure(
        "ekran_2_senaryo_kurucu.png",
        "Şekil 3.3. Senaryo Kurucu ekranı: karar değişkenlerinin tanımlanması ve "
        "gerçek OpenStudio koşusunun başlatılması",
        "Senaryo Kurucu ekranı, Bölüm 3.3'te tanımlanan karar değişkenlerinin "
        "elle belirlenmesine ve tek bir senaryonun gerçek OpenStudio iş akışıyla "
        "koşturulmasına olanak verir. Bu ekran, vekil model tahminlerinin nokta "
        "bazında sınanmasında kullanılmıştır.",
    ),
    ScreenFigure(
        "ekran_3_model_varliklar.png",
        "Şekil 3.4. Model ve Varlıklar ekranı: mekân, yüzey, ısıl bölge ve "
        "konstrüksiyon katmanlarının incelenmesi",
        "Model ve Varlıklar ekranı, bina modelinin içeriğini OpenStudio "
        "yazılım geliştirme kitinin resmî arayüzü üzerinden okur. Mekân sayısı, "
        "yüzey sayısı, ısıl bölgeler ve konstrüksiyon katmanlarının ısıl "
        "özellikleri bu ekrandan doğrulanabilir.",
    ),
    ScreenFigure(
        "ekran_4_vekil_model.png",
        "Şekil 4.5. Vekil Model ekranı: aday modellerin karşılaştırması, bağımsız "
        "test kümesi başarımı ve duyarlılık sıralaması",
        "Vekil Model ekranı Bölüm 4.2 ve 4.4'teki bulguları etkileşimli olarak "
        "sunar. Aday modellerin başarımı, bağımsız test kümesindeki ölçütler ve "
        "Sobol duyarlılık sıralaması aynı ekranda görüntülenir; kabul ölçütünü "
        "karşılamayan hedefler ayrıca işaretlenir.",
    ),
    ScreenFigure(
        "ekran_5_pareto.png",
        "Şekil 4.6. Pareto ekranı: çok amaçlı optimizasyon cephesi ve hipervolüm "
        "yakınsaması",
        "Pareto ekranı, Bölüm 4.5'te sunulan cepheyi etkileşimli olarak "
        "görüntüler. Çözümler amaç eksenlerine göre incelenebilir; TOPSIS uzlaşı "
        "çözümü ve uç noktalar ayrıca işaretlenmiştir.",
    ),
    ScreenFigure(
        "ekran_6_iso50001.png",
        "Şekil 4.7. ISO 50001 ekranı: önemli enerji kullanımları, derece-gün "
        "normalizasyonu ve enerji performans göstergeleri",
        "ISO 50001 ekranı, Bölüm 4.3'teki göstergeleri standardın kavram "
        "diliyle sunar. Önemli enerji kullanımlarının kümülatif payı, iklim "
        "normalizasyonunda kullanılan derece-gün değerleri ve taban çizgisi "
        "göstergeleri bu ekranda toplanmıştır. Taban çizgisinin ölçülmüş veriye "
        "kalibre edilmediği uyarısı ekranda açıkça yer alır.",
    ),
    ScreenFigure(
        "ekran_7_dogrulama.png",
        "Şekil 4.8. Doğrulama ekranı: vekil model tahmini ile bağımsız EnergyPlus "
        "koşusunun nokta bazında karşılaştırılması",
        "Doğrulama ekranı, Bölüm 4.6'daki sonuçları nokta bazında listeler. Her "
        "doğrulama noktası için vekil model tahmini, gerçek EnergyPlus sonucu, "
        "sapma yüzdesi ve noktanın seçilme gerekçesi görüntülenir; kabul "
        "ölçütünün sağlanıp sağlanmadığı ekranın üst bandında belirtilir.",
    ),
)

# Bolum 3'e giren arayuz sekilleri ile Bolum 4'e girenlerin ayrimi.
METHOD_SCREENS = SCREENS[:3]
FINDING_SCREENS = SCREENS[3:]


def _place(document, screen: ScreenFigure, screenshot_dir: Path) -> bool:
    path = screenshot_dir / screen.filename
    if not path.exists():
        return False
    kit.body(document, screen.lead)
    kit.figure(document, path, width_cm=15.5)
    kit.figure_caption(document, screen.caption)
    return True


def software_section(document, facts: dict[str, Any], screenshot_dir: Path) -> None:
    """3.10 Yazilim araci ve arayuz."""
    kit.heading2(document, "3.10 Yazılım Aracı ve Kullanıcı Arayüzü")
    kit.body(
        document,
        "Yöntemin uygulanabilir ve yinelenebilir olması için, tüm analiz "
        "adımlarını tek bir çalışma alanında toplayan bir yazılım aracı "
        "geliştirilmiştir. Araç üç katmanlı bir mimariye sahiptir: kullanıcı "
        "arayüzü NiceGUI ile, uygulama katmanı FastAPI tabanlı bir HTTP "
        "arayüzüyle, simülasyon katmanı ise OpenStudio yazılım geliştirme kitiyle "
        "gerçekleştirilmiştir.",
    )
    kit.body(
        document,
        "Katmanlar arasındaki ayrım bilinçlidir. Kullanıcı arayüzü model, "
        "simülasyon sonucu veya veri dosyalarını doğrudan açmaz; yalnızca model "
        "kimliği ve JSON veri yapıları üzerinden HTTP arayüzüne başvurur. Yerel "
        "dosya yolları arayüz yanıtlarında dışarı verilmez. Bu tasarım, analiz "
        "mantığının görselleştirmeden bağımsız olarak sınanabilmesini ve aracın "
        "başka bir bina modeline uygulanabilmesini sağlar.",
    )
    kit.body(
        document,
        "Aracın genel yapısı Şekil 3.1'de, başlıca ekranları ise Şekil 3.2 – "
        "Şekil 3.4 arasında sunulmuştur. Analiz sonuçlarını görüntüleyen ekranlar "
        "Bölüm 4'te ilgili bulgularla birlikte verilmiştir.",
    )
    architecture = screenshot_dir.parent / "sekiller/sekil_3_1_mimari.png"
    if architecture.exists():
        kit.figure(document, architecture, width_cm=13.0)
        kit.figure_caption(
            document,
            "Şekil 3.1. Yazılım aracının katmanlı mimarisi",
        )

    kit.table_caption(document, "Tablo 3.3. Yazılım aracının katmanları")
    kit.data_table(
        document,
        ["Katman", "Teknoloji", "Sorumluluk"],
        [
            ["Kullanıcı arayüzü", "NiceGUI", "Görselleştirme ve etkileşim"],
            ["Uygulama arayüzü", "FastAPI", "Model kimliği, doğrulama, yetkilendirme"],
            ["Servis katmanı", "OpenStudio SDK", "Model okuma ve iş akışı üretimi"],
            ["Simülasyon", "EnergyPlus", "Yıllık enerji hesabı"],
            ["Analiz", "scikit-learn, pymoo", "Vekil model ve optimizasyon"],
        ],
        widths=[3.6, 4.4, 7.5],
    )
    for screen in METHOD_SCREENS:
        _place(document, screen, screenshot_dir)


def interface_findings(document, facts: dict[str, Any], screenshot_dir: Path) -> None:
    """4.7 Sonuclarin arayuzde sunumu."""
    kit.heading2(document, "4.7 Sonuçların Arayüzde Sunumu")
    kit.body(
        document,
        "Bölüm 4.2 – 4.6 arasında sunulan bulgular, yazılım aracının ilgili "
        "ekranlarında etkileşimli olarak da görüntülenebilmektedir. Bu ekranlar "
        "raporun statik tablolarının yerini almaz; analiz sonuçlarının "
        "yinelenebilirliğini ve karar vericiye aktarılabilirliğini gösterir. "
        "Ekranların tümü, raporun sayısal bölümlerini besleyen aynı çıktı "
        "dosyalarını okur; ayrı bir veri kopyası tutulmaz.",
    )
    for screen in FINDING_SCREENS:
        _place(document, screen, screenshot_dir)


def available(screenshot_dir: Path) -> int:
    return sum(1 for shot in SCREENS if (screenshot_dir / shot.filename).exists())
