# Taban Çizgisi Varsayımları

Model gerçek fatura verisiyle **kalibre edilmemiştir**. Bu belge, sonuçların
hangi kabuller üzerine kurulduğunu tek yerde toplar. Tezin sınırlılıklar bölümü
buradan yazılacaktır.

Tüm değerler `data/input/gsf_fng_6mayis_onarilmis.osm` modelinden OpenStudio SDK
ile doğrudan okunmuştur.

## Bina

| Büyüklük | Değer | Kaynak |
|---|---|---|
| Toplam bina alanı | 4.246,18 m² | `Building Area` tablosu |
| İklimlendirilen alan | 4.120,62 m² | `Building Area` tablosu |
| Yüzey sayısı | 1.310 | `OS:Surface` |
| Mekân sayısı | 127 | `OS:Space` |
| Isıl bölge sayısı | 8 | `OS:ThermalZone` |
| Cam/duvar oranı | %78,61 | 2.072,10 m² duvar, 1.628,77 m² cam |
| Hava verisi | Muğla TMYx 2009–2023 | `weather_tmyx.epw` |

**Not:** 127 mekân yalnızca 8 ısıl bölgeye toplanmıştır. Bu, 4.246 m²'lik bir
bina için kaba bir bölgeleme sayılır; ısıtma ve soğutma yüklerinin mekân bazında
ayrışması sınırlıdır.

## Isıl ekipman

| Parametre | Değer | Nesne |
|---|---|---|
| Chiller COP | **5,5** | `Chiller:Electric:EIR` — Chiller - Air Cooled, hava soğutmalı, autosize |
| Kazan verimi | **0,90** | `Boiler:HotWater` — HW Boiler |
| Bölge cihazı | 4 borulu fan-coil | `ZoneHVAC:FourPipeFanCoil` (6 bölgede) |
| Plant devresi | 2 | sıcak su + soğutulmuş su |

**COP 5,5 doğrulanmamıştır.** Hava soğutmalı bir chiller için iyimser bir
değerdir ve soğutma toplam tüketimin %55'i olduğu için sonucu doğrudan belirler.
Faz 3'te 3,0–7,0 aralığında taranacaktır.

## Ayar noktaları

Sekiz bölgenin **tamamı** aynı sabit değerleri kullanıyor:

| Program | Değer | Değişim |
|---|---|---|
| `heating setpoint` | 22,0 °C | yıl boyunca sabit |
| `cooling setpoint` | 24,0 °C | yıl boyunca sabit |

**İki önemli sonuç:**

1. Ölü bant yalnızca **2 K**. Bu, tipik ofis uygulamalarının (genellikle 20/26,
   yani 6 K) çok altındadır ve HVAC'ı gereksiz yere çalıştırır.
2. **Gece ve hafta sonu geri çekmesi yok.** Programlar sabit; bina boşken de
   aynı ayar noktası korunuyor.

Her ikisi de yatırım gerektirmeyen işletme önlemleridir ve Faz 3'te karar
değişkeni olarak taranacaktır.

## İç yükler

| Yük | Değer | Nesne |
|---|---|---|
| Aydınlatma — ofis, konferans salonu, atölye | 7,0 W/m² | `Lights Definition(ofis, k.salon, atolye)` |
| Aydınlatma — merdiven, koridor, mecoda, WC | 3,0 W/m² | `light defination (merd, kordor, mecoda, wc)` |
| Asansör motoru | 5.000 W | `asansor motoru` |
| Aydınlatma programı | `AYDINLATMA` | — |
| Ekipman programı | `ELEKTRIK EKIPMAN` | yıllık tam yük eşdeğeri 3.247 saat |
| Doluluk programı | `DOLULUK` | — |

### Asansör motoru — açık kabul

Onarım öncesinde `Electric Equipment 1` nesnesi `asnsr` **SpaceType**'ına
bağlıydı. O SpaceType'a dört mekân (KZ_ASN_18, KB_ASNS_7, K1_ASNS_1, K2_ASNS_1 —
her kattan bir asansör boşluğu) ait olduğu için EnergyPlus tanımı dört kez
örnekliyor ve toplam **20.000 W** oluşuyordu.

**Kabul:** Binada tek bir asansör vardır ve motoru bir kez sayılmalıdır. Onarım,
ekipmanı `K2_ASNS_1` mekânına bağlar (makine dairesi en üst katta varsayılmıştır).

**Doğrulanması gereken iki nokta:**
1. Binadaki gerçek asansör sayısı.
2. 5.000 W bir asansör motorunun **tepe** gücüdür; sürekli bağlı yük olarak
   kullanılması muhtemelen yüksek kalır. Gerçek motor gücü ve çalışma profili
   teyit edilmelidir.

## İklimlendirilmeyen bölgeler

`TZ_asnsr` ve `TZ_mecoda` bölgelerinin **termostatı var ancak ZoneHVAC cihazı
yok**. Ayar noktası tanımlı olduğu halde onu karşılayacak ekipman bulunmuyor, bu
yüzden sıcaklıkları serbest yüzüyor.

`TZ_mecoda` için sonuç sınırlı (yılın %1,2'si konfor bandı dışı). `TZ_asnsr` için
ise 20 kW'lık yük nedeniyle yıkıcıydı; onarım sonrası yeniden ölçülmüştür.

**Karar gerekiyor:** Asansör boşluğu ve mecoda gerçekten iklimlendirilmiyorsa
termostatları kaldırılıp havalandırma tanımlanmalı; iklimlendiriliyorsa fan-coil
eklenmelidir.

## Kalibrasyon durumu

**Model ölçüme dayalı olarak kalibre edilmemiştir.** Elde 12 aylık fatura veya
sayaç verisi yoktur.

Sonuç olarak:

- Enerji taban çizgisi (EnB), **simülasyon tabanlı referans senaryodur**;
  ölçülmüş bir taban çizgisi değildir.
- Mutlak tüketim değerleri değil, **senaryolar arası göreli değişimler**
  yorumlanmalıdır.
- ASHRAE Guideline 14 kriterleri (NMBE ≤ %5, CVRMSE ≤ %15) uygulanamamıştır.

Bu, optimizasyon çalışmasını geçersiz kılmaz: çok amaçlı optimizasyon göreli
karşılaştırma üzerine kuruludur. Ancak tezde açıkça beyan edilmelidir.

## Asansör boşluğu havalandırması — açık kabul

`TZ_asnsr` bölgesinde HVAC cihazı yok ve modelde **hiç havalandırma tanımlı
değildi**. Asansör motorunun ısısı bölgede hapsolduğu için sıcaklık yıl boyunca
88,0 °C ortalamada kalıyordu. Asansör yükü dörtte bire indirildikten sonra bile
43,8 °C ortalama ve 63,6 °C tepe değeri sürüyordu.

Yönetmelik gereği asansör kuyuları tepeden havalandırılır. Modelde bu eksikti;
onarım bir `ZoneVentilation:DesignFlowRate` nesnesi ekler.

**Boyutlandırma:**

```
Q = m · cp · ΔT
V = 5.000 W / (1,2 kg/m³ · 1.005 J/kgK · 10 K) = 0,414 m³/s
```

Yani motorun tepe gücündeki ısıyı yaklaşık 10 K sıcaklık farkıyla atacak debi.
`Ventilation Type = Natural` seçildiği için modele **fan enerjisi eklenmez**.

**Değiştirilebilir:** Debi, `model_repair_worker.py` içindeki
`SHAFT_VENTILATION_M3_S` sabitiyle tek yerden ayarlanır. Gerçek kuyu havalandırma
kesiti biliniyorsa bu değer onunla değiştirilmelidir.

**Alternatif ve muhtemelen daha doğru çözüm:** 5.000 W bir asansör motorunun tepe
gücüdür. Gerçek ortalama güç doğrulanabilirse havalandırma ihtiyacı da azalır.
Bu, önerilen ilk doğrulama adımıdır.
