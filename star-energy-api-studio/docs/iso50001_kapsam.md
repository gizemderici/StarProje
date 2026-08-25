# ISO 50001 Kapsamı ve Göstergeler

Bu belge, standardın istediği dört nesneyi tanımlar: önemli enerji kullanımı
(SEU), enerji taban çizgisi (EnB), enerji performans göstergeleri (EnPI) ve
normalizasyon değişkenleri.

Kod karşılığı: `iso50001/` — `seu.py`, `enpi.py`, `normalization.py`.
Raporu üreten betik: `build_iso50001_report.py`.
Makine okunur çıktı: `data/iso50001/iso50001_report.json`.

---

## 1. Önemli enerji kullanımı (SEU)

Ölçüt: son kullanımlar büyükten küçüğe sıralanır, kümülatif pay **%80** eşiğine
ulaşana kadar olanlar SEU sayılır. ISO 50001 sayısal bir eşik dayatmaz;
kuruluşun ölçütü tanımlamasını ister.

Kaynak: `data/baseline_v1` taban koşusu.

| Son kullanım | GJ/yıl | Pay | Kümülatif | SEU |
|---|---|---|---|---|
| **Soğutma** | 1.119,56 | %58,3 | %58,3 | ✔ |
| **İç ekipman** | 261,13 | %13,6 | %71,9 | ✔ |
| **Fanlar** | 239,90 | %12,5 | %84,4 | ✔ |
| İç aydınlatma | 230,27 | %12,0 | %96,4 | |
| Isıtma | 46,20 | %2,4 | %98,8 | |
| Pompalar | 22,95 | %1,2 | %100,0 | |

**SEU kapsamı: soğutma, iç ekipman, fanlar — toplam %84,4.**

### Bu tablonun tez açısından anlamı

Isıtma toplamın **%2,4'ü**. Duvar yalıtımı kalınlığını optimize etmek, tüketimin
yüzde birkaçını hedeflemek demektir. Çalışmanın ağırlığı soğutma tarafına —
cam, gölgeleme, ayar noktası ve chiller verimine — kaymalıdır.

İç ekipmanın %13,6 ile ikinci sırada olması da dikkat çekicidir; bunun içinde
asansör yükü belirleyici paya sahiptir (bkz. `docs/bulgular_faz1.md`).

---

## 2. Enerji taban çizgisi (EnB)

| | |
|---|---|
| Kaynak | `data/baseline_v1` — Faz 1 onarımı sonrası taban koşusu |
| Saha enerjisi | **1.920,00 GJ/yıl** (533.333 kWh/yıl) |
| Toplam alan | 4.246,18 m² |
| Doluluk | 201,74 kişi (0,05383 kişi/m²) |
| Hava verisi | Muğla TMYx 2009–2023 |
| **Ölçülmüş mü** | **HAYIR** |

### Sınırlılık beyanı

> Bu çalışmada enerji taban çizgisi, ölçülmüş tüketime değil **onarılmış
> simülasyon modeline** dayanmaktadır. Elde 12 aylık fatura veya sayaç verisi
> bulunmadığından model ASHRAE Guideline 14 ölçütlerine (NMBE ≤ %5,
> CVRMSE ≤ %15) göre kalibre edilememiştir.
>
> Bu nedenle mutlak tüketim değerleri değil, senaryolar arası **göreli**
> değişimler yorumlanmıştır. Yöntemin saha verisiyle kalibrasyonu sonraki
> çalışmaya bırakılmıştır.

Bu, optimizasyon çalışmasını geçersiz kılmaz: çok amaçlı optimizasyon zaten
göreli karşılaştırma üzerine kuruludur. Ancak tezde açıkça beyan edilmelidir.

Modelin bilinen varsayımları: `docs/baseline_assumptions.md`.

---

## 3. Normalizasyon değişkenleri

Derece-günler doğrudan `data/input/weather_tmyx.epw` dosyasının 8.760 saatlik
kuru termometre sütunundan hesaplanır; dış veri gerekmez.

Saatlik yöntem kullanılır. Günlük ortalamaya göre daha doğrudur: geçiş
mevsimlerinde gün içinde hem ısıtma hem soğutma ihtiyacı doğar, günlük ortalama
ikisini de gizler.

| Gösterge | Değer |
|---|---|
| HDD (taban 18 °C) | **1.782,5** |
| CDD (taban 22 °C) | **557,5** |
| Yıllık ortalama sıcaklık | 15,99 °C |

### Aylık dağılım

| Ay | HDD | CDD | | Ay | HDD | CDD |
|---|---|---|---|---|---|---|
| Ocak | 372,8 | 0,0 | | Temmuz | 0,0 | 190,0 |
| Şubat | 301,5 | 0,0 | | Ağustos | 0,2 | 171,7 |
| Mart | 278,7 | 0,0 | | Eylül | 6,7 | 71,9 |
| Nisan | 150,1 | 10,2 | | Ekim | 96,3 | 12,1 |
| Mayıs | 78,3 | 24,9 | | Kasım | 189,2 | 1,6 |
| Haziran | 11,3 | 75,1 | | Aralık | 297,5 | 0,0 |

### İklim–bina çelişkisi

**İklim ısıtma ağırlıklı, bina soğutma ağırlıklı.** HDD (1.782,5), CDD'nin
(557,5) üç katından fazla. Buna karşın binada soğutma %58,3, ısıtma %2,4.

Muğla 646 m rakımda, iç kesimde; kışları belirgin biçimde soğuk. Binanın buna
rağmen soğutma ağırlıklı olmasının üç sebebi var:

1. **Cam/duvar oranı %78,61** — güneş kazancı baskın.
2. **İç kazançlar** — aydınlatma 230 GJ + ekipman 261 GJ, ikisi de yıl boyu ısı.
3. **Soğutma ayar noktası 24 °C, ölü bant yalnızca 2 K** — chiller kışın bile
   devreye giriyor (bkz. `docs/bulgular_faz1.md`).

Bu çelişki tezin tartışma bölümü için değerli bir bulgudur: iklim verisine
bakarak yalıtım odaklı bir müdahale seçmek yanıltıcı olurdu.

---

## 4. Enerji performans göstergeleri (EnPI)

Taban çizgisi değerleri:

| Gösterge | Değer | Birim |
|---|---|---|
| Birim alan başına yıllık enerji | **125,603** | kWh/m²·yıl |
| Kişi başına yıllık enerji | **2.643,667** | kWh/kişi·yıl |
| Derece-gün normalize gösterge | **0,054** | kWh/m²·DG |

Derece-gün normalize gösterge bu çalışmada senaryoları birbirinden ayırmaz,
çünkü tüm senaryolar aynı EPW dosyasını kullanır. Yine de hesaplanır: farklı
hava yıllarıyla veya başka bir binayla karşılaştırma yapıldığında ISO 50006'nın
istediği normalizasyon budur.

---

## 5. Senaryo değerlendirmesi

`data/parametric/results.csv` hazır olduğunda `build_iso50001_report.py` her
senaryo için taban çizgisine göre mutlak ve yüzde iyileşmeyi hesaplar; sonuç
`data/iso50001/iso50001_report.json` içindeki `scenarios` dizisine yazılır.

Bu değerler Faz 6'daki çok amaçlı optimizasyonun birinci amaç fonksiyonunu
(EnPI) besler.
