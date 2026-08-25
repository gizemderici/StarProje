# Faz 1 için Ölçülmüş Bulgular

Bu belgedeki her sayı `data/reference_run/` içindeki 7 Mayıs 2026 koşusundan
doğrudan okunmuştur. Faz 1 işleri bu bulguları kapatmak üzere tanımlanmıştır.

## 1.1 — Asansör iç yükü

OpenStudio SDK ile doğrulanan mekanizma: modelde **tek bir** `OS:ElectricEquipment`
nesnesi var (`Electric Equipment 1`, tanım `asansor motoru`, 5.000 W), ancak bu
nesne bir mekâna değil **`asnsr` SpaceType'ına** bağlı.

O SpaceType'a dört mekân ait — her kattan bir asansör boşluğu:

| Mekân | Kat |
|---|---|
| `KB_ASNS_7` | bodrum |
| `KZ_ASN_18` | zemin |
| `K1_ASNS_1` | 1. kat |
| `K2_ASNS_1` | 2. kat |

EnergyPlus, SpaceType'a bağlı yükü her mekânda ayrı ayrı örnekler. Sonuç:
**4 x 5.000 W = 20.000 W**, 38,28 m²'lik bölgede **522 W/m²**.

**Program eksik değildir.** `.osm` içinde `Schedule Name` alanı boş görünür,
ancak SpaceType'ın varsayılan program seti `ELEKTRIK EKIPMAN` programını sağlar;
yıllık tam yük eşdeğeri 3.247 saattir.

Ölçülen sonuç: **233,78 GJ/yıl**, binanın toplam iç ekipman tüketiminin
**%54,0'ı**. Karşılaştırma için binanın en büyük bölgesi `TZ_atolye` (1.227,64 m²)
170,69 GJ tüketiyor. Asansör boşluğu, zemin alanının %0,9'unu kaplamasına rağmen
en çok elektrik tüketen bölgedir.

**Uygulanan onarım:** Ekipman SpaceType'tan alınıp tek bir mekâna (`K2_ASNS_1`)
bağlandı; toplam 20.000 W'tan 5.000 W'a indi. Kabul ve doğrulanması gereken
noktalar: `docs/baseline_assumptions.md`.

## 1.2 — TZ_ASNSR sıcaklığı

`hourly_zone.csv` üzerinden 8.760 saatlik istatistik:

| Zon | min °C | ortalama °C | max °C | 20–26 °C dışı saat |
|---|---|---|---|---|
| **`TZ_ASNSR`** | **58,9** | **88,0** | **122,1** | **8.760 / 8.760** |
| `TZ_MECODA` | 19,2 | 23,2 | 26,4 | 106 |
| `TZ_WC` | 22,0 | 24,0 | 26,5 | 2 |
| `TZ_ATOLYE` | 22,0 | 23,9 | 24,0 | 0 |
| `TZ_KONFSALON` | 22,0 | 23,4 | 24,0 | 0 |
| `TZ_KORIDOR` | 22,0 | 23,7 | 24,0 | 0 |
| `TZ_MERDVN` | 22,0 | 23,8 | 24,2 | 0 |
| `TZ_ODA` | 22,0 | 23,7 | 24,3 | 0 |

38 m²'lik havalandırmasız bir boşlukta 20 kW ısı, 88 °C ortalamayı açıklıyor.
Bu zon komşularına iç yüzeylerden ısı aktardığı için 1.173,86 GJ'lik soğutma
sonucu 1.1 ve 1.2 kapatılmadan kullanılmamalıdır.

## 1.3 — Severe hatalar

`eplusout.err` içinde 3 Severe, 828 uyarı:

```
** Severe ** For zone: TZ_ATOLYE  ... not possible to calculate the volume ...
** Severe ** For zone: TZ_KORIDOR ... not possible to calculate the volume ...
** Severe ** For zone: TZ_WC      ... not possible to calculate the volume ...
```

Üç zon da 10 m³ varsayılan hacme düşüyor; infiltrasyon ve zon hava kapasitesi
yanlış hesaplanıyor.

## 1.4 — Ayar noktaları

Sekiz bölgenin **tamamı** aynı iki sabit programı kullanıyor:

| Program | Değer | Değişim |
|---|---|---|
| `heating setpoint` | 22,0 °C | yıl boyunca sabit |
| `cooling setpoint` | 24,0 °C | yıl boyunca sabit |

İki bulgu:

1. Ölü bant yalnızca **2 K**. Tipik ofis uygulaması 20/26 (6 K) civarındadır.
2. **Gece ve hafta sonu geri çekmesi yok.** Bina boşken de aynı ayar noktası
   korunuyor.

İkisi de yatırım gerektirmeyen işletme önlemidir; Faz 3'te karar değişkeni
olarak taranacaktır.

### İki bölgede HVAC cihazı yok

`TZ_asnsr` ve `TZ_mecoda` bölgelerinin termostatı var ancak `ZoneHVAC` cihazı
**sıfır**. Diğer altı bölgede `ZoneHVAC:FourPipeFanCoil` bulunuyor. Ayar noktası
tanımlı olduğu halde onu karşılayacak ekipman olmadığı için sıcaklıkları serbest
yüzüyor — `TZ_asnsr`'daki 88 °C'nin doğrudan sebebi budur.

`Time Setpoint Not Met During Occupied Cooling` yalnızca 2,50 saat görünürken
`Time Not Comfortable Based on Simple ASHRAE 55-2004` **3.253,50 saat**
(yılın %37'si) olması bu çelişkiden kaynaklanıyor.

## 1.5 — Kullanılmayan nesneler

`Window Material Simple Glazing System 1`: U = 0,1 W/m²K ve SHGC = 0,1.
Bu değerler hiçbir gerçek camda görülmez ve nesne **hiçbir konstrüksiyonda
kullanılmıyor**. Yanlışlıkla bir senaryoya girerse sonucu sessizce bozar.

## Faz 2 için hazır bekleyen fırsat

Modelde yedi tam tanımlı pencere konstrüksiyonu var; bina 114 pencerenin
hepsinde bunların en zayıfını kullanıyor:

| Konstrüksiyon | Katmanlar | Durum |
|---|---|---|
| `penc_std_4mm` | 4mm + 12mm hava + 4mm | **kullanımda (114 pencere)** |
| `penc_lowe_4mm` | 4mm + 12mm hava + 4mm Low-E | kullanılmamış |
| `penc_lowe_argon_4mm` | 4mm + 16mm argon + 4mm Low-E | kullanılmamış |
| `penc_cont_6_4mm` | 6mm control + 12mm hava + 4mm | kullanılmamış |
| `penc_triple_lowe_4mm` | üçlü cam, 2x argon 12mm, 2x Low-E | kullanılmamış |
| `penc_snerji_4mm` | 4mm + 16mm argon + konfor sinerji | kullanılmamış |
| `penc_renk_6mm` | 6mm + 16mm hava + 6mm renkli gri | kullanılmamış |

Cam/duvar oranı %78,61 (2.072,10 m² duvar, 1.628,77 m² cam) ve soğutma toplam
tüketimin %55,1'i olduğu için en yüksek kaldıraç buradadır.

---

# Faz 1 Sonucu — uygulanan onarımlar ve ölçülen etki

Onarım betiği: `integrations/OpenStudio/model_repair_worker.py`
Kaynak model değiştirilmez; çıktı `data/input/gsf_fng_6mayis_onarilmis.osm`.
Her değişiklik `data/input/onarim_raporu.json` dosyasına dökülür.

| İş | Uygulanan değişiklik |
|---|---|
| 1.1 | `Electric Equipment 1`, `asnsr` SpaceType'ından alınıp `K2_ASNS_1` mekânına bağlandı: 20.000 W → 5.000 W |
| 1.2 | `TZ_asnsr` bölgesine doğal havalandırma eklendi: 0,414 m³/s, fan enerjisi yok |
| 1.3 | `TZ_atolye` (3.682,92 m³), `TZ_koridor` (3.860,67 m³), `TZ_WC` (516,66 m³) hacimleri açıkça yazıldı |
| 1.5 | `Window Material Simple Glazing System 1` (U=0,1 · SHGC=0,1) silindi |

## Ölçülen etki

| Gösterge | Önce | Sonra |
|---|---|---|
| **Severe hata** | **3** | **0** |
| Toplam saha enerjisi | 2.128,85 GJ | **1.920,00 GJ** |
| EUI | 501,36 MJ/m² | **452,17 MJ/m²** |
| İç ekipman | 433,16 GJ | **261,13 GJ** |
| Soğutma | 1.173,86 GJ | **1.119,56 GJ** |
| Isıtma | 30,95 GJ | **46,20 GJ** |
| ASHRAE 55 konforsuz saat | 3.253,50 | **494,83** |
| `TZ_ASNSR` ortalama sıcaklık | 88,0 °C | **21,2 °C** |
| `TZ_ASNSR` tepe sıcaklık | 122,1 °C | **39,9 °C** |

Isıtmanın artması beklenen sonuçtur: asansörün hayalî ısı kazancı kalktı ve kuyu
havalandırması ısı atıyor.

Taban çizgisinin tam sonuçları: `data/baseline_v1/README.md`.

## Faz 1'den çıkan iki yeni bulgu

**1. Konfor metriği iklimlendirilmeyen bölgeleri dışlamalı.** `TZ_asnsr` ve
`TZ_mecoda` bölgelerinin ZoneHVAC cihazı yok. `TZ_ASNSR` onarım sonrası
dış hava sıcaklığını izliyor (min 11,2 · ortalama 21,2 · max 39,9 °C); kalan
7.049 ihlal saatinin 5.261'i soğuk taraftadır. Bu doğru fiziksel davranıştır,
kusur değildir. Faz 4 ve Faz 6'daki konfor amaç fonksiyonu bu iki bölgeyi
dışlamalıdır.

**2. Chiller kışın çalışıyor.** Koşudaki 1.504 uyarının neredeyse tamamı tek bir
yinelenen mesaj: hava soğutmalı chiller, dış hava 0 °C'nin altındayken devrede.
Sebep ayar noktalarıdır — sekiz bölge de sabit 22/24 °C kullanıyor, ölü bant
2 K ve gece/hafta sonu geri çekmesi yok. Yüksek cam oranıyla birlikte bu, kış
aylarında bile mekanik soğutma çağırıyor. Ölü bandı genişletmek Faz 3'ün en
yüksek getirili **yatırımsız** senaryosu olabilir.
