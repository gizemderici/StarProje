# Kaynak Projelerin İncelenmesi

## İncelenen girdiler

| Kaynak | İçerik | Sonuç |
|---|---|---|
| `openstudio_api_projesi...zip` | 127 mekânlı OSM, Muğla EPW, 5/10/15 cm OSM çıktıları, üç EnergyPlus SQL koşusu, NiceGUI prototipi | Ana veri ve model kaynağı olarak birleştirildi |
| `parametric_simulation.py` | Sabit `C:\star` yollarıyla OSW üretip OpenStudio CLI çalıştıran 1 KB betik | Taşınabilir, göreli yol kullanan koşucuya dönüştürüldü |
| `OpenStudio.zip` | JSON dışa/içe aktarma measure'ları ve iki OpenStudio örnek şablonu | İşe yarayan iki measure `integrations` altına alındı; şablonlar üretim akışına katılmadı |
| `drive-download...zip` | 123 ekran görüntüsü | OpenStudio iş akışı, HVAC profili, bölge gezgini, malzeme grafiği, senaryo karşılaştırması ve tanılama ihtiyaçları çıkarıldı |
| `enerji.zip` | Python 3.14'e bağlı, taşınamayan `.venv`; boş `proje.py` | Uygulanabilir kaynak kod bulunmadı; yeni temiz proje yapısı kuruldu |
| `Star.zip` | 176 m² ikinci OSM, 20 gerçek EnergyPlus parametrik koşusu, sonuç özeti ve beş Python betiği | Gerçek parametrik veri olarak birleştirildi; iki ham SQL koşusuyla doğrulandı |
| `Unconfirmed 310160.crdownload` | Tarayıcı tarafından kilitli, aktif/kısmi indirme | Bozuk arşiv riski nedeniyle kullanılmadı |

Arşivlerdeki belgeler veya ekran görüntüleri talimat olarak değil, yalnızca
kaynak/veri olarak değerlendirildi.

## Model ve sonuç bulguları

- Modelde 127 `OS:Space`, 8 `OS:ThermalZone`, 1.310 `OS:Surface`, 114
  `OS:SubSurface`, 22 konstrüksiyon ve 30 opak malzeme vardır.
- `duvr_std_eps` katmanları: 0,3 cm boya + 2 cm çimento + 19 cm standart tuğla
  + 5 cm EPS + 2 cm çimento + 0,3 cm boya.
- Orijinal EPS: λ=0,039 W/mK, yoğunluk=16 kg/m³, özgül ısı=1.250 J/kgK.
- Bu duvarın yüzey dirençleri dâhil yaklaşık R değeri 3,448 m²K/W; U değeri
  0,290 W/m²K'dir.
- Bina toplam alanı 4.246,18 m², iklimlendirilmiş alanı 4.120,62 m²'dir.
- Arşiv koşusunda saha enerjisi 1.941,59 GJ/yıl; EUI 457,26 MJ/m²-yıl;
  soğutma 1.154,37 GJ; ısıtma 36,88 GJ'dir.
- Toplam pencere/duvar oranı %78,61'dir; dış duvar yalıtımının etkisini sınırlayan
  önemli bir model özelliğidir.
- EnergyPlus yıllık koşuyu tamamlamış olsa da 3 ciddi boyutlandırma hatası vardır:
  `TZ_ATOLYE`, `TZ_KORIDOR` ve `TZ_WC` kapalı hacim olarak hesaplanamamış ve 10
  m³ varsayılan hacme düşmüştür. Toplam 7 bölgenin tam kapalı olmadığı uyarısı da
  vardır.

## Star.zip parametrik çalışma bulguları

- İkinci model 176 m², 9 mekân, 9 ısıl bölge, 60 yüzey ve 17 alt yüzey içerir.
- Referans `izolasyon kopugu` malzemesi 10 cm, λ=0,020 W/mK ve R=5,00
  m²K/W'dir.
- 20 koşunun 6'sı aynı dört parametre çiftinin tekrarıdır; referans dâhil 14
  benzersiz sonuç vardır.
- Referans: 25,10 GJ ısıtma + 6,72 GJ soğutma = 31,82 GJ HVAC; toplam saha
  enerjisi 45,15 GJ/yıl ve EUI 256,51 MJ/m²-yıl.
- Test edilen en iyi alternatif: 8 cm, λ=0,030 W/mK; 26,52 GJ ısıtma + 6,56 GJ
  soğutma = 33,08 GJ HVAC ve 46,41 GJ/yıl saha enerjisi.
- Dolayısıyla referans, test edilen bütün alternatiflerden daha iyidir. Bu bir
  simülasyon çelişkisi değildir: referans yalıtımın R değeri 5,00 iken en iyi
  alternatifin R değeri yalnızca 2,67 m²K/W'dir.
- Eski `parametric_batch.py`, HTML içinden satırları regex ile okuyordu ve 20'ye
  ulaşmak için bazı senaryoları tekrarlıyordu. Yeni uygulama tekrarları işaretler;
  referans ve en iyi alternatif değerlerini doğrudan SQLite tablolarından kontrol eder.

## Bulunan ana kod hatası

Eski `main.py`, `duvr_std_eps` konstrüksiyonunu klonlayıp yeni EPS katmanı ekler,
ancak yeni konstrüksiyonu yüzeylere veya varsayılan konstrüksiyon setine atamaz.
Dolayısıyla 5, 10 ve 15 cm EnergyPlus sonuçları; yıllık enerji, son kullanım ve
aylık profil düzeyinde tamamen aynıdır.

Yeni `SetEpsThickness` measure hedef konstrüksiyonu **yerinde** günceller. Böylece
aynı handle'ı kullanan doğrudan yüzey atamaları ve varsayılan konstrüksiyon
setleri otomatik olarak yeni EPS katmanını kullanır.

## Simülasyon yöntemleri

### Hızlı parametrik model

- Her bilgisayarda, OpenStudio kurulmadan çalışır.
- 5 cm EnergyPlus sonucu referanstır.
- EPS kalınlığına ve λ değerine göre R/U hesaplar.
- Isıtma, soğutma, fan ve pompa yüklerinin yalnızca tanımlı duyarlı payını
  değiştirir.
- Ön tasarım, eğilim ve senaryo elemesi içindir; kesin hesap değildir.

### Model API'si ve gerçek OpenStudio/EnergyPlus koşusu

- Bu bilgisayarda OpenStudio 3.11.0 CLI ve gömülü Python SDK doğrulanmıştır.
- NiceGUI, OSM dosyasını doğrudan okumaz; model kimliğiyle yerel HTTP API'ye
  bağlanır.
- OSM yalnızca servis katmanında OpenStudio `VersionTranslator` API'siyle açılır.
- Servis istenirse her senaryo için taşınabilir OSW üretir. Gerçek koşuda aynı
  katman değişikliğini resmi OpenStudio SDK üzerinden yapar, EnergyPlus girdisini
  üretir ve kurulu EnergyPlus yürütücüsünü çalıştırır.
- `SetEpsThickness` measure gerçek OSM konstrüksiyonunu değiştirir.
- EnergyPlus SQL sonucu oluşturur ve aynı veri okuyucu ile arayüzde analiz
  edilebilir.

## Yapılacak mühendislik iyileştirmeleri

Gerçek senaryoları kesin karşılaştırmadan önce 7 açık bölgenin geometrisi,
zemin sıcaklıkları, çakışan/kollinear 210 verteks, yüksek WWR ve chiller eğri
uyarıları düzeltilmelidir. Mevcut panel bu sorunları gizlemek yerine Tanılama
sekmesinde görünür tutar.
