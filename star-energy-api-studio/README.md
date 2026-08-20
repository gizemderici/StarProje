# STAR Energy API Studio

OpenStudio/EnergyPlus bina modelini, arşivlenmiş SQL sonuçlarını ve EPS
parametrik senaryolarını tek bir Türkçe NiceGUI arayüzünde birleştiren Python
projesi.

## Hemen çalıştırma

1. `star-energy-api-studio.code-workspace` dosyasını VS Code ile açın.
2. `start.bat` dosyasına çift tıklayın veya VS Code'da **Terminal → Run Task →
   Uygulamayı çalıştır** seçin.
3. Başlatıcı önce HTTP API'yi `http://127.0.0.1:8091`, ardından NiceGUI
   arayüzünü `http://127.0.0.1:8090` adresinde açar.

API belgeleri: `http://127.0.0.1:8091/docs`

Proje içinde çalışan bir `.venv` hazırlanmıştır. Başka bir bilgisayara
taşındığında `start.ps1`, Python 3.11+ bulup ortamı yeniden kurabilir.

## Neler var?

- **Genel Bakış:** 5/10/15 cm arşiv EnergyPlus SQL sonuçları, aylık tüketim,
  son kullanım dağılımı ve veri kalite kontrolü.
- **Parametrik Stüdyo:** EPS kalınlığı ve iletkenliği için anlık tarama, U/R
  değeri, enerji, EUI ve tasarruf karşılaştırması; ayrıca `Star.zip` içindeki 20
  gerçek EnergyPlus koşusunun grafik ve tablosu; CSV/JSON dışa aktarma.
- **Model Gezgini:** NiceGUI → HTTP API → OpenStudio SDK akışıyla 1.310 yüzey,
  127 mekân, 8 ısıl bölge, 22 konstrüksiyon ve katman özellikleri. Arayüzden
  yeni `.osm` ve isteğe bağlı `.epw` yükleyebilir, API'nin ürettiği model
  kimliğiyle modeller arasında geçiş yapabilirsiniz.
- **OpenStudio Koşusu:** API üzerinden OSW üretimi; gerçek koşuda OpenStudio SDK
  ile EPS değişikliği ve kurulu EnergyPlus ile yıllık simülasyon.
- **Tanılama:** EnergyPlus uyarıları, ciddi hatalar, WWR ve kaynak birleştirme
  kaydı.

## Komut satırı

Hızlı parametrik simülasyon:

```powershell
.\.venv\Scripts\python.exe .\run_simulations.py --mode quick --thicknesses 3 5 8 10 15 20 25 30
```

Bu bilgisayarda doğrulanan kurulum OpenStudio 3.11.0'dır. Başka bir kurulum
kullanılacaksa gerekirse yolu tanımlayın:

```powershell
$env:OPENSTUDIO_EXE = 'C:\Program Files\openstudio-3.11.0\bin\openstudio.exe'
.\.venv\Scripts\python.exe .\run_simulations.py --mode openstudio --thicknesses 5 10 15
```

OpenStudio kurulu değilken yalnızca çalıştırılabilir OSW dosyaları hazırlamak:

```powershell
.\.venv\Scripts\python.exe .\run_simulations.py --mode openstudio --prepare-only --thicknesses 5 10 15
```

Testler:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## API mimarisi

NiceGUI OSM, SQL veya STAR CSV dosyasını doğrudan açmaz. `client/energy_api.py`
model kimliği ve JSON ile HTTP API'ye bağlanır. Yeni model yüklemesinde dosya
yolu değil, OSM/EPW içeriği API'ye gönderilir. API güvenli depoda model kimliği
üretir; modeli `OpenStudioService` ile kurulu OpenStudio'nun resmi SDK'sına
açtırır. Yerel dosya yolları API yanıtlarında dışarı verilmez. Ayrıntılı şema
için `docs/MIMARI.md` dosyasına bakın.

## Sonuçların doğru yorumu

Arşivdeki 5, 10 ve 15 cm EnergyPlus sonuçları birbirinin aynıdır. Eski Python
kodu yeni konstrüksiyonu üretmiş ancak kullanılan yüzeylere bağlamamıştır.
Projede bu sorun konstrüksiyonun katmanlarını yerinde güncelleyen OpenStudio
measure ile giderildi.

Parametrik Stüdyo sonuçları “kalibre edilmiş hızlı tahmin” olarak etiketlidir;
nihai mühendislik doğrulaması, düzeltilmiş measure ile gerçek OpenStudio koşusu
yapılarak gerçekleştirilmelidir. Ayrıntılar için `docs/PROJE_INCELEMESI.md`
dosyasına bakın.

`Star.zip` ayrı bir 176 m² modeldir. 20 koşudan 14'ü benzersizdir; özet verileri
referans ve en iyi test koşusunun ham SQL dosyalarıyla doğrulanmıştır. Referans
yalıtım (10 cm, λ=0,020 W/mK) denenen tüm alternatiflerden daha güçlü olduğu
için referans HVAC sonucu en düşük kalmıştır.
