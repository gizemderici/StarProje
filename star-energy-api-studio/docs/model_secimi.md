# Kanonik Model Seçimi

**Karar:** Faz 0.2
**Seçilen model:** `data/input/gsf_fng_6mayis.osm`

## Bulgu: üç aday değil, iki model var

İnceleme sırasında `gsf_fng_6mayis.osm` ile `bina_orijinal.osm` dosyalarının
farklı olduğu sanılıyordu, çünkü ham baytları farklı özet değeri veriyordu.
Fark yalnızca satır sonlarındandır: depodaki kopya git tarafından CRLF'e
çevrilmiş, arşivden çıkan kopya LF olarak kalmıştır.

Satır sonu normalize edildiğinde ikisi **birebir aynı dosyadır**:

| Dosya | Normalize boyut | SHA-256 (ilk 20) |
|---|---|---|
| `data/input/gsf_fng_6mayis.osm` | 1.775.122 | `a69a2b2461e529c8b79b` |
| `data/input/bina_orijinal.osm` | 1.775.122 | `a69a2b2461e529c8b79b` |

Bu tekrarın yeniden oluşmaması için depoya `.gitattributes` eklendi.

## Gerçek adaylar

| Model | Normalize boyut | Ait olduğu koşu | Saha enerjisi |
|---|---|---|---|
| **`gsf_fng_6mayis.osm`** | 1.775.122 | 7 Mayıs 2026 | **2.128,85 GJ** |
| `bina_eps_5cm.osm` | 1.774.920 | `data/archived_runs/eps_5cm` | 1.941,59 GJ |
| `bina_eps_10cm.osm` | 1.774.920 | `data/archived_runs/eps_10cm` | 1.941,59 GJ |
| `bina_eps_15cm.osm` | 1.774.920 | `data/archived_runs/eps_15cm` | 1.941,59 GJ |

## Gerekçe

1. **Tek doğrulanabilir koşuya sahip model bu.** 7 Mayıs 2026 koşusunun tohum
   dosyasıdır; `eplusout.sql`, `eplusout.err`, `out.osw` ve 8.760 satırlık
   saatlik zon çıktısı elimizdedir.

2. **Yalnızca bu koşuda saatlik zon verisi var.** `hourly_zone.csv`, 8 zonun hava
   sıcaklığını ve bağıl nemini 8.760 saat boyunca içerir. Faz 4'ün konfor hedefi
   ve Faz 6'nın üçüncü amaç fonksiyonu bu veriye dayanır.

3. **EPS varyantları parametrik veri üretemiyor.** Üç `.osm` dosyası birbirinden
   farklıdır (farklı SHA), ancak koşu sonuçları birebir aynıdır:

   | | 5 cm | 10 cm | 15 cm |
   |---|---|---|---|
   | Cooling | 1154,37 | 1154,37 | 1154,37 |
   | Heating | 36,88 | 36,88 | 36,88 |
   | Total End Uses | 1904,72 | 1904,72 | 1904,72 |

   Model dosyalarının farklı ama sonuçların aynı olması teşhisi kesinleştirir:
   eski kod yeni konstrüksiyonu **üretmiş** ancak yüzeylere **bağlamamıştır**.
   Bu üç koşu yalnızca tarihsel referanstır.

4. **2.128,85 GJ ile 1.941,59 GJ farkı bir çelişki değildir.** İki farklı model
   sürümüne aittir. Kanonik model seçildikten sonra karşılaştırma tek sürüm
   üzerinden yapılacaktır.

## Bilinen tutarsızlık

`models.json` içinde `main-building` kaydının `archived_results` alanı halen
`data/archived_runs` klasörünü gösteriyor; bu koşular aslında `legacy-eps-5cm`
modeline aittir. Alan şimdilik korundu, aksi halde `/quick-study` uç noktası
404 döndürürdü.

**Faz 1.6** onarılmış taban koşusunu ürettiğinde alan yeni koşuyu gösterecek
biçimde güncellenmelidir. `engine/estimator.py` içindeki baz senaryo da aynı
anda gözden geçirilmelidir (Faz 4.7).

## Kanonik modelin bilinen kusurları

Model **henüz onarılmamıştır**; Faz 1 tamamlanana kadar sonuçları nihai kabul
edilmemelidir. Ayrıntı: `docs/bulgular_faz1.md`.

- 3 Severe hata: `TZ_ATOLYE`, `TZ_KORIDOR`, `TZ_WC` hacimleri hesaplanamıyor
- 828 uyarı
- `TZ_ASNSR` zonu yıl boyunca 58,9–122,1 °C, ortalama 88,0 °C
- Asansör iç yükü 20.000 W / 38,28 m² = 522 W/m², yılda 233,78 GJ
