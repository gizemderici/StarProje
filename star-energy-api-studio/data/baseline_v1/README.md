# Taban Çizgisi v1 — Faz 1 onarımı sonrası

Bu koşu, tezin **enerji taban çizgisidir (EnB)**.

| | |
|---|---|
| Model | `data/input/gsf_fng_6mayis_onarilmis.osm` |
| Hava verisi | `data/input/weather_tmyx.epw` (Muğla TMYx 2009–2023) |
| İş akışı | `workflow.osw` — `CreateCSVOutput`, `OpenStudioResults` |
| OpenStudio | 3.11.0 |
| Süre | 3 dk 7 sn |
| **Severe hata** | **0** |
| Uyarı | 1.504 (neredeyse tamamı tek yinelenen chiller mesajı) |

Onarım ayrıntıları: `data/input/onarim_raporu.json` ve `docs/bulgular_faz1.md`.
Varsayımlar: `docs/baseline_assumptions.md`.

## Referans koşuya göre değişim

| Kalem (GJ/yıl) | Referans (onarımsız) | **Taban v1** | Fark |
|---|---|---|---|
| Soğutma (elektrik) | 1.173,86 | **1.119,56** | −54,30 |
| İç ekipman (elektrik) | 433,16 | **261,13** | −172,03 |
| Fanlar (elektrik) | 239,52 | **239,90** | +0,38 |
| İç aydınlatma (elektrik) | 230,27 | **230,27** | 0,00 |
| Pompalar (elektrik) | 21,11 | **22,95** | +1,84 |
| Isıtma (doğalgaz) | 30,95 | **46,20** | +15,25 |
| **Toplam saha enerjisi** | 2.128,85 | **1.920,00** | −208,85 |
| **EUI (MJ/m²·yıl)** | 501,36 | **452,17** | −49,19 |
| ASHRAE 55 konforsuz saat | 3.253,50 | **494,83** | −2.758,67 |
| Severe hata | 3 | **0** | −3 |

### İç ekipman düşüşü bağımsız olarak doğrulandı

Asansör onarımı iç ekipmanı 433,16 → **261,13 GJ**'ye indirdi. Bu değer,
`data/archived_runs` içindeki eski koşunun iç ekipman değeriyle **birebir
aynıdır**. Eski modelde asansör motoru tek bir mekâna bağlıymış; bir noktada
`asnsr` SpaceType'ına taşınmış ve dört kez sayılır hale gelmiş. Onarım orijinal
doğru değeri geri getirdi.

## Bölge sıcaklıkları

| Bölge | ortalama °C | max °C | 20–26 °C dışı saat |
|---|---|---|---|
| `TZ_ASNSR` | 21,2 | 39,9 | 7.049 |
| `TZ_ATOLYE` | 23,8 | 24,2 | 0 |
| `TZ_KONFSALON` | 23,4 | 24,0 | 0 |
| `TZ_KORIDOR` | 23,7 | 24,0 | 0 |
| `TZ_MECODA` | 23,1 | 26,4 | 115 |
| `TZ_MERDVN` | 23,5 | 24,2 | 0 |
| `TZ_ODA` | 23,7 | 24,3 | 0 |
| `TZ_WC` | 24,0 | 26,0 | 1 |

`TZ_ASNSR` onarım öncesinde 88,0 °C ortalama ve 122,1 °C tepe değerindeydi.

### Konfor metriği iklimlendirilmeyen bölgeleri dışlamalıdır

`TZ_ASNSR` dağılımı: min 11,2 · ortalama 21,2 · max 39,9 °C. İhlallerin
5.261 saati **soğuk** taraftadır (< 20 °C), 1.788 saati sıcak taraftadır.

Bu doğru davranıştır: bölge iklimlendirilmiyor ve doğal havalandırmayla dış hava
sıcaklığını izliyor. Dolayısıyla **Faz 4 ve Faz 6'daki konfor amaç fonksiyonu
`TZ_ASNSR` ve `TZ_MECODA` bölgelerini dışlamalıdır** — ikisinin de ZoneHVAC
cihazı yoktur.

## Faz 3 için gözlem: chiller kışın çalışıyor

1.504 uyarının neredeyse tamamı tek bir yinelenen mesajdır: hava soğutmalı
chiller, dış hava sıcaklığı 0 °C'nin altındayken devrede.

Sebebi ayar noktalarıdır: sekiz bölgenin tamamı sabit 22/24 °C kullanıyor,
ölü bant yalnızca 2 K ve gece/hafta sonu geri çekmesi yok. Yüksek cam oranıyla
birlikte bu, kış aylarında bile mekanik soğutma çağırıyor.

Ölü bandı genişletmek Faz 3'ün en yüksek getirili, **yatırımsız** senaryosu
olabilir.
