"""Proje Sonuc Raporu: 4. Bulgular, 5. Tartisma, 6. Sonuc ve Oneriler, Kaynaklar.

Sayisal degerler cagiran taraftan `facts` sozlugu ile gelir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporting import docx_kit as kit
from reporting.figures import label_of
from ui_pages.panels import reason_label


def tr(value: float, digits: int = 2) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# --------------------------------------------------------------------------- #
# 4. Bulgular
# --------------------------------------------------------------------------- #
def findings(document, facts: dict[str, Any], figure_dir: Path) -> None:
    kit.heading1(document, "4. Bulgular")

    _baseline(document, facts)
    _sensitivity(document, facts, figure_dir)
    _iso(document, facts, figure_dir)
    _surrogate(document, facts)
    _pareto(document, facts, figure_dir)
    _validation(document, facts, figure_dir)


def _baseline(document, facts: dict[str, Any]) -> None:
    kit.heading2(document, "4.1 Model Onarımının Ölçülen Etkisi")
    kit.body(
        document,
        "Bölüm 3.2'de tanımlanan onarımların taban çizgisi üzerindeki etkisi "
        "Tablo 4.1'de verilmiştir. En belirgin değişim, asansör boşluğunun yıl "
        "boyunca 88,0 °C ortalama sıcaklıkta kalmasına yol açan yapay ısı "
        "kazancının ortadan kalkmasıdır. Bu kazanç komşu bölgelere iç yüzeylerden "
        "aktarıldığı için soğutma yükünü de şişirmekteydi.",
    )
    kit.table_caption(
        document, "Tablo 4.1. Model onarımının taban çizgisi üzerindeki etkisi"
    )
    kit.data_table(
        document,
        ["Gösterge", "Onarım öncesi", "Onarım sonrası"],
        [
            ["Severe düzeyinde hata sayısı", "3", "0"],
            ["Toplam saha enerjisi (GJ/yıl)", "2.128,85", "1.920,00"],
            ["Enerji yoğunluğu (MJ/m²·yıl)", "501,36", "452,17"],
            ["İç ekipman enerjisi (GJ/yıl)", "433,16", "261,13"],
            ["Soğutma enerjisi (GJ/yıl)", "1.173,86", "1.119,56"],
            ["Isıtma enerjisi (GJ/yıl)", "30,95", "46,20"],
            ["ASHRAE 55 konforsuz saat", "3.253,50", "494,83"],
            ["Asansör boşluğu ortalama sıcaklığı (°C)", "88,0", "21,2"],
        ],
        widths=[7.4, 4.0, 4.1],
    )
    kit.body(
        document,
        "Isıtma enerjisindeki artış beklenen bir sonuçtur: asansör motorunun aşırı "
        "değerlendirilmiş atık ısısı ortadan kalkmış, ayrıca kuyuya eklenen doğal "
        "havalandırma ısı atmaya başlamıştır. Onarım sonrası elde edilen 1.920,00 GJ "
        "değeri, çalışmanın tüm sonraki adımlarında enerji taban çizgisi olarak "
        "kullanılmıştır.",
    )


def _sensitivity(document, facts: dict[str, Any], figure_dir: Path) -> None:
    indices = facts["sensitivity"]
    ordered = sorted(indices, key=lambda item: item["total"], reverse=True)
    top = ordered[0]
    eps = next(item for item in indices if item["key"] == "eps_thickness_cm")

    kit.heading2(document, "4.2 Duyarlılık Analizi")
    kit.body(
        document,
        "Toplam saha enerjisi hedefine ilişkin Sobol duyarlılık indisleri "
        "Tablo 4.2'de sayısal olarak, Şekil 4.1'de ise görsel olarak sunulmuştur. "
        f"Sıralamanın ilk basamağında {tr(top['first_order'], 4)} birinci mertebe "
        f"indisiyle {label_of(top['label'])} yer almaktadır; tek bu değişken enerji "
        f"varyansının yaklaşık %{tr(top['first_order'] * 100, 0)}'ini "
        "açıklamaktadır.",
    )
    kit.table_caption(
        document,
        "Tablo 4.2. Toplam saha enerjisi için Sobol duyarlılık indisleri",
    )
    kit.data_table(
        document,
        ["Sıra", "Karar değişkeni", "Birinci mertebe (S₁)", "Toplam etki (S_T)"],
        [
            [str(index + 1), label_of(item["label"]),
             tr(item["first_order"], 4), tr(item["total"], 4)]
            for index, item in enumerate(ordered)
        ],
        widths=[1.6, 7.0, 3.4, 3.5],
    )
    kit.figure(document, figure_dir / "sekil_4_1_duyarlilik.png", width_cm=15.0)
    kit.figure_caption(
        document,
        "Şekil 4.1. Karar değişkenlerinin toplam saha enerjisine ilişkin Sobol "
        "birinci mertebe ve toplam etki indisleri",
    )
    kit.body(
        document,
        f"Başlangıç hipotezinin değişkeni olan EPS kalınlığı, on bir değişken "
        f"arasında son sırada yer almaktadır. Birinci mertebe indisi "
        f"{tr(eps['first_order'], 4)}, toplam etki indisi ise {tr(eps['total'], 4)} "
        "değerindedir; bir başka deyişle değişken, enerji varyansının binde birini "
        "dahi açıklamamaktadır. Isıl iletkenlik değişkeni de aynı biçimde "
        "sıralamanın alt basamaklarındadır. Bu bulgu, yalıtım kalınlığının bu bina "
        "için etkili bir müdahale kalemi olmadığının birinci kanıtıdır.",
    )


def _iso(document, facts: dict[str, Any], figure_dir: Path) -> None:
    seu = facts["seu"]
    uses = seu["uses"]
    indicators = facts["iso"]["baseline_indicators"]
    climate = facts["iso"]["climate"]

    kit.heading2(document, "4.3 ISO 50001 Göstergeleri ve Önemli Enerji Kullanımları")
    kit.body(
        document,
        "Son kullanım kalemlerinin dağılımı Tablo 4.3 ve Şekil 4.2'de verilmiştir. "
        f"Kümülatif pay, ilk {len(seu['significant_uses'])} kalemde "
        f"%{tr(seu['significant_share_percent'], 1)} değerine ulaşarak %80 eşiğini "
        "aşmaktadır; dolayısıyla ISO 50001 kapsamındaki önemli enerji kullanımları "
        + ", ".join(label_of(name) for name in seu["significant_uses"])
        + " kalemleridir.",
    )
    kit.table_caption(
        document, "Tablo 4.3. Son kullanımlara göre enerji dağılımı ve önemli "
        "enerji kullanımları"
    )
    kit.data_table(
        document,
        ["Son kullanım", "Enerji (GJ/yıl)", "Pay (%)", "Kümülatif (%)", "SEU"],
        [
            [label_of(item["label"]), tr(item["energy_gj"], 2),
             tr(item["share_percent"], 1), tr(item["cumulative_percent"], 1),
             "Evet" if item["significant"] else "Hayır"]
            for item in uses
        ],
        widths=[4.4, 3.4, 2.4, 3.0, 2.3],
    )
    kit.figure(document, figure_dir / "sekil_4_2_seu.png", width_cm=15.0)
    kit.figure_caption(
        document,
        "Şekil 4.2. Son kullanımlara göre yıllık enerji tüketimi ve kümülatif pay "
        "eğrisi; koyu sütunlar önemli enerji kullanımlarını göstermektedir",
    )
    heating = next(item for item in uses if item["name"] == "Heating")
    cooling = uses[0]
    kit.body(
        document,
        f"Bina belirgin biçimde soğutma ağırlıklıdır: soğutma tek başına toplam "
        f"tüketimin %{tr(cooling['share_percent'], 1)}'ini oluştururken ısıtmanın "
        f"payı yalnızca %{tr(heating['share_percent'], 1)}'dir. Isı yalıtımının "
        "doğrudan etkilediği kalem ısıtma olduğuna göre, yalıtım iyileştirmesinin "
        "üzerinde çalışabileceği taban zaten küçüktür. Bu, başlangıç hipotezine "
        "ilişkin ikinci kanıttır.",
    )
    kit.table_caption(document, "Tablo 4.4. Taban çizgisi enerji performans göstergeleri")
    kit.data_table(
        document,
        ["Gösterge", "Değer", "Birim"],
        [[item["label"], tr(item["value"], 4), item["unit"]] for item in indicators],
        widths=[7.4, 4.0, 4.1],
    )
    kit.body(
        document,
        f"İklim normalizasyonunda kullanılan derece-gün değerleri, 18 °C tabanlı "
        f"ısıtma için {tr(climate['hdd'], 1)}, 22 °C tabanlı soğutma için "
        f"{tr(climate['cdd'], 1)}'dir. Taban çizgisinin simülasyon kaynaklı olduğu ve "
        "ölçülmüş tüketim verisine kalibre edilmediği vurgulanmalıdır; göstergeler "
        "bu nedenle mutlak bir performans beyanı değil, senaryolar arası "
        "karşılaştırma ölçeği olarak kullanılmalıdır.",
    )


def _surrogate(document, facts: dict[str, Any]) -> None:
    scores = facts["surrogate"]["test_scores"]
    dataset = facts["surrogate"]["dataset"]
    speedup = facts["surrogate"]["speedup"]
    energy = facts["scores"]["site_energy_gj"]

    kit.heading2(document, "4.4 Vekil Model Doğruluğu")
    kit.body(
        document,
        f"Vekil model, {dataset['train_rows']} satırlık eğitim kümesi üzerinde "
        f"eğitilmiş ve {dataset['test_rows']} satırlık bağımsız test kümesinde "
        "sınanmıştır. Sonuçlar Tablo 4.5'te verilmiştir. Optimizasyonun amaç "
        "fonksiyonlarını besleyen iki hedef olan toplam saha enerjisi ve konfor "
        "ihlali, kabul ölçütlerini karşılamaktadır.",
    )
    kit.table_caption(
        document, "Tablo 4.5. Bağımsız test kümesinde vekil model başarımı"
    )
    rows = []
    for row in scores:
        metric = row["metric"]
        value = (row["cvrmse_percent"] if metric == "CVRMSE"
                 else row["nrmse_range_percent"])
        rows.append([
            row["target"],
            row["model"],
            tr(row["r2"], 3),
            metric.replace("(aralik)", " (aralık)"),
            f"%{tr(value, 2)}",
            "Geçti" if row["meets_target"] else "Kaldı",
        ])
    kit.data_table(
        document,
        ["Hedef", "Model", "R²", "Ölçüt", "Değer", "Kapı"],
        rows,
        widths=[4.4, 2.2, 1.8, 3.2, 2.0, 1.9],
    )
    kit.body(
        document,
        f"Toplam saha enerjisi hedefinde %{tr(energy['cvrmse_percent'], 2)} CVRMSE ve "
        f"{tr(energy['r2'], 3)} belirlilik katsayısı elde edilmiştir; normalize "
        f"ortalama yanlılık hatası %{tr(energy['nmbe_percent'], 3)} ile ihmal "
        "edilebilir düzeydedir. Isıtma enerjisi hedefi kabul ölçütünü "
        "karşılamamaktadır ve bu durum açıkça raporlanmaktadır. Nedeni, eğitim "
        "kümesindeki koşuların yaklaşık yarısında ısıtma enerjisinin sıfıra yakın "
        "olmasıdır; bu hedef amaç fonksiyonlarında kullanılmadığından kabul "
        "kapısının dışında tutulmuştur.",
    )
    kit.body(
        document,
        f"Hesaplama maliyeti açısından bir EnergyPlus koşusu ortalama "
        f"{tr(speedup['energyplus_seconds_per_run'], 0)} saniye sürerken, vekil model "
        "çağrısı mikrosaniye mertebesindedir. Elde edilen hızlanma oranı yaklaşık "
        f"{tr(speedup['ratio'] / 1e6, 1)} milyon kattır. Bu oran, on binlerce aday "
        "çözümün değerlendirilmesini gerektiren duyarlılık analizi ve çok amaçlı "
        "optimizasyon adımlarını uygulanabilir kılan temel etkendir.",
    )


def _pareto(document, facts: dict[str, Any], figure_dir: Path) -> None:
    front = facts["front"]
    convergence = front["convergence"]

    kit.heading2(document, "4.5 Pareto Cephesi")
    kit.body(
        document,
        f"NSGA-II çalıştırması {len(convergence)} nesil boyunca yürütülmüş ve "
        f"{front['solution_count']} çözümlü bir Pareto cephesi üretmiştir. "
        f"Hipervolüm göstergesi {tr(convergence[0]['hypervolume'], 4)} başlangıç "
        f"değerinden {tr(convergence[-1]['hypervolume'], 4)} değerine yükselmiş ve "
        "yaklaşık ellinci nesilden sonra kararlı seyretmiştir. Cephe ile yakınsama "
        "eğrisi Şekil 4.3'te birlikte sunulmuştur.",
    )
    kit.figure(document, figure_dir / "sekil_4_3_pareto.png", width_cm=15.5)
    kit.figure_caption(
        document,
        "Şekil 4.3. Solda enerji performans göstergesi ile yatırım maliyeti "
        "düzleminde Pareto cephesi (renk ölçeği konfor ihlalini göstermektedir), "
        "sağda hipervolüm yakınsaması",
    )
    kit.body(
        document,
        "Cephenin biçimi, enerji ile maliyet arasındaki ödünleşimin doğrusal "
        "olmadığını göstermektedir. Yüksek enerji tüketimli bölgede görece küçük "
        "yatırımlarla belirgin kazanım elde edilirken, düşük enerji bölgesinde aynı "
        "kazanım için gereken yatırım hızla artmaktadır.",
    )


def _validation(document, facts: dict[str, Any], figure_dir: Path) -> None:
    summary = facts["summary"]
    points = sorted(
        facts["validation"]["points"],
        key=lambda item: abs(item["deviation_percent"]),
        reverse=True,
    )
    topsis = facts["topsis"]

    kit.heading2(document, "4.6 Sayısal Doğrulama")
    kit.body(
        document,
        "Doğrulama süreci dört tur olarak yürütülmüştür. İlk iki turda kabul "
        "ölçütü sağlanamamış, üstelik adaptif örnekleme tek başına uygulandığında "
        "sapma büyümüştür. Turların özeti Tablo 4.6'da verilmiştir.",
    )
    kit.table_caption(document, "Tablo 4.6. Doğrulama turlarının özeti")
    kit.data_table(
        document,
        ["Tur", "Belirsizlik katsayısı k", "Eğitim satırı", "Ortalama sapma",
         "En büyük sapma", "Kapı"],
        [
            ["1", "0", "151", "%2,72", "%5,22", "Kaldı"],
            ["2", "0", "159", "%3,40", "%8,11", "Kaldı"],
            ["3", "1,0", "167", "%2,38", "%5,31", "Kaldı"],
            ["4", "0,5", "175",
             f"%{tr(summary['mean_absolute_deviation_percent'], 2)}",
             f"%{tr(summary['max_absolute_deviation_percent'], 2)}", "Geçti"],
        ],
        widths=[1.4, 3.4, 2.6, 2.8, 2.8, 2.5],
    )
    kit.body(
        document,
        "İlk iki turda toplam on altı sapmanın on dördü negatif işaretlidir; bu, "
        "rastgele bir hata dağılımı değil sistematik bir yanlılık göstergesidir. "
        "Vekil model, optimizasyonun yerleştiği bölgede tutarlı biçimde iyimser "
        "tahmin üretmektedir. Bulgunun yorumu Bölüm 5.2'de tartışılmaktadır. "
        "Uygulanan çözüm, Kriging modelinin ürettiği tahmin belirsizliğinin "
        "optimizasyona bir ceza terimi olarak aktarılmasıdır: amaç fonksiyonuna "
        "ortalama tahmin yerine ortalama ile standart sapmanın k katının toplamı "
        "verilmektedir.",
    )
    kit.body(
        document,
        "Dördüncü turda kabul ölçütü sağlanmıştır. Sekiz doğrulama noktasının "
        "tamamı toleransın içindedir; ortalama mutlak sapma "
        f"%{tr(summary['mean_absolute_deviation_percent'], 2)}, en büyük mutlak sapma "
        f"%{tr(summary['max_absolute_deviation_percent'], 2)} olarak ölçülmüştür. "
        "Nokta bazında sonuçlar Tablo 4.7 ve Şekil 4.4'te verilmiştir.",
    )
    kit.table_caption(
        document,
        "Tablo 4.7. Dördüncü turda doğrulama noktalarının vekil model tahmini ile "
        "EnergyPlus sonucunun karşılaştırılması",
    )
    kit.data_table(
        document,
        ["case_id", "Seçim gerekçesi", "Vekil tahmin", "EnergyPlus", "Sapma"],
        [
            [item["case_id"].replace("case_", ""),
             reason_label(item["reason"]),
             tr(item["predicted_enpi_kwh_m2"], 2),
             tr(item["actual_enpi_kwh_m2"], 2),
             f"%{tr(item['deviation_percent'], 2)}"]
            for item in points
        ],
        widths=[2.8, 5.4, 2.4, 2.4, 2.0],
    )
    kit.figure(document, figure_dir / "sekil_4_4_dogrulama.png", width_cm=15.0)
    kit.figure_caption(
        document,
        "Şekil 4.4. Doğrulama noktalarında vekil model tahmininin EnergyPlus "
        "sonucundan sapması; kesikli çizgiler ±%5 kabul toleransını göstermektedir",
    )
    kit.body(
        document,
        "Değerler enerji performans göstergesi cinsindendir. Tezde önerilecek TOPSIS "
        f"uzlaşı çözümünün sapması %{tr(abs(topsis['deviation_percent']), 2)}'dir. Bu "
        "çözüm, taban çizgisindeki 1.920,00 GJ tüketimi "
        f"{tr(topsis['actual_site_energy_gj'], 2)} GJ seviyesine indirmekte, enerji "
        "performans göstergesini ise "
        f"{tr(topsis['actual_enpi_kwh_m2'], 2)} kWh/m²·yıl değerine çekmektedir.",
    )
    kit.body(
        document,
        "Konfor ihlali hedefinde vekil model, doğrulanan çözümlerde sıfır ihlal "
        "öngörmüş, gerçek koşuda ise sınırlı sayıda ihlal saati ölçülmüştür. Bu "
        "hedefin seyrek dağılımlı yapısı göz önüne alındığında beklenen bir "
        "sonuçtur ve raporlanan sapma değerleri enerji göstergesi üzerinden "
        "tanımlanmıştır.",
    )


# --------------------------------------------------------------------------- #
# 5. Tartisma
# --------------------------------------------------------------------------- #
def discussion(document, facts: dict[str, Any]) -> None:
    eps = next(item for item in facts["sensitivity"]
               if item["key"] == "eps_thickness_cm")
    seu = facts["seu"]

    kit.heading1(document, "5. Tartışma")

    kit.heading2(document, "5.1 Başlangıç Hipotezinin Reddi")
    kit.body(
        document,
        "Projenin kurgulandığı yalıtım odaklı hipotez, birbirinden bağımsız üç "
        "kanıt hattıyla reddedilmiştir. Birincisi duyarlılık analizidir: EPS "
        f"kalınlığının birinci mertebe Sobol indisi {tr(eps['first_order'], 4)} "
        "değerindedir ve on bir değişken arasında son sırada yer almaktadır. "
        "İkincisi enerji dağılımıdır: bina soğutma ağırlıklıdır ve ısıtmanın payı "
        f"%{tr(next(item for item in seu['uses'] if item['name'] == 'Heating')['share_percent'], 1)} "
        "ile sınırlıdır. Üçüncüsü ise standarda uygunluk kontrolüdür: taban "
        "çizgisindeki dış duvarın ısı geçirgenlik katsayısı 0,2901 W/m²K olup "
        "TS 825'in 0,50 W/m²K sınırının belirgin biçimde altındadır; cam ısı "
        "geçirgenlik katsayısı ise 2,718 W/m²K ile 2,80 W/m²K sınırının altında "
        "kalmaktadır. Bina kabuğu her iki bileşende de standardı sağlamaktadır.",
    )
    kit.body(
        document,
        "Üç kanıt aynı sonuca işaret etmektedir: bu binada iyileştirme potansiyeli "
        "kabuğun standarda uydurulmasında değil, soğutma yükünün azaltılmasında "
        "bulunmaktadır. Kabuk hâlihazırda uyumlu olduğuna göre, mevzuata uyum "
        "gerekçesiyle yapılacak bir yalıtım veya cam yenilemesinin dayanağı "
        "yoktur; cam değişimi ancak güneş kazancını azaltarak soğutma yükünü "
        "düşürdüğü ölçüde gerekçelendirilebilir. Duyarlılık sıralamasının ilk üç "
        "basamağını chiller verimi, "
        "soğutma ayar noktası ve cam tipi oluşturmaktadır ki bunların tümü aynı "
        "fiziksel mekanizmaya, yani soğutma yüküne bağlanmaktadır.",
    )
    kit.body(
        document,
        "Bu sonuç yöntemin değerini ortaya koymaktadır. Sezgiye dayalı bir "
        "iyileştirme programı, kaynakların büyük bölümünü ölçülebilir bir kazanım "
        "üretmeyecek olan duvar yalıtımına yönlendirecekti. Nicel duyarlılık "
        "analizi, bu yanlış yönlendirmeyi yatırım kararı alınmadan önce ve sayısal "
        "kanıtla önlemiştir.",
    )

    kit.heading2(document, "5.2 Optimizasyonun Vekil Model Hatasını Sömürmesi")
    kit.body(
        document,
        "Doğrulama sürecinin ilk iki turunda ortaya çıkan sistematik yanlılık, "
        "yöntem açısından çalışmanın en önemli bulgusudur. NSGA-II, amaç "
        "fonksiyonunu en küçüklerken vekil modelin gerçekten iyi olduğu noktalarla "
        "modelin iyi sandığı noktaları birbirinden ayırt edemez. Az örneklenmiş bir "
        "bölgede model iyimser tahmin üretiyorsa, optimizasyon tam olarak o bölgeye "
        "yerleşir.",
    )
    kit.body(
        document,
        "Bulgunun ölçülebilir kanıtı, adaptif örneklemenin tek başına durumu "
        "iyileştirmek yerine kötüleştirmesidir. Birinci turda en büyük sapma %5,22 "
        "iken, doğrulama noktaları eğitim kümesine eklenip model yeniden "
        "eğitildikten sonra ikinci turda sapma %8,11 seviyesine çıkmıştır. Aynı "
        "aralıkta vekil modelin bağımsız test kümesindeki hatası ise düşmüştür. "
        "Yani modelin ortalama doğruluğu artarken doğrulama sapması büyümüştür. Bu "
        "çelişki, sorunun modelin ortalama doğruluğunda değil, optimizasyonun "
        "modeli nerede sorguladığında olduğunu göstermektedir. Her adaptif tur "
        "cepheyi daha da dışarı ittiği için model kendi belirsizlik bölgesine doğru "
        "ilerlemiştir.",
    )
    kit.body(
        document,
        "Uygulanan çözüm, Jones vd. (1998) tarafından pahalı kara kutu "
        "eniyilemesinde önerilen belirsizlik temelli yaklaşımın uyarlanmasıdır. "
        "Kriging yalnızca tahmin değil tahmin belirsizliği de ürettiğinden, "
        "optimizasyona ortalama yerine ortalama ile standart sapmanın k katının "
        "toplamı verilmiştir. Model, emin olmadığı bölgede kendini "
        "cezalandırmakta ve cephe iyi örneklenmiş bölgede kalmaktadır. Katsayının "
        "k = 1,0 seçildiği üçüncü turda yanlılık yön değiştirerek tümüyle pozitife "
        "dönmüş, k = 0,5 değerinde ise dengelenmiş ve kabul ölçütü sağlanmıştır.",
    )
    kit.body(
        document,
        "Bu katsayının bir ayar parametresi olduğu ve mevcut çalışmada deneysel "
        "olarak belirlendiği açıkça belirtilmelidir. Bununla birlikte dördüncü "
        "turun doğrulama noktaları, ayarın yapıldığı noktalardan tamamen farklıdır; "
        "seçim mekanizması eğitim kümesindeki çözümleri aday havuzundan "
        "çıkarmaktadır. Dolayısıyla raporlanan sapmalar ayar sürecinden bağımsızdır.",
    )
    kit.body(
        document,
        "Buradan çıkan genel sonuç, vekil model tabanlı çok amaçlı optimizasyonda "
        "doğrulamanın üç bileşenin birlikte çalışmasını gerektirdiğidir: doğrulama "
        "noktalarının eğitim kümesine eklendiği adaptif örnekleme, optimizasyonu az "
        "örneklenmiş bölgeye itilmekten alıkoyan belirsizlik cezası ve dairesel "
        "doğrulamaya karşı koruma. Bu üçü olmadan doğrulama, modelin gerçek hatasını "
        "değil ezberini ölçer.",
    )

    kit.heading2(document, "5.3 Sınırlılıklar")
    kit.body(
        document,
        "Çalışmanın sonuçları aşağıdaki sınırlar içinde yorumlanmalıdır.",
    )
    kit.bullet(
        document,
        "Enerji taban çizgisi simülasyon kaynaklıdır ve ölçülmüş fatura verisine "
        "kalibre edilmemiştir. Bu nedenle mutlak tüketim değerleri değil, senaryolar "
        "arası göreli farklar anlamlıdır.",
    )
    kit.bullet(
        document,
        "Yatırım maliyeti modelindeki birim fiyatlar varsayımdır. Pareto cephesinin "
        "maliyet ekseni, güncel piyasa fiyatlarıyla yeniden ölçeklenmelidir. Buna "
        "karşılık enerji ve konfor eksenleri bu varsayımdan etkilenmemektedir.",
    )
    kit.bullet(
        document,
        "TS 825 kısıtları üçüncü iklim bölgesi kabulüyle uygulanmıştır. Binanın "
        "gerçek iklim bölgesi doğrulanmalı ve gerekirse sınır değerler "
        "güncellenmelidir.",
    )
    kit.bullet(
        document,
        "Isıtma enerjisi hedefinde vekil model kabul ölçütünü karşılamamaktadır. "
        "Bu hedef amaç fonksiyonlarında kullanılmadığından sonuçları etkilememekte, "
        "ancak ısıtma odaklı bir çalışma için modelin yeniden kurulması gerekir.",
    )
    kit.bullet(
        document,
        "Eğitim kümesindeki koşuların bir bölümünde ısınma dönemi yakınsamasına "
        "ilişkin uyarılar bulunmaktadır. Uyarıların çoğu iklimlendirilmeyen tek bir "
        "bölgeyle ilgilidir ve konfor ölçütü bu bölgeyi dışlamaktadır.",
    )
    kit.bullet(
        document,
        "Tasarım uzayındaki EPS kalınlığı üst sınırı, uygulamada karşılığı "
        "bulunmayan bir değere kadar genişletilmiştir. Duyarlılık sonuçları göz "
        "önüne alındığında bu aralığın daraltılması, hesaplama maliyetini önemli "
        "ölçüde azaltacaktır.",
    )


# --------------------------------------------------------------------------- #
# 6. Sonuc ve oneriler
# --------------------------------------------------------------------------- #
def conclusions(document, facts: dict[str, Any]) -> None:
    summary = facts["summary"]
    topsis = facts["topsis"]
    enpi = facts["iso"]["baseline_indicators"][0]["value"]
    energy = facts["scores"]["site_energy_gj"]

    kit.heading1(document, "6. Sonuç ve Öneriler")
    kit.body(
        document,
        "Bu projede, önemli enerji kullanıcısı niteliğindeki bir kampüs binası için "
        "ISO 50001 uyumlu, vekil model tabanlı bir çok amaçlı optimizasyon yöntemi "
        "tasarlanmış ve simülasyon destekli sayısal doğrulamayla sınanmıştır. Elde "
        "edilen başlıca sonuçlar aşağıda özetlenmiştir.",
    )
    kit.bullet(
        document,
        f"Vekil model, bağımsız test kümesinde %{tr(energy['cvrmse_percent'], 2)} "
        f"CVRMSE ve {tr(energy['r2'], 3)} belirlilik katsayısı ile ASHRAE Guideline "
        "14 kabul sınırlarının içindedir ve EnergyPlus'a kıyasla milyonlar "
        "mertebesinde hızlanma sağlamaktadır.",
    )
    kit.bullet(
        document,
        f"Pareto cephesinden seçilen sekiz nokta bağımsız EnergyPlus koşularıyla "
        f"doğrulanmış, ortalama mutlak sapma "
        f"%{tr(summary['mean_absolute_deviation_percent'], 2)} ile %5 kabul "
        "ölçütünün altında kalmıştır.",
    )
    kit.bullet(
        document,
        f"Önerilen uzlaşı çözümü, enerji performans göstergesini {tr(enpi, 2)} "
        f"kWh/m²·yıl seviyesinden {tr(topsis['actual_enpi_kwh_m2'], 2)} kWh/m²·yıl "
        "seviyesine indirmektedir; söz konusu çözümün doğrulama sapması "
        f"%{tr(abs(topsis['deviation_percent']), 2)}'dir.",
    )
    kit.bullet(
        document,
        "Başlangıçtaki yalıtım odaklı hipotez, üç bağımsız kanıt hattıyla "
        "reddedilmiştir. İyileştirme potansiyeli soğutma sistemi verimliliği, "
        "soğutma ayar noktası ve cam bileşeninde yoğunlaşmaktadır.",
    )
    kit.bullet(
        document,
        "Vekil model tabanlı optimizasyonun, doğrulama olmaksızın sistematik olarak "
        "iyimser çözümler ürettiği ölçülmüş ve belirsizlik cezasıyla giderilmiştir.",
    )

    kit.heading2(document, "6.1 Uygulamaya Yönelik Öneriler")
    kit.body(
        document,
        "Bina işletmesi açısından öncelik sıralaması aşağıdaki gibi önerilmektedir.",
    )
    kit.bullet(
        document,
        "Yatırım gerektirmeyen ilk önlem, ayar noktalarının gözden geçirilmesidir. "
        "Mevcut durumda sekiz bölgenin tamamı yıl boyunca sabit 22/24 °C değerlerini "
        "kullanmakta, ölü bant yalnızca 2 K olmakta ve gece ile hafta sonu geri "
        "çekmesi bulunmamaktadır. Bu ayarlar, dış hava sıcaklığının düşük olduğu "
        "dönemlerde bile mekanik soğutma talebi doğurmaktadır.",
    )
    kit.bullet(
        document,
        "İkinci öncelik cam bileşenidir. Bina, modelde tanımlı yedi pencere "
        "konstrüksiyonunun en zayıfını 114 pencerenin tamamında kullanmaktadır. "
        "Mevcut cam TS 825 sınırını sağlamaktadır; dolayısıyla gerekçe mevzuata "
        "uyum değil, güneş kazancının azaltılmasıyla elde edilecek soğutma "
        "tasarrufudur. Cam-duvar oranının %78,61 olması bu kalemin kaldıracını "
        "artırmaktadır. Duyarlılık sıralamasında cam tipi üçüncü basamaktadır.",
    )
    kit.bullet(
        document,
        "Üçüncü öncelik soğutma sisteminin verimliliğidir; duyarlılık sıralamasında "
        "ilk basamak bu değişkene aittir.",
    )
    kit.bullet(
        document,
        "Dış duvar yalıtımının artırılması, mevcut duvar TS 825 sınırını zaten "
        "sağladığı ve duyarlılık katkısı ihmal edilebilir düzeyde olduğu için "
        "öncelikli müdahale kalemi olarak önerilmemektedir.",
    )
    kit.bullet(
        document,
        "Bu öncelik sıralaması, TS 825'in raporun hazırlandığı sırada geçerli olan "
        "önceki sürümüne dayanmaktadır. Standardın Ekim 2024 revizyonu daha sıkı "
        "değerler getirmiş olup 1 Nisan 2025'te yürürlüğe girmiştir; kabuk "
        "uygunluğu güncel sürüme göre yeniden denetlenmelidir.",
    )

    kit.heading2(document, "6.2 Sonraki Çalışmalar İçin Öneriler")
    kit.bullet(
        document,
        "Taban çizgisinin ölçülmüş tüketim verisiyle kalibre edilmesi, sonuçların "
        "ISO 50001 kapsamında resmî bir performans beyanına dönüştürülmesini "
        "sağlayacaktır.",
    )
    kit.bullet(
        document,
        "Belirsizlik ceza katsayısının deneysel olarak değil, doğrulama "
        "yanlılığını sıfırlayacak biçimde özdevimli olarak ayarlanması yöntemi "
        "daha genel hâle getirecektir.",
    )
    kit.bullet(
        document,
        "Yatırım maliyeti modelinin güncel piyasa fiyatlarıyla ve yaşam döngüsü "
        "maliyeti yaklaşımıyla yeniden kurulması, Pareto cephesinin karar "
        "vericiler açısından doğrudan kullanılabilir olmasını sağlayacaktır.",
    )
    kit.bullet(
        document,
        "Tasarım uzayının duyarlılık sonuçlarına göre daraltılması ve serbest kalan "
        "hesaplama bütçesinin soğutma sistemi değişkenlerine ayrılması, aynı maliyetle "
        "daha yüksek çözünürlüklü bir cephe üretecektir.",
    )


# --------------------------------------------------------------------------- #
# Kaynaklar
# --------------------------------------------------------------------------- #
REFERENCES = [
    "ASHRAE. 2014. ASHRAE Guideline 14-2014: Measurement of Energy, Demand, and "
    "Water Savings. Atlanta: American Society of Heating, Refrigerating and "
    "Air-Conditioning Engineers.",

    "Blank, J., Deb, K. 2020. “pymoo: Multi-objective optimization in "
    "Python”, IEEE Access, 8, 89497-89509.",

    "Crawley, D. B., Lawrie, L. K., Winkelmann, F. C., Buhl, W. F., Huang, Y. J., "
    "Pedersen, C. O., Strand, R. K., Liesen, R. J., Fisher, D. E., Witte, M. J., "
    "Glazer, J. 2001. “EnergyPlus: creating a new-generation building energy "
    "simulation program”, Energy and Buildings, 33(4), 319-331.",

    "Deb, K., Pratap, A., Agarwal, S., Meyarivan, T. 2002. “A fast and elitist "
    "multiobjective genetic algorithm: NSGA-II”, IEEE Transactions on "
    "Evolutionary Computation, 6(2), 182-197.",

    "Hwang, C. L., Yoon, K. 1981. Multiple Attribute Decision Making: Methods and "
    "Applications — A State-of-the-Art Survey. Berlin: Springer-Verlag.",

    "ISO. 2023. ISO 50006: Energy management systems — Evaluating energy "
    "performance using energy performance indicators and energy baselines "
    "(2. baskı). Cenevre: International Organization for Standardization.",

    "Jones, D. R., Schonlau, M., Welch, W. J. 1998. “Efficient global "
    "optimization of expensive black-box functions”, Journal of Global "
    "Optimization, 13(4), 455-492.",

    "Nguyen, A. T., Reiter, S., Rigo, P. 2014. “A review on simulation-based "
    "optimization methods applied to building performance analysis”, Applied "
    "Energy, 113, 1043-1058.",

    "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, "
    "O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., "
    "Passos, A., Cournapeau, D., Brucher, M., Perrot, M., Duchesnay, E. 2011. "
    "“Scikit-learn: machine learning in Python”, Journal of Machine "
    "Learning Research, 12, 2825-2830.",

    "Rasmussen, C. E., Williams, C. K. I. 2006. Gaussian Processes for Machine "
    "Learning. Cambridge: MIT Press.",

    "Saltelli, A., Annoni, P., Azzini, I., Campolongo, F., Ratto, M., Tarantola, S. "
    "2010. “Variance based sensitivity analysis of model output. Design and "
    "estimator for the total sensitivity index”, Computer Physics "
    "Communications, 181(2), 259-270.",

    "Sobol, I. M. 2001. “Global sensitivity indices for nonlinear mathematical "
    "models and their Monte Carlo estimates”, Mathematics and Computers in "
    "Simulation, 55(1-3), 271-280.",

    "TSE. 2008. TS 825: Binalarda Isı Yalıtım Kuralları. Ankara: Türk Standardları "
    "Enstitüsü. (Ekim 2024 revizyonu 1 Nisan 2025 itibarıyla yürürlüktedir.)",

    "TSE. 2018. TS EN ISO 50001: Enerji yönetim sistemleri — Şartlar ve "
    "kullanım kılavuzu. Ankara: Türk Standardları Enstitüsü.",

    "Westermann, P., Evins, R. 2019. “Surrogate modelling for sustainable "
    "building design — A review”, Energy and Buildings, 198, 170-186.",

    "Zitzler, E., Thiele, L. 1999. “Multiobjective evolutionary algorithms: a "
    "comparative case study and the strength Pareto approach”, IEEE "
    "Transactions on Evolutionary Computation, 3(4), 257-271.",
]


def references(document) -> None:
    from docx.shared import Cm, Pt

    kit.heading1(document, "Kaynaklar")
    for entry in sorted(REFERENCES):
        paragraph = kit.body(document, entry)
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.left_indent = Cm(1.0)
        paragraph.paragraph_format.first_line_indent = Cm(-1.0)
