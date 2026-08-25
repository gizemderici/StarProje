# Faz 1 için Ölçülmüş Bulgular

Bu belgedeki her sayı `data/reference_run/` içindeki 7 Mayıs 2026 koşusundan
doğrudan okunmuştur. Faz 1 işleri bu bulguları kapatmak üzere tanımlanmıştır.

## 1.1 — Asansör iç yükü

`TZ_ASNSR` zonunda **dört ayrı** `ElectricEquipment` kaydı var; `asansor motoru`
tanımı her katın asansör mekânına ayrı ayrı bağlanmış:

| Mekân | Güç | Program |
|---|---|---|
| `KB_ASNS_7` | 5.000 W | `ELEKTRIK EKIPMAN` |
| `KZ_ASN_18` | 5.000 W | `ELEKTRIK EKIPMAN` |
| `K1_ASNS_1` | 5.000 W | `ELEKTRIK EKIPMAN` |
| `K2_ASNS_1` | 5.000 W | `ELEKTRIK EKIPMAN` |
| **Toplam** | **20.000 W** | 38,28 m² → **522 W/m²** |

**Program eksik değildir.** `.osm` içinde `Electric Equipment 1` nesnesinin
`Schedule Name` alanı boş görünür, ancak SpaceType'ın varsayılan program seti
`ELEKTRIK EKIPMAN` programını sağlar. Yıllık tam yük eşdeğeri 3.247 saattir.

Sonuç: **233,78 GJ/yıl**, binanın toplam iç ekipman tüketiminin **%54,0'ı**.
Karşılaştırma için binanın en büyük zonu `TZ_ATOLYE` (1.227,64 m²) 170,69 GJ
tüketiyor. Asansör boşluğu, zemin alanının %0,9'unu kaplamasına rağmen en çok
elektrik tüketen zondur.

**Yapılacak:** Tek bir asansör kabini dört kez sayılmış olabilir; ayrıca 5.000 W
bir asansör motoru için tepe gücüdür, sürekli bağlı yük değildir. Gerçek asansör
sayısı ve motor gücü doğrulanıp tanım tek mekâna indirilmelidir.

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

Zon sıcaklıkları yıl boyunca 22,0–24,3 °C bandında. Ölü bant yaklaşık 2 K.
`Time Setpoint Not Met During Occupied Cooling` yalnızca 2,50 saat; buna karşın
`Time Not Comfortable Based on Simple ASHRAE 55-2004` **3.253,50 saat**
(yılın %37'si). İki gösterge çelişiyor; 1.1–1.2 kapatıldıktan sonra yeniden
ölçülmelidir.

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
