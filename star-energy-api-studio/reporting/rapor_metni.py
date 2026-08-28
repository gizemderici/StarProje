"""Proje Sonuc Raporu ana metni: 1. Giris - 6. Sonuc ve Oneriler + Kaynaklar.

Sayisal degerler cagiran taraftan `facts` sozlugu ile gelir; bu modulde
elle yazilmis sayi bulunmaz.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporting import docx_kit as kit


def tr(value: float, digits: int = 2) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# --------------------------------------------------------------------------- #
# 1. Giris
# --------------------------------------------------------------------------- #
def introduction(document, facts: dict[str, Any]) -> None:
    kit.heading1(document, "1. Giriş")
    kit.body(
        document,
        "Enerji yönetim sistemleri, kuruluşların enerji performansını ölçülebilir "
        "biçimde iyileştirmesini hedefler. TS EN ISO 50001 standardı bu iyileştirmeyi "
        "sürekli bir çevrim olarak tanımlar ve çevrimin merkezine iki kavramı "
        "yerleştirir: enerji taban çizgisi (EnB) ve enerji performans göstergesi "
        "(EnPİ). Standardın öngördüğü ilk adım, toplam tüketimin baskın bölümünden "
        "sorumlu olan önemli enerji kullanımlarının (SEU) belirlenmesidir. Bu "
        "belirleme yapılmadan uygulanan iyileştirme önlemleri, kaynakların düşük "
        "getirili alanlara yönlendirilmesiyle sonuçlanabilir.",
    )
    kit.body(
        document,
        "Bina ölçeğinde enerji iyileştirmesi doğası gereği çok amaçlı bir karar "
        "problemidir. Enerji tüketimini azaltan bir müdahale çoğunlukla yatırım "
        "maliyeti doğurur; ısıl konforu iyileştiren bir ayar noktası değişikliği ise "
        "enerji tüketimini artırabilir. Bu amaçlar arasındaki ödünleşim tek bir "
        "optimum çözüm değil, bir Pareto cephesi üretir. Cephenin hesaplanabilmesi "
        "için binlerce aday çözümün değerlendirilmesi gerekir. Ayrıntılı bir "
        "EnergyPlus koşusu bu çalışmadaki bina için yaklaşık iki dakika sürmektedir; "
        "dolayısıyla doğrudan simülasyon tabanlı optimizasyon pratik değildir.",
    )
    kit.body(
        document,
        "Vekil model yaklaşımı bu darboğazı, sınırlı sayıda gerçek simülasyon "
        "koşusundan öğrenilen istatistiksel bir yaklaşımlayıcı kurarak aşar. Ancak "
        "vekil modelin kendi hatası, optimizasyon sürecine sistematik bir yanlılık "
        "olarak sızabilir. Bu nedenle vekil model tabanlı bir yöntemin bilimsel "
        "geçerliliği, ürettiği çözümlerin bağımsız simülasyonlarla doğrulanmasına "
        "bağlıdır. Raporun başlığındaki son ifade olan sayısal doğrulama, tam olarak "
        "bu gerekliliğe karşılık gelmektedir.",
    )

    kit.heading2(document, "1.1 Projenin Amacı ve Kapsamı")
    kit.body(
        document,
        "Projenin amacı, önemli enerji kullanıcısı niteliğindeki bir kampüs binası "
        "için ISO 50001 uyumlu, vekil model tabanlı bir çok amaçlı optimizasyon "
        "yöntemi tasarlamak ve bu yöntemi simülasyon destekli sayısal doğrulamayla "
        "sınamaktır. Kapsam üç başlıkta özetlenebilir:",
    )
    kit.bullet(
        document,
        "Yöntem tasarımı: örnekleme, vekil model kurulumu, duyarlılık analizi, çok "
        "amaçlı optimizasyon ve doğrulama adımlarının uçtan uca kurulması.",
    )
    kit.bullet(
        document,
        "ISO 50001 entegrasyonu: enerji taban çizgisinin tanımlanması, önemli enerji "
        "kullanımlarının belirlenmesi ve iklim normalizasyonu uygulanmış performans "
        "göstergelerinin hesaplanması.",
    )
    kit.bullet(
        document,
        "Sayısal doğrulama: Pareto cephesinden seçilen çözümlerin bağımsız "
        "EnergyPlus koşularıyla sınanması ve sapmaların raporlanması.",
    )

    kit.heading2(document, "1.2 Başlangıç Hipotezi")
    kit.body(
        document,
        "Proje, binanın enerji tüketiminin baskın biçimde dış duvar yalıtımının "
        "yetersizliğinden kaynaklandığı hipoteziyle kurgulanmıştır. Bu hipotez, ısı "
        "yalıtımının ülkemizdeki bina enerji verimliliği uygulamalarında en yaygın "
        "müdahale kalemi olmasıyla uyumludur. Raporun ilerleyen bölümlerinde "
        "gösterileceği üzere hipotez, bu bina için üç bağımsız kanıt hattıyla "
        "reddedilmiştir. Söz konusu red yöntemin başarısızlığı değil, aksine "
        "öngörülen işlevini yerine getirdiğinin göstergesidir: nicel duyarlılık "
        "analizi, sezgiyle kurulmuş bir tasarım varsayımını ölçülebilir biçimde "
        "çürütmüştür.",
    )


# --------------------------------------------------------------------------- #
# 2. Literatur ozeti
# --------------------------------------------------------------------------- #
def literature(document, facts: dict[str, Any]) -> None:
    kit.heading1(document, "2. Literatür Özeti")

    kit.heading2(document, "2.1 Simülasyon Tabanlı Bina Enerjisi Optimizasyonu")
    kit.body(
        document,
        "Bina performansı analizinde simülasyon tabanlı optimizasyon yöntemleri "
        "Nguyen vd. (2014) tarafından derlenmiştir. Derlemede, süreksiz ve çok tepeli "
        "arama uzaylarındaki dayanıklılıkları nedeniyle evrimsel algoritmaların en "
        "yaygın tercih olduğu belirtilmektedir. Çok amaçlı problemlerde baskın "
        "yöntem, Deb vd. (2002) tarafından önerilen NSGA-II algoritmasıdır; algoritma "
        "baskınlık sıralaması ile kalabalık mesafesi ölçütünü birleştirerek cephe "
        "boyunca dağılımı korur. Cephe kalitesinin ölçülmesinde Zitzler ve Thiele "
        "(1999) tarafından tanımlanan hipervolüm göstergesi kullanılmaktadır. "
        "Kullanılan yazılım uygulaması Blank ve Deb (2020) tarafından geliştirilen "
        "pymoo kütüphanesidir.",
    )

    kit.heading2(document, "2.2 Vekil Modeller")
    kit.body(
        document,
        "Sürdürülebilir bina tasarımında vekil modellerin kullanımı Westermann ve "
        "Evins (2019) tarafından derlenmiştir. Derleme, Gauss süreçleri (Kriging) ile "
        "yapay sinir ağlarının en sık kullanılan iki aile olduğunu, örneklem "
        "büyüklüğünün küçük olduğu durumlarda Kriging'in üstünlük sağladığını ortaya "
        "koymaktadır. Kriging'in kuramsal çerçevesi Rasmussen ve Williams (2006) "
        "tarafından verilmiştir. Yöntemin bu çalışma açısından kritik özelliği, "
        "yalnızca nokta tahmini değil tahmine ilişkin belirsizliği de üretmesidir. "
        "Jones vd. (1998), pahalı kara kutu fonksiyonlarının eniyilenmesinde bu "
        "belirsizliğin doğrudan kullanılabileceğini göstermiştir; söz konusu fikir bu "
        "projede, optimizasyonun vekil model hatasını sömürmesini engellemek üzere "
        "uyarlanmıştır.",
    )

    kit.heading2(document, "2.3 Duyarlılık Analizi")
    kit.body(
        document,
        "Varyans temelli küresel duyarlılık analizi Sobol (2001) tarafından "
        "tanımlanmış, toplam etki indislerinin verimli kestirimi için kullanılan "
        "örnekleme şeması Saltelli vd. (2010) tarafından geliştirilmiştir. Yöntem, "
        "model çıktısındaki varyansın hangi girdilere atfedilebileceğini girdiler "
        "arası etkileşimleri de hesaba katarak ayrıştırır. Bu özellik ISO 50001'in "
        "önemli enerji kullanımı kavramıyla doğrudan örtüşmektedir: her ikisi de "
        "sınırlı kaynağın en yüksek etkili kalemlere yönlendirilmesini hedefler.",
    )

    kit.heading2(document, "2.4 Standartlar ve Doğruluk Ölçütleri")
    kit.body(
        document,
        "TS EN ISO 50001 (2018) enerji yönetim sisteminin gereklerini, ISO 50006 "
        "(2023) ise enerji taban çizgisi ve performans göstergelerinin ölçüm "
        "esaslarını tanımlar. İkinci standart, göstergelerin karşılaştırılabilir "
        "olması için ilgili değişkenlere göre normalize edilmesini şart koşar; bina "
        "uygulamalarında bu değişken tipik olarak derece-gün sayısıdır. Simülasyon "
        "modellerinin ölçülmüş veriye kalibrasyonunda kabul ölçütleri ASHRAE "
        "Guideline 14 (2014) tarafından verilmektedir; bu çalışmada aynı "
        "istatistikler, yani değişim katsayılı kök ortalama kare hata (CVRMSE) ve "
        "normalize ortalama yanlılık hatası (NMBE), vekil model ile EnergyPlus "
        "arasındaki uyumun ölçülmesinde kullanılmıştır. Isı yalıtımına ilişkin "
        "ulusal sınır değerler TS 825 standardının EK 1-C çizelgesinde iklim "
        "bölgelerine göre "
        "tanımlanmıştır. Simülasyon motoru olarak kullanılan EnergyPlus, Crawley vd. "
        "(2001) tarafından tanıtılmıştır.",
    )

    kit.heading2(document, "2.5 Literatürdeki Boşluk")
    kit.body(
        document,
        "İncelenen çalışmaların büyük bölümünde vekil model, bağımsız bir test "
        "kümesindeki doğruluğu raporlandıktan sonra optimizasyonda doğrudan "
        "kullanılmakta; optimizasyon sonucu üretilen çözümlerin gerçek simülasyonla "
        "yeniden sınanması ise çoğunlukla atlanmaktadır. Oysa optimizasyon, arama "
        "uzayında vekil modelin ortalama olarak iyi çalıştığı bölgeleri değil, "
        "modelin iyimser tahmin ürettiği bölgeleri arar. Bu ayrım, ortalama model "
        "doğruluğunun tek başına yeterli bir güvence olmadığı anlamına gelir. Bu "
        "projede söz konusu boşluk hem ölçülmüş hem de giderilmiştir; ayrıntılar "
        "Bölüm 4.6 ve Bölüm 5.2'de sunulmaktadır.",
    )


# --------------------------------------------------------------------------- #
# 3. Gerec ve yontem
# --------------------------------------------------------------------------- #
def methods(document, facts: dict[str, Any]) -> None:
    dataset = facts["surrogate"]["dataset"]
    climate = facts["iso"]["climate"]

    kit.heading1(document, "3. Gereç ve Yöntem")

    kit.heading2(document, "3.1 Bina ve Simülasyon Modeli")
    kit.body(
        document,
        "Çalışmaya konu olan yapı, toplam 4.246,18 m² kapalı alana sahip bir kampüs "
        "binasıdır. Model 127 mekân, 1.310 yüzey ve 8 ısıl bölge içermektedir. "
        "Cephede 114 pencere bulunmakta olup toplam cam alanı 1.628,77 m², brüt duvar "
        "alanı 2.072,10 m²'dir; buna karşılık gelen cam-duvar oranı %78,61'dir. "
        "Isıtma ve soğutma yükleri altı bölgede dört borulu fan-coil üniteleriyle "
        "karşılanmakta, asansör boşluğu ile mekanik oda ise iklimlendirilmemektedir.",
    )
    kit.body(
        document,
        "Simülasyonlar OpenStudio 3.11.0 üzerinden EnergyPlus motoruyla, saatlik "
        "çözünürlükte ve 8.760 saatlik tam yıl için yürütülmüştür. İklim verisi "
        "olarak tipik meteorolojik yıl (TMYx) dosyası kullanılmıştır. Söz konusu "
        f"dosyadan hesaplanan ısıtma derece-gün sayısı (18 °C tabanlı) {tr(climate['hdd'], 1)}, "
        f"soğutma derece-gün sayısı (22 °C tabanlı) ise {tr(climate['cdd'], 1)}'dir.",
    )

    kit.heading2(document, "3.2 Model Onarımı ve Taban Çizgisinin Belirlenmesi")
    kit.body(
        document,
        "Devralınan model üzerinde yürütülen ilk koşu üç adet Severe düzeyinde hata "
        "üretmiştir. Optimizasyona geçilmeden önce bu hataların ve bunlara eşlik "
        "eden fiziksel tutarsızlıkların giderilmesi gerekmiştir; aksi hâlde tüm "
        "sonraki sonuçlar hatalı bir taban üzerine kurulmuş olurdu. Onarım işlemleri "
        "kaynak model üzerinde değil, ayrı bir çıktı dosyası üretilerek uygulanmış ve "
        "her değişiklik makinece okunabilir bir onarım raporuna kaydedilmiştir. "
        "Uygulanan dört düzeltme şunlardır:",
    )
    kit.bullet(
        document,
        "Asansör motoru yükü bir mekân tipine bağlı olduğu için dört ayrı asansör "
        "boşluğunda yeniden örneklenmiş ve toplam 20.000 W olarak uygulanmıştı; yük "
        "tek bir mekâna taşınarak 5.000 W değerine indirilmiştir.",
    )
    kit.bullet(
        document,
        "Havalandırması bulunmayan asansör boşluğuna 0,414 m³/s doğal havalandırma "
        "tanımlanmıştır; bölgenin yıllık ortalama sıcaklığı 88,0 °C seviyesinden "
        "21,2 °C seviyesine inmiştir.",
    )
    kit.bullet(
        document,
        "Hacimleri hesaplanamayan ve bu nedenle 10 m³ varsayılan değere düşen üç "
        "bölgenin hacimleri açıkça tanımlanmıştır. Severe hataların kaynağı budur.",
    )
    kit.bullet(
        document,
        "Hiçbir konstrüksiyonda kullanılmayan ve fiziksel olarak gerçekçi olmayan "
        "değerler taşıyan bir cam malzemesi modelden çıkarılmıştır.",
    )
    kit.body(
        document,
        "Onarım sonrası koşu sıfır Severe hata ile tamamlanmış ve bu koşu çalışmanın "
        "enerji taban çizgisi olarak kabul edilmiştir. Onarımın ölçülen etkisi "
        "Bölüm 4.1'de verilmiştir.",
    )

    kit.heading2(document, "3.3 Karar Değişkenleri ve Tasarım Uzayı")
    kit.body(
        document,
        "Tasarım uzayı, biri kategorik onu sürekli olmak üzere on bir karar "
        "değişkeninden oluşmaktadır. Değişkenler yedi ayrı OpenStudio measure "
        "aracılığıyla modele uygulanmaktadır; böylece her aday çözüm, elle müdahale "
        "olmaksızın çalıştırılabilir bir simülasyon iş akışına dönüştürülmektedir. "
        "Değişkenler, sınır değerleri ve taban çizgisindeki karşılıkları Tablo 3.1'de "
        "sunulmuştur.",
    )
    kit.table_caption(document, "Tablo 3.1. Karar değişkenleri ve tasarım uzayı")
    rows = []
    for spec in facts["design_space"]:
        if spec["type"] == "categorical":
            rng = f"{len(spec['choices'])} seçenek"
            base = str(spec["baseline"])
        else:
            rng = f"{tr(spec['minimum'], 3)} – {tr(spec['maximum'], 3)}"
            base = tr(float(spec["baseline"]), 3)
        rows.append([facts["labels"].get(spec["label"], spec["label"]),
                     spec["unit"] or "–", base, rng])
    kit.data_table(
        document,
        ["Karar değişkeni", "Birim", "Taban çizgisi", "Tarama aralığı"],
        rows,
        widths=[6.4, 2.0, 3.0, 4.1],
    )
    kit.body(
        document,
        "Isıtma ve soğutma ayar noktaları arasında asgari 0,5 K ölü bant bulunması "
        "koşulu, hem örnekleme hem de optimizasyon aşamasında zorlanmaktadır. Bu "
        "koşul sağlanmadığında EnergyPlus fiziksel olarak anlamsız bir kontrol "
        "durumuna girmektedir.",
    )

    kit.heading2(document, "3.4 Deney Tasarımı")
    kit.body(
        document,
        "Eğitim kümesi, Sobol düşük tutarsızlıklı dizisiyle üretilmiştir. Düşük "
        "tutarsızlıklı diziler, aynı örneklem büyüklüğünde rastgele örneklemeye "
        "kıyasla tasarım uzayını daha düzgün tarar ve vekil model doğruluğunu "
        "artırır. Taban çizgisine karşılık gelen nokta daima kümenin ilk elemanı "
        f"olarak yer almaktadır. Başlangıçta {dataset['rows'] - 24} nokta üretilmiş, "
        "adaptif örnekleme turlarında doğrulama noktaları eğitim kümesine eklenerek "
        f"küme {dataset['rows']} satıra çıkarılmıştır.",
    )
    kit.body(
        document,
        "Her koşunun eksiksiz tamamlandığı, EnergyPlus çıktı dosyasındaki tamamlanma "
        "kaydı üzerinden denetlenmektedir. Yarım kalan koşular hasat edilmemekte, "
        "böylece sıfır enerjili yapay satırların eğitim kümesini kirletmesi "
        "engellenmektedir.",
    )

    kit.heading2(document, "3.5 Vekil Model Kurulumu")
    kit.body(
        document,
        "Her hedef değişken için üç aday model yarıştırılmıştır: sırt regresyonuyla "
        "düzenlileştirilmiş polinom modeli, Matérn çekirdekli Gauss süreci (Kriging) "
        "ve histogram tabanlı gradyan artırma. Model seçimi çapraz doğrulama "
        f"başarımına göre yapılmakta, seçilen model {dataset['test_rows']} satırlık "
        "bağımsız bir test kümesinde sınanmaktadır.",
    )
    kit.body(
        document,
        "Ham karar değişkenlerine ek olarak fiziğe dayalı türetilmiş öznitelikler "
        "tanımlanmıştır: chiller COP ve kazan veriminin çarpmaya göre tersleri, "
        "katman kalınlığı ile ısıl iletkenlikten hesaplanan duvar U değeri ve ayar "
        "noktaları arasındaki ölü bant. Bu öznitelikler, enerji tüketiminin söz "
        "konusu büyüklüklerle doğrusal değil ters orantılı ilişkisini modele "
        "doğrudan aktarmaktadır. Türetilmiş özniteliklerin eklenmesi, toplam saha "
        "enerjisi hedefindeki CVRMSE değerini %14,65 seviyesinden %6,19 seviyesine "
        "indirmiştir. Kategorik cam tipi değişkeni birebir kodlama ile "
        f"sayısallaştırılmakta, toplam öznitelik sayısı {dataset['features']} "
        "olmaktadır.",
    )
    kit.body(
        document,
        "Doğruluk ölçütü hedefin dağılımına göre seçilmektedir. Yoğun dağılımlı "
        "hedeflerde ASHRAE Guideline 14 uyarınca CVRMSE kullanılmaktadır. Buna "
        "karşılık ısıtma enerjisi ve konfor ihlali gibi değerlerin büyük bölümünün "
        "sıfıra yakın olduğu seyrek hedeflerde CVRMSE, ortalamanın küçüklüğü "
        "nedeniyle yanıltıcı biçimde büyümektedir; bu hedeflerde değer aralığına "
        "göre normalize edilmiş kök ortalama kare hata ile belirlilik katsayısı "
        "birlikte kullanılmaktadır.",
    )

    kit.heading2(document, "3.6 Duyarlılık Analizi")
    kit.body(
        document,
        "Küresel duyarlılık analizi, eğitilmiş vekil model üzerinde Saltelli "
        "örnekleme şemasıyla yürütülmüştür. Her karar değişkeni için birinci mertebe "
        "indisi ve toplam etki indisi hesaplanmaktadır. Birinci mertebe indisi, "
        "değişkenin tek başına açıkladığı varyans payını; toplam etki indisi ise "
        "değişkenin diğer değişkenlerle etkileşimleri dâhil toplam katkısını verir. "
        "Analizin vekil model üzerinde yürütülmesi, doğrudan EnergyPlus ile "
        "yapılması hâlinde gereken on binlerce koşuyu gereksiz kılmaktadır.",
    )

    kit.heading2(document, "3.7 ISO 50001 Çerçevesinin Uygulanması")
    kit.body(
        document,
        "Enerji taban çizgisi, onarım sonrası referans koşusundan türetilmiştir. "
        "Önemli enerji kullanımları, son kullanım kalemleri büyükten küçüğe "
        "sıralanarak kümülatif payın %80 eşiğini aştığı noktaya kadar olan kalemler "
        "olarak belirlenmiştir. Enerji performans göstergeleri birim alan başına "
        "yıllık enerji, kişi başına yıllık enerji ve derece-gün normalize gösterge "
        "olmak üzere üç düzeyde hesaplanmıştır. Derece-gün değerleri, iklim "
        "dosyasındaki saatlik kuru termometre sıcaklıklarından doğrudan "
        "hesaplanmaktadır.",
    )
    kit.body(
        document,
        "Taban çizgisinin simülasyon kaynaklı olduğu ve ölçülmüş fatura verisine "
        "kalibre edilmediği, üretilen raporda makinece okunabilir bir alanla açıkça "
        "işaretlenmiştir. Bu ayrım, ISO 50001 kapsamında bir doğrulama iddiasında "
        "bulunulmadığının kaydıdır.",
    )

    kit.heading2(document, "3.8 Çok Amaçlı Optimizasyon")
    kit.body(
        document,
        "Optimizasyon problemi üç amaç ve beş eşitsizlik kısıtı ile "
        "tanımlanmıştır. Amaçlar enerji performans göstergesi, yatırım maliyeti ve "
        "konfor ihlali süresidir. Kısıtlar Tablo 3.2'de verilmiştir. Problem, karma "
        "değişken desteğine sahip NSGA-II uygulamasıyla çözülmüştür.",
    )
    kit.table_caption(document, "Tablo 3.2. Amaç fonksiyonları ve kısıtlar")
    kit.data_table(
        document,
        ["Tür", "Tanım", "Yön / sınır"],
        [
            ["Amaç 1", "Enerji performans göstergesi (EnPİ)", "en küçükle"],
            ["Amaç 2", "Yatırım maliyeti", "en küçükle"],
            ["Amaç 3", "Konfor ihlali süresi", "en küçükle"],
            ["Kısıt 1", "TS 825 dış duvar ısı geçirgenlik katsayısı", "≤ 0,50 W/m²K"],
            ["Kısıt 2", "TS 825 cam ısı geçirgenlik katsayısı", "≤ 2,80 W/m²K"],
            ["Kısıt 3", "Konfor ihlali tavanı", "üst sınır"],
            ["Kısıt 4", "Yatırım bütçesi tavanı", "üst sınır"],
            ["Kısıt 5", "Asgari ölü bant", "≥ 0,5 K"],
        ],
        widths=[2.4, 8.1, 5.0],
    )
    kit.body(
        document,
        "Konfor amacı hesaplanırken iklimlendirilmeyen iki bölge kapsam dışı "
        "bırakılmıştır. Bu bölgelerde ısıtma ve soğutma cihazı bulunmadığından iç "
        "sıcaklıkları dış hava sıcaklığını izlemektedir; söz konusu davranış bir "
        "kusur değil, doğru fiziksel sonuçtur ve konfor ölçütüne dâhil edilmesi "
        "yanıltıcı olurdu.",
    )
    kit.body(
        document,
        "Cephe kalitesi hipervolüm göstergesiyle izlenmiştir. Aday çözümler "
        "arasından tezde önerilecek tek bir uzlaşı çözümünün belirlenmesinde, Hwang "
        "ve Yoon (1981) tarafından tanımlanan TOPSIS yöntemi kullanılmıştır.",
    )

    kit.heading2(document, "3.9 Doğrulama Protokolü")
    kit.body(
        document,
        "Doğrulama noktalarının seçimi rastgele değildir; üç kural birlikte "
        "uygulanmaktadır. Birincisi, her amacın uç noktası seçilir; vekil model "
        "cephenin kenarlarında en çok zorlanır. İkincisi, TOPSIS uzlaşı çözümü "
        "mutlaka doğrulanır; önerilecek çözüm budur. Üçüncüsü, cephenin orta "
        "bölgesinin de temsil edilmesi için maksimin ölçütüyle dağılım noktaları "
        "eklenir.",
    )
    kit.body(
        document,
        "Eğitim kümesinde yer alan çözümler aday havuzundan çıkarılmaktadır. Bu "
        "kural adaptif örnekleme turlarında zorunludur: önceki turun doğrulama "
        "noktaları eğitim kümesine eklendiğinden, yeniden seçilmeleri hâlinde "
        "doğrulama dairesel hâle gelir ve modelin gerçek hatası yerine ezberi "
        "ölçülür. Sapma işareti tanımlıdır; pozitif değer vekil modelin fazla "
        "tahmin ettiğini gösterir. Kabul ölçütü, her doğrulama noktasında mutlak "
        "sapmanın %5 altında kalmasıdır.",
    )
