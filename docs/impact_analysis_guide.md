# Etki Analizi Rehberi

Bu dokuman, projedeki yeni etki analizi yapisinin nasil calistigini teknik ekip icin kisa ama kalici bir referans olarak aciklar.

## Amac

Bu yapi, bir CSV degerinin degismesi halinde:

- hangi alanlarin etkilendigini bulmak
- bu etkileri dogrudan ve dolayli olarak ayirmak
- eski ve yeni degerleri karsilastirmak
- sonucu tablo, ozet ve grafik olarak gostermek

amaciyla gelistirildi.

## Ana Bilesenler

### 1. Bagimlilik ve etki analizi motoru

Dosya:
- [analyze_csv_dependencies.py](c:\StarProje\analyze_csv_dependencies.py)

Temel sorumluluklari:
- veri setlerini yuklemek
- bagimlilik iliskilerini tanimlamak
- secili bir satirin etkisini hesaplamak
- eski ve yeni state arasindaki degisiklikleri bulmak
- degisimlerden etki analizi raporu uretmek

Ilgili fonksiyonlar:
- `analyze_row_dependency`
- `detect_state_changes`
- `build_impact_analysis_from_changes`

### 2. UI veri adaptasyon ve gorunum katmani

Dosya:
- [nicegui_csv_viewer.py](c:\StarProje\nicegui_csv_viewer.py)

Temel sorumluluklari:
- senaryo loglarini okumak
- etki analizini tablo satirlarina donusturmek
- filtreleme, ozet ve grafik modeli uretmek
- NiceGUI uzerinden kullaniciya sunmak

Ilgili fonksiyonlar:
- `build_impact_rows_for_scenario`
- `filter_impact_rows`
- `build_impact_summary`
- `build_impact_chart_model`

### 3. Test katmani

Dosyalar:
- [test_dependency_analysis.py](c:\StarProje\tests\test_dependency_analysis.py)
- [test_impact_view_models.py](c:\StarProje\tests\test_impact_view_models.py)

Testler su alanlari kapsar:
- etki analizi mantigi
- eski/yeni state diff yapisi
- ozet veri uretimi
- filtreleme ve siralama
- grafik veri modeli
- bos veri ve edge case davranislari

## Veri Akisi

Asagidaki akis su anki teknik yapinin ozetidir:

```text
Senaryo JSON
  ->
Senaryo uygulama ve log uretimi
  ->
Degisen alan log kayitlari
  ->
Bagimlilik analizi
  ->
Etki satirlarina donusum
  ->
Ozet + tablo + grafik modeli
  ->
NiceGUI ekrani
```

Biraz daha acik haliyle:

```text
scenario_definitions/*.json
  ->
apply_scenario_definition.py
  ->
simulation_outputs/*__changes.json
  ->
build_impact_rows_for_scenario()
  ->
analyze_row_dependency()
  ->
filter_impact_rows()
  ->
build_impact_summary() + build_impact_chart_model()
  ->
Senaryolar sekmesindeki UI bilesenleri
```

## Bagimlilik Mantigi

Sistemde temel bagimlilik zinciri su sekildedir:

```text
materials.csv
  ->
construction_layers.csv
  ->
constructions.csv
  ->
walls.csv / floors.csv / roofs.csv / windows.csv / openings.csv
```

Ek iliskiler:

```text
zones.csv
  ->
spaces.csv
  ->
walls.csv / floors.csv / roofs.csv

walls.csv
  ->
windows.csv / openings.csv
```

Bu nedenle bir deger degistiginde:

- ilk halkada dogrudan bagli kayitlar bulunur
- ikinci halkada dolayli etkilenen veri setleri hesaplanir

## Etki Analizi Ornegi

Ornek degisim:

- veri seti: `materials.csv`
- satir: `name=beton`
- kolon: `conductivity_w_per_mk`
- eski deger: `1.75`
- yeni deger: `2.10`

Beklenen etki:

- dogrudan:
- `construction_layers.csv`

- dolayli:
- `constructions.csv`
- `walls.csv`
- `floors.csv`
- `roofs.csv`

Bu ornek rapor su dosyada gorulebilir:
- [dependency_report.md](c:\StarProje\docs\dependency_report.md)

## Grafik Veri Modeli

Grafik katmani `build_impact_chart_model()` fonksiyonu ile uretilir.

Bu fonksiyon uc farkli grafik cikisi uretir:

### 1. Once / sonra karsilastirma

Amac:
- degisen ana degerin eski ve yeni halini gormek

Uretilen alanlar:
- `comparison.labels`
- `comparison.old_values`
- `comparison.new_values`
- `comparison.highlight_values`

### 2. Veri seti bazli etki dagilimi

Amac:
- hangi veri setinin ne kadar etkilendigini gormek

Uretilen alanlar:
- `distribution.labels`
- `distribution.direct_values`
- `distribution.indirect_values`

### 3. Iliski grafigi

Amac:
- ana degisim ile bagli alanlarin ag yapisini gostermek

Uretilen alanlar:
- `relations.nodes`
- `relations.links`
- `relations.categories`

Grafik kategorileri:
- `Ana Degisim`
- `Dogrudan Etki`
- `Dolayli Etki`

## UI Davranisi

Senaryolar sekmesinde su alanlar bulunur:

- Senaryo detayi
- Degisim Ozeti
- Etkilenen Alanlar tablosu
- Grafik Onizleme

UI davranisi:

- senaryo secildiginde etki alani yenilenir
- senaryo tekrar calistirildiginda log ve etki yeniden olusturulur
- filtreler degistiginde tablo ve grafik birlikte guncellenir
- filtre temizlenirse varsayilan gorunume donulur

## Filtreleme ve Inceleme

Etkilenen alanlarda su filtreler vardir:

- serbest metin arama
- tum / sadece dogrudan / sadece dolayli etki filtresi
- varsayilan / en buyuk degisim / en fazla etki siralamasi

Bu filtreler:

- ozet kartini
- tabloyu
- grafik veri modelini

ayni anda etkiler.

## Bilinen Limitasyonlar

- UI testleri tam anlamiyla browser seviyesinde degil; su an saf fonksiyon ve veri adaptasyonu test ediliyor.
- Iliski grafigi buyuk veri setlerinde kalabalik gorunebilir; bu nedenle ileride seviye bazli filtre veya grup ozeti eklenebilir.
- `build_impact_rows_for_scenario()` su an senaryo loglarina dayanir; log olmadan UI katmaninda etki listesi olusturulmaz.
- Eklenen ve silinen satirlar icin otomatik etki analizi su an `skipped` olarak isaretlenir; esas odak hucre guncellemeleridir.
- Grafik tooltip tarafinda NiceGUI ve ECharts entegrasyonu nedeniyle bazi ileri seviye formatter kullanimlari sinirli tutulmustur.

## Test ve Calistirma

Testleri calistirmak icin:

```powershell
python -m unittest discover -s tests -v
```

UI'yi calistirmak icin:

```powershell
python nicegui_csv_viewer.py
```

Not:
- [nicegui_csv_viewer.py](c:\StarProje\nicegui_csv_viewer.py) icinde `ui.run(...)` cagrisi test importlarini bozmamak icin `__main__` / `__mp_main__` kosuluyla korunur.

## Sonraki Iyilestirme Alanlari

- browser seviyesinde UI testi eklemek
- grafik icin daha sade node isimleri ve seviye bazli filtreler eklemek
- eklenen/silinen satirlar icin tam etki analizi yapmak
- rapor formatini disa aktarim icin standartlastirmak
