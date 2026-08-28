# Fikri Ürün Bildirim Formu — hazırlık notu

TÜBİTAK ARDEB kuralları, Proje Sonuç Raporu ile birlikte **Fikri Ürün Bildirim
Formu**'nun doldurulmasını zorunlu kılar. Form ARDEB-PTS üzerinden gönderilir
ve imza gerektirir; bu belge formu doldurmaz, formun sorduğu bilgileri
depodan toplar.

---

## Önce dikkat: bu projede fikri ürün büyük olasılıkla **vardır**

Şablonun tanımı:

> Projeden fikri ürün (patent, faydalı model, marka, know-how, endüstriyel
> tasarım, entegre devre topografyası, yeni bitki ve hayvan türleri ve bunların
> ıslah yöntemleri, **bilgisayar programları ve bunların kaynak kodları** vb.)
> çıkıp çıkmadığı formda belirtilir.

Bilgisayar programları ve kaynak kodları **açıkça sayılmıştır**. Bu proje
çalışır durumda bir yazılım üretmiştir (aşağıdaki envanter). Dolayısıyla
"hayır" seçeneğini işaretlemek muhtemelen doğru olmayacaktır.

Şablon ayrıca şunu belirtir:

> Projeden fikri ürün dışında ortaya çıkan eserler yani, **bilgisayar
> programları ve bunların kaynak kodları hariç** … kitap, makale, bildiri …
> için fikri ürün formu doldurulmayacağına dikkat edilir.

Yani makale/bildiri için form gerekmez, **yazılım için gerekir**.

### Bunun doğurduğu yükümlülük

> Fikri Ürün Bildirim Formunun sunulmasından itibaren **en geç üç ay içerisinde**
> ilgili fikri ürünle ilgili **tescil başvurusu** yapılmalıdır.

Bu ciddi bir taahhüttür. Yazılımın fikri ürün olarak bildirilip
bildirilmeyeceği ve tescil yolunun ne olacağı (eser sahipliği tescili,
kurumun teknoloji transfer ofisi üzerinden işlem vb.) **proje yürütücüsünün
ve kurumun kararıdır**. Karar öncesinde ARDEB'e danışılması önerilir.

---

## Yazılım envanteri

Depo: `star-energy-api-studio/` · Geliştirme dönemi: 12 Mart 2026 – 28 Ağustos 2026

| Bileşen | Ölçü |
|---|---|
| Python kaynak kodu | **13.853 satır** / 70 dosya |
| OpenStudio measure'ları (Ruby, proje tarafından yazılan) | **804 satır** / 9 measure |
| Otomatik test dosyası | 9 dosya, 141 test |

### Proje tarafından yazılan OpenStudio measure'ları (9)

Karar değişkenlerini modele uygulayan yedi measure ve iki yardımcı:

`SetEpsThickness` · `SetWindowConstruction` · `SetInfiltrationRate` ·
`SetThermostatSetpoints` · `SetPlantEfficiency` · `SetLightingPower` ·
`SetElevatorLoad` · `ExportModelToJson` · `ImportResultsFromJson`

### Proje ürünü OLMAYAN bileşenler

Bunlar forma **dâhil edilmemelidir**:

| Bileşen | Sahibi |
|---|---|
| `CreateCSVOutput` measure | Alliance for Sustainable Energy (OpenStudio ile gelir) |
| `OpenStudioResults` measure | Alliance for Sustainable Energy (OpenStudio ile gelir) |
| OpenStudio 3.11.0, EnergyPlus | Alliance for Sustainable Energy / DOE |
| NiceGUI, FastAPI, scikit-learn, pymoo, matplotlib, python-docx, numpy, scipy | Üçüncü taraf açık kaynak kütüphaneler (`requirements.txt`) |

### Ana modüller ve işlevleri

| Modül | İşlev |
|---|---|
| `engine/` | Karar değişkeni tanımları, örnekleme, OpenStudio koşu yönetimi, SQL sonuç okuma |
| `surrogate/` | Vekil model eğitimi (Kriging / polinom / boosting), Sobol duyarlılık analizi |
| `optimization/` | Amaç fonksiyonları, kısıtlar, maliyet modeli, NSGA-II problem tanımı, TOPSIS |
| `validation/` | Doğrulama noktası seçimi ve sapma özeti |
| `iso50001/` | SEU belirleme, derece-gün normalizasyonu, EnPİ hesabı |
| `reporting/` | Proje Sonuç Raporu üreteci (şekiller, DOCX, ekran görüntüleri) |
| `api_layer/`, `services/`, `client/`, `model_store/`, `ui_pages/` | HTTP API, OpenStudio servis katmanı, arayüz |

### Özgün olduğu ileri sürülebilecek yönler

Formda "yeniliği/özgünlüğü" sorulursa dayanak olabilecek noktalar:

1. Vekil model belirsizliğinin optimizasyona ceza terimi olarak aktarılması ve
   katsayının doğrulama yanlılığını sıfırlayacak biçimde ayarlanması
   (`run_optimization.py --uncertainty-penalty`).
2. Dairesel doğrulamaya karşı koruma: eğitim kümesindeki çözümlerin doğrulama
   aday havuzundan çıkarılması (`validation/selection.py`).
3. Seyrek dağılımlı hedeflerde CVRMSE yerine aralığa göre normalize hata ve
   belirlilik katsayısının birlikte kullanılması (`surrogate/models.py`).
4. ISO 50001 önemli enerji kullanımı kavramının Sobol duyarlılık sıralamasıyla
   birlikte kullanılması.
5. Raporun tüm sayısal değerlerinin üretilmiş çıktı dosyalarından okunarak
   derlenmesi; metinde elle yazılmış sonuç değeri bulunmaması.

---

## Katkı kaydı

`git shortlog` çıktısı:

| Katkı veren | Commit |
|---|---|
| Gizem \<gizemderici26@gmail.com\> | 28 |
| gizemderici \<gizemderici26@gmail.com\> | 27 |

Aynı kişinin iki farklı git kimliği; toplam 55 commit.

**Not:** Commit kayıtları kod katkısını gösterir, hak sahipliğini belirlemez.
Hak sahipliği kurumun fikri mülkiyet yönetmeliğine ve proje sözleşmesine
göre belirlenir. Form "hak sahipleri tarafından" imzalanır.

---

## Kapatılması gereken boşluk: lisans dosyası yok

Depoda **hiçbir LICENSE dosyası bulunmamaktadır**. Bu, yazılımın kullanım ve
dağıtım koşullarının tanımsız olduğu anlamına gelir. Fikri ürün bildirimi
yapılacaksa, lisans tercihinin kurumla birlikte kararlaştırılması ve depoya
yazılması gerekir. Seçim, tescil yolunu da etkileyebilir.

---

## Formu doldururken elde olması gerekenler

Bu belgeden karşılanamayan, sizden gelmesi gereken bilgiler:

- Proje no ve program kodu
- Proje yürütücüsü, araştırmacı, danışman ve bursiyer bilgileri
- Kurum/kuruluş bilgileri ve fikri mülkiyet yönetmeliği
- Hak sahipliği paylaşımı
- Tescil yolu tercihi ve lisans kararı

---

## Özet

| Soru | Durum |
|---|---|
| Projeden fikri ürün çıktı mı? | **Muhtemelen evet** — çalışır durumda bir yazılım |
| Hangi tür? | Bilgisayar programı ve kaynak kodu |
| Form kapsamı | Tamamı doldurulur, hak sahiplerince imzalanır |
| Üç ay içinde tescil başvurusu | **Zorunlu** — karar öncesi ARDEB'e danışın |
| Lisans | **Tanımsız** — kapatılmalı |

Nihai karar proje yürütücüsüne aittir; bu belge yalnızca formun sorduğu
bilgileri derler.
