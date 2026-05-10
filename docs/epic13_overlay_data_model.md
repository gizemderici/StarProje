# EPIC 13.2 Overlay Grafik Veri Modeli

Bu backlog, birden fazla cizgiyi ayni grafikte gosterecek ortak veri modelini tanimlar.

## Ortak Veri Modeli

Model dosyasi: [overlay_chart_model.py](../overlay_chart_model.py)

Veri yapisi alanlari:
- chart_name: grafik adi
- x_labels: x ekseni etiketleri
- series: cizgi listesi

Her cizgi icin:
- name: cizgi adi
- data: cizgi veri serisi
- line_type: cizgi tipi (line, area, step)
- color: cizgi rengi
- line_style: cizgi stili (solid, dashed, dotted)
- origin: baz mi, senaryo mu, varyant mi (base, scenario, variant)

## Hedeflenen Uretim Senaryolari
- 2 cizgili grafik: base + scenario
- 3 cizgili grafik: base + scenario A + scenario B
- coklu senaryo grafik: base + n adet varyant

## Beklenen Faydalar
- Tum overlay grafikler tek model uzerinden uretilebilir.
- EChart gibi farkli cizim katmanlarina tek noktadan donusum yapilabilir.
- UI katmaninda metrik bazli kod tekrarini azaltir.
