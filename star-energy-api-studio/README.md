# STAR Energy API Studio

Önemli enerji kullanıcısı bir kampüs binasında **ISO 50001 uyumlu enerji
tüketiminin çok amaçlı optimizasyonu**: vekil model tabanlı yöntem tasarımı ve
simülasyon destekli sayısal doğrulama.

OpenStudio/EnergyPlus modelini, 175 gerçek simülasyon koşusunu, vekil modeli,
NSGA-II Pareto cephesini, ISO 50001 göstergelerini ve doğrulama sonuçlarını tek
bir Türkçe NiceGUI arayüzünde birleştirir.

| | |
|---|---|
| **Bina** | 4.246,18 m² kampüs binası · 127 mekân · 8 ısıl bölge · 1.310 yüzey |
| **Taban çizgisi** | 1.920,00 GJ/yıl · 452,17 MJ/m² · **0 Ciddi Hata** |
| **Karar değişkeni** | 11 (7 OpenStudio measure) |
| **Eğitim kümesi** | 175 gerçek EnergyPlus koşusu |
| **Vekil model doğruluğu** | CVRMSE %2,75 · R² 0,994 |
| **Doğrulama** | 8 taze nokta · ortalama sapma %1,89 · en büyük %4,57 |

---

## Merkezî bulgu: yalıtım bu binada belirleyici değildir

Proje EPS yalıtım kalınlığını taramak üzere kurulmuştu. **Veri bunu üç bağımsız
yoldan çürüttü.**

**1. Sobol duyarlılık analizi** — enerji varyansının hangi değişkenden geldiği:

| Değişken | S1 (birinci mertebe) | ST (toplam) |
|---|---|---|
| Chiller COP | **0,5687** | 0,5720 |
| Soğutma ayar noktası | 0,2214 | 0,2502 |
| Cam tipi | 0,1234 | 0,1288 |
| Aydınlatma (ofis/salon/atölye) | 0,0598 | 0,0791 |
| … | | |
| **EPS kalınlığı** | **0,0002** | **0,0004** |

EPS kalınlığı 11 değişken arasında **sonuncudur**; varyansın binde ikisini bile
açıklamaz. Chiller COP tek başına %57'sini açıklar.

**2. ISO 50001 önemli enerji kullanımları (SEU, Pareto %80 kuralı):**

| Son kullanım | GJ | Pay | Kümülatif |
|---|---|---|---|
| Soğutma | 1.119,56 | %58,3 | %58,3 |
| İç ekipman | 261,13 | %13,6 | %71,9 |
| Fanlar | 239,90 | %12,5 | **%84,4** |
| İç aydınlatma | 230,27 | %12,0 | %96,4 |

Bina **soğutma ağırlıklıdır**. Isıtma payı %2,4'tür — yalıtımın etkileyeceği
kalem zaten küçüktür.

**3. TS 825 uygunluk kontrolü** (bölge 3 varsayımı):

- Taban duvar U = **0,2901 W/m²K** < 0,50 sınırı → **zaten uygun**
- Taban cam U = **2,718 W/m²K** > 2,00 sınırı → **uygun değil**

Yani iyileştirme potansiyeli duvarda değil, **camda ve soğutma sisteminde**.

> Bu, tezin yöntem bölümünün ana çıktısıdır: vekil model tabanlı duyarlılık
> analizi, başlangıçtaki tasarım hipotezini sayısal olarak reddetmiştir.

---

## Hemen çalıştırma

1. `star-energy-api-studio.code-workspace` dosyasını VS Code ile açın.
2. `start.bat` dosyasına çift tıklayın veya **Terminal → Run Task → Uygulamayı
   çalıştır** seçin.
3. Başlatıcı önce HTTP API'yi `http://127.0.0.1:8091`, ardından NiceGUI
   arayüzünü `http://127.0.0.1:8090` adresinde açar.

API belgeleri: `http://127.0.0.1:8091/docs`

Proje içinde hazır bir `.venv` bulunur. Başka bir bilgisayara taşındığında
`start.ps1`, Python 3.11+ bulup ortamı yeniden kurar.

---

## Arayüz sekmeleri

| Sekme | İçerik |
|---|---|
| **Enerji Merkezi** | Onarılmış taban koşusu (varsayılan); aylık profil, son kullanım dağılımı. Eski 5/10/15 cm arşiv koşuları ayrıca seçilebilir ve veri kalitesi uyarısıyla etiketlidir. |
| **Senaryo Kurucu** | 11 karar değişkeni için senaryo tanımı; gerçek OpenStudio koşusu tetikleme. |
| **Canlı Akış** | Koşu ilerlemesi ve EnergyPlus çıktısı. |
| **Model ve Varlıklar** | NiceGUI → HTTP API → OpenStudio SDK akışıyla mekân, yüzey, bölge ve konstrüksiyon katmanları. Arayüzden yeni `.osm`/`.epw` yüklenebilir. |
| **Geçmiş ve Tanılama** | EnergyPlus uyarıları, ciddi hatalar, WWR, koşu geçmişi. |
| **Vekil Model** | Aday model karşılaştırması, bağımsız test kümesi skorları, Sobol duyarlılık sıralaması, hızlanma. |
| **Pareto** | 80 çözümlü cephe, hipervolüm yakınsaması, TOPSIS uzlaşı çözümü. |
| **ISO 50001** | SEU dağılımı, HDD/CDD normalizasyonu, EnPI göstergeleri. |
| **Doğrulama** | Vekil tahmin ile gerçek EnergyPlus koşusunun nokta nokta karşılaştırması. |

---

## Yöntem zinciri

```
Faz 0  Kanonik model seçimi
Faz 1  Model onarımı            -> 3 Severe -> 0 Severe
Faz 2  Measure altyapısı        -> 11 değişken, 7 measure
Faz 3  Parametrik koşu          -> 151 benzersiz EnergyPlus sonucu (313,5 dk)
Faz 4  Vekil model              -> Kriging, CVRMSE %2,75
Faz 5  ISO 50001                -> SEU, HDD/CDD, EnPI
Faz 6  NSGA-II optimizasyon     -> 80 çözümlü Pareto cephesi
Faz 7  Sayısal doğrulama        -> ortalama sapma %1,89 (kapı: %5)
Faz 8  Arayüz entegrasyonu
```

### Faz 3 — parametrik koşu

Sobol düşük-tutarsızlık örneklemesi, taban noktası daima 0. indekste. Isıtma ve
soğutma ayar noktaları arasında **asgari 0,5 K ölü bant** örnekleme aşamasında
zorlanır. Koşu bütünlüğü `eplusout.end` içindeki `Completed Successfully`
ifadesiyle doğrulanır; yarım kalan koşular hasat edilmez.

### Faz 4 — vekil model

Üç aday yarışır: polinom+RidgeCV, Kriging (Matérn), HistGradientBoosting.
Fiziğe dayalı türetilmiş öznitelikler (`1/COP`, `1/kazan verimi`, duvar U
değeri, ölü bant) modeli %14,65 CVRMSE'den %6,19'a taşımıştır.

| Hedef | Model | R² | Ölçüt | Değer |
|---|---|---|---|---|
| `site_energy_gj` | kriging | 0,994 | CVRMSE | **%2,75** ✓ |
| `cooling_gj` | kriging | 0,994 | CVRMSE | %4,31 ✓ |
| `comfort_violation_hours` | boosting | 0,984 | NRMSE(aralık) | %5,40 ✓ |
| `heating_gj` | kriging | 0,645 | NRMSE(aralık) | %11,11 ✗ (kapı dışı) |

`heating_gj` kapı ölçütünü karşılamaz ve bu **açıkça raporlanır**: 175 koşunun
79'unda ısıtma sıfıra yakındır, seyrek hedeflerde CVRMSE yanıltıcıdır. Amaç
fonksiyonlarında kullanılmadığı için kapı dışında tutulmuştur.

Hızlanma: EnergyPlus koşusu ~132 s, vekil model çağrısı ~6 µs → **~21,9 milyon
kat**.

### Faz 6 — çok amaçlı optimizasyon

NSGA-II (`pymoo`, karma değişkenli), 3 amaç ve 5 kısıt:

- **Amaçlar:** EnPI (kWh/m²·yıl), yatırım maliyeti (TRY), konfor ihlali (bölge-saat)
- **Kısıtlar:** TS 825 duvar U, TS 825 cam U, konfor tavanı, bütçe tavanı, asgari ölü bant

Hipervolüm 120 nesilde **0,6572 → 0,8853**. Cephe 80 çözüm içerir.

### Faz 7 — doğrulama ve vekil model hatasının sömürülmesi

İlk iki turda 16 sapmanın 14'ü negatifti: optimizasyon, modelin *iyimser*
olduğu az örneklenmiş bölgelere yerleşiyordu. Adaptif örnekleme tek başına
sorunu **büyüttü** (%5,22 → %8,11).

Çözüm, Kriging'in belirsizlik tahminini optimizasyona vermek:

```
tahmin = ortalama + k · sigma
```

| Tur | k | Eğitim | Ortalama sapma | En büyük | Kapı |
|---|---|---|---|---|---|
| 1 | 0 | 151 | %2,72 | %5,22 | ✗ |
| 2 | 0 | 159 | %3,40 | %8,11 | ✗ |
| 3 | 1,0 | 167 | %2,38 | %5,31 | ✗ |
| 4 | **0,5** | **175** | **%1,89** | **%4,57** | **✓** |

Doğrulama noktaları eğitim kümesinden **çıkarılır**; aksi halde doğrulama
dairesel hale gelir ve modelin ezberini ölçer. Ayrıntı:
[docs/faz7_dogrulama.md](docs/faz7_dogrulama.md).

---

## Sonuç: önerilen çözüm

TOPSIS uzlaşı çözümü, gerçek EnergyPlus koşusuyla doğrulanmıştır:

| | Taban çizgisi | TOPSIS çözümü |
|---|---|---|
| Saha enerjisi | 1.920,00 GJ | 1.128,65 GJ |
| EnPI | 125,60 kWh/m²·yıl | **73,83 kWh/m²·yıl** |
| Vekil model sapması | — | **%1,47** |

ISO 50006 iklim normalizasyonu: HDD18 = 1.782,5 · CDD22 = 557,5 (EPW'den
saatlik kuru termometre sıcaklığıyla hesaplanır).

---

## Komut satırı

Faz 3 — parametrik koşu (saatler sürer):

```powershell
.\.venv\Scripts\python.exe .\run_parametric_study.py --count 151 --seed 7
```

Faz 4 — vekil model eğitimi ve duyarlılık analizi:

```powershell
.\.venv\Scripts\python.exe .\run_surrogate.py
```

Faz 5 — ISO 50001 raporu:

```powershell
.\.venv\Scripts\python.exe .\build_iso50001_report.py
```

Faz 6 — NSGA-II, belirsizlik cezası katsayısıyla:

```powershell
.\.venv\Scripts\python.exe .\run_optimization.py --uncertainty-penalty 0.5
```

Faz 7 — doğrulama:

```powershell
.\.venv\Scripts\python.exe .\run_validation.py
```

Bu bilgisayarda doğrulanan kurulum **OpenStudio 3.11.0**'dır. Farklı bir kurulum
için yolu tanımlayın:

```powershell
$env:OPENSTUDIO_EXE = 'C:\Program Files\openstudio-3.11.0\bin\openstudio.exe'
```

Testler — `tests/` bir Python paketi değildir, bu yüzden üst dizin `tests`
olarak verilir:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t tests
```

125 test geçmektedir.

---

## API mimarisi

NiceGUI, OSM/SQL/CSV dosyalarını **doğrudan açmaz**. `client/energy_api.py`
model kimliği ve JSON ile HTTP API'ye bağlanır; model yüklemesinde dosya yolu
değil içerik gönderilir. API güvenli depoda kimlik üretir ve modeli
`OpenStudioService` üzerinden resmi SDK'ya açtırır. **Yerel dosya yolları API
yanıtlarında dışarı verilmez** — bu bir testle korunur.

Sonuç uçları:

| Uç | Döndürdüğü |
|---|---|
| `GET /api/v1/models/{id}/baseline-results` | Faz 1 onarımı sonrası taban koşusu |
| `GET /api/v1/models/{id}/archived-results` | Eski 5/10/15 cm arşiv koşuları |
| `GET /api/v1/models/{id}/study-results` | İkinci binanın parametrik çalışması |

Ayrıntılı şema: [docs/MIMARI.md](docs/MIMARI.md).

---

## Sonuçların doğru yorumu

**Arşiv koşuları parametrik veri değildir.** `data/archived_runs` içindeki 5, 10
ve 15 cm sonuçları birbirinin **aynısıdır** (Cooling 1.154,37 · Heating 36,88 ·
Total 1.904,72). Eski kod alternatif konstrüksiyonu üretmiş ancak yüzeylere
bağlamamıştır. Bu koşular yalnızca tarihsel referanstır ve arayüzde böyle
etiketlenir. Hata, konstrüksiyon katmanlarını yerinde güncelleyen measure ile
giderilmiştir.

**Parametrik Stüdyo'daki hızlı tahmin kalibre edilmemiştir.** Yalnızca eğilim
göstermek içindir; mühendislik kararı vekil model ve gerçek OpenStudio koşusuyla
verilir.

**Taban çizgisi ölçülmüş değildir.** `data/baseline_v1` simülasyon tabanlı bir
referans senaryodur; model faturaya kalibre edilmemiştir. ISO 50001 raporu bu
uyarıyı `measured: false` alanıyla taşır.

**Açıkça varsayım olan girdiler:**

- `optimization/cost_model.py` içindeki `UNIT_PRICES` birim fiyatları
- TS 825 iklim bölgesi **3** kabul edilmiştir; binanın gerçek bölgesi doğrulanmalıdır
- EPS kalınlığı üst sınırı 30 cm — hem gerçekçi değildir hem de koşu süresini uzatır
- 175 parametrik koşunun 24'ünde ısınma yakınsaması uyarısı vardır (15'i yalnızca `TZ_ASNSR` bölgesinde)

`Star.zip` **ayrı bir 176 m² modeldir**, kampüs binası değildir; çapraz
doğrulama vakası olarak tutulur. 20 koşudan 14'ü benzersizdir.

---

## Belgeler

| Dosya | İçerik |
|---|---|
| [docs/model_secimi.md](docs/model_secimi.md) | Kanonik model kararı ve giderilen tutarsızlıklar |
| [docs/bulgular_faz1.md](docs/bulgular_faz1.md) | Model onarımı: ölçülmüş öncesi/sonrası |
| [docs/faz2_measure_altyapisi.md](docs/faz2_measure_altyapisi.md) | 11 karar değişkeni ve 7 measure |
| [docs/faz7_dogrulama.md](docs/faz7_dogrulama.md) | Doğrulama yöntemi ve belirsizlik cezası |
| [docs/iso50001_kapsam.md](docs/iso50001_kapsam.md) | ISO 50001/50006 kapsam ve sınırlar |
| [docs/baseline_assumptions.md](docs/baseline_assumptions.md) | Taban çizgisi varsayımları |
| [data/baseline_v1/README.md](data/baseline_v1/README.md) | Taban koşusunun künyesi |
