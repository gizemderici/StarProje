# OpenStudio OSM Veri Okuma ve Analiz Projesi

Bu proje, Python ve OpenStudio API kullanilarak bir `.osm` bina modelinin okunmasi, model verilerinin yapilandirilmis formata donusturulmesi, analiz edilmesi ve CSV tablolari olarak disa aktarilmasi amaciyla gelistirilmistir.

## Amac

Bu calismanin temel amaci, OpenStudio modelini yalnizca acmak degil, model icindeki verileri programatik olarak okuyup daha sonra kullanilabilecek bir veri altyapisi haline getirmektir.

Bu kapsamda proje su ihtiyaclara cevap verir:

- `.osm` model dosyasini Python ile okumak
- model icindeki temel bina elemanlarini cikarmak
- elemanlar arasi iliskileri koruyarak JSON uretmek
- elde edilen verileri analiz etmek
- verileri Excel'de acilabilecek CSV dosyalarina donusturmek

## Proje Kapsami

Su anda sistem asagidaki veri gruplarini okuyabilmektedir:

- thermal zone bilgileri
- space bilgileri
- duvar bilgileri
- cati bilgileri
- doseme bilgileri
- pencere ve diger aciklik bilgileri
- malzeme bilgileri
- construction bilgileri
- construction katman bilgileri
- eleman siniflandirma bilgileri

## Gelistirme Sureci

Asagida, proje boyunca yapilan calismalar adim adim ozetlenmistir.

### 1. OpenStudio Python API erisiminin dogrulanmasi

Ilk adimda OpenStudio Python API'nin ortamda calisip calismadigi kontrol edilmistir.

Bu is icin olusturulan dosya:

- [check_openstudio_api.py](c:\StarProje\check_openstudio_api.py)

Bu script:

- `openstudio` modulunu import etmeyi dener
- import basariliysa OpenStudio surumunu yazdirir
- import basarisizsa uygun hata bilgisini verir

Bu adim, sonraki tum gelistirmelerin saglikli ilerleyebilmesi icin temel dogrulama katmanidir.

### 2. OSM model dosyasinin yuklenmesi

Ikinci adimda `.osm` model dosyasinin OpenStudio uzerinden yuklenmesi saglanmistir.

Bu is icin olusturulan dosya:

- [openstudio_model_info.py](c:\StarProje\openstudio_model_info.py)

Bu script:

- `VersionTranslator` kullanarak modeli yukler
- model yuklenirse temel model ozetini terminale yazar

Bu asamada asagidaki temel bilgiler alinmistir:

- OpenStudio surumu
- space sayisi
- thermal zone sayisi
- surface sayisi
- construction sayisi
- material sayisi

Bu adim ile modelin Python tarafindan basarili sekilde okunabildigi gosterilmistir.

### 3. Detayli model verilerinin cikartilmasi

Ucuncu adimda modelin icindeki daha ayrintili verileri okumak icin ana veri cikarma scripti gelistirilmistir.

Bu is icin olusturulan dosya:

- [extract_openstudio_data.py](c:\StarProje\extract_openstudio_data.py)

Bu script modelden su bilgileri cikarir:

- zones
- walls
- roofs
- floors
- windows
- openings
- spaces
- materials
- constructions

Ayrica bu script:

- alan ve hacim bilgilerini okur
- elemanlar arasi baglantilari kurar
- verileri terminale yazdirir
- tum verileri JSON formatinda kaydeder

### 4. Teknik problemlerin giderilmesi

Gelistirme sirasinda OpenStudio Python binding yapisina bagli cesitli teknik problemlerle karsilasildi ve cozumler eklendi.

#### 4.1 OSM yolunun uygun formatta verilmesi

Model dosya yolu OpenStudio'nun bekledigi bicimde tanimlandi:

```python
openstudio.path(OSM_PATH)
```

#### 4.2 OSM dosya yolu dogrulamasi

Model yuklenmeden once dosyanin gercekten var olup olmadigi kontrol edildi.

Bu sayede:

- hatali yol kullanildiginda dogrudan bilgi verilir
- hata ayiklama daha kolay olur

#### 4.3 Optional sayisal degerlerin guvenli okunmasi

Bazi OpenStudio fonksiyonlari dogrudan sayi yerine `OptionalDouble` dondugu icin yardimci donusum fonksiyonlari eklendi.

Bu duzeltme sayesinde:

- veri varsa sayiya cevrilir
- veri yoksa `N/A` veya `None` kullanilir
- script calismasi hata nedeniyle kesilmez

Bu ozellikle su alanlarda gerekli oldu:

- zone volume
- space volume
- floor area
- gross area
- azimuth

#### 4.4 Malzeme donusum metodlarinin uyarlanmasi

OpenStudio Python API'de malzeme donusum metodlari C++ orneklerinden farkli isimlerle gelebilmektedir.

Bu nedenle su metodlar Python binding'e uygun sekilde kullanildi:

- `to_StandardOpaqueMaterial()`
- `to_MasslessOpaqueMaterial()`
- `to_SimpleGlazing()`

Bu sayede malzeme ozellikleri dogru sekilde okunabilir hale getirildi.

### 5. Construction ve katman verisinin eklenmesi

Bir sonraki adimda yalnizca elemanlari listelemek yerine, bu elemanlarin teknik yapisini da okuyabilmek amaciyla `construction` verisi eklendi.

Bu kapsamda:

- tum construction nesneleri okundu
- her construction icin katman sayisi belirlendi
- katmanlardaki malzemeler JSON icine dahil edildi

Bu sayede su teknik iliski kurulmus oldu:

- duvar -> construction -> katmanlar -> malzemeler

Bu adim, projeyi yalnizca geometri/veri sayma asamasindan yapi bileşeni analizi asamasina tasimistir.

### 6. Yapi elemanlarinin siniflandirilmasi

Model icindeki yuzeyler ve acikliklar daha anlamli analiz yapabilmek icin siniflandirildi.

Eklenen siniflandirmalar:

- duvarlar icin `dis_duvar`, `ic_duvar`
- cati/tavan icin `cati`, `ic_tavan`
- dosemeler icin `zemin_dosemesi`, `ic_doseme`, `dis_doseme`
- acikliklar icin `dis_pencere`, `ic_aciklik`, `dis_kapi`, `ic_kapi`

Bu sayede:

- elemanlar yalnizca tur bazinda degil, islev bazinda da ayristirilabilir hale geldi
- dis kabuk analizi yapmak kolaylasti
- daha anlamli alan ve kullanim raporlari uretilebilir hale gelindi

### 7. JSON cikti altyapisinin kurulmasi

Modelden cekilen tum veriler yapilandirilmis bir JSON dosyasina aktarildi.

Uretilen dosya:

- [model_data.json](c:\StarProje\model_data.json)

JSON icindeki ana bolumler:

- `model_summary`
- `zones`
- `walls`
- `roofs`
- `floors`
- `windows`
- `openings`
- `spaces`
- `materials`
- `constructions`

Eklenen iliskisel alanlara ornekler:

- duvar icin `space_name`
- duvar icin `construction_name`
- duvar icin `element_class`
- pencere icin `host_surface_name`
- pencere icin `construction_name`
- pencere icin `element_class`
- space icin `thermal_zone_name`
- construction icin `layers`

Bu yapi sayesinde veri, sonraki adimlarda tekrar tekrar islenebilecek bir arakatman haline getirilmistir.

### 8. JSON uzerinden analiz raporlarinin uretilmesi

Veri cikarma katmanindan sonra ikinci bir asama olarak, JSON uzerinden rapor ureten analiz scripti gelistirildi.

Bu is icin olusturulan dosya:

- [analyze_model_data.py](c:\StarProje\analyze_model_data.py)

Bu script asagidaki analizleri yapar:

- model ozeti
- toplam dis duvar alani
- toplam ic duvar alani
- toplam cati alani
- toplam doseme alani
- toplam dis pencere alani
- eleman siniflandirma ozeti
- zone bazinda alan ozeti
- construction kullanim ozeti
- malzeme kullanim ozeti

Bu adim ile proje yalnizca veri ureten degil, veri yorumlayan bir yapiya donusmustur.

### 9. CSV export altyapisinin eklenmesi

Verilerin Excel veya benzeri tablo araclarinda kolayca incelenebilmesi icin CSV export scripti eklendi.

Bu is icin olusturulan dosya:

- [export_model_data_to_csv.py](c:\StarProje\export_model_data_to_csv.py)

Bu script:

- `model_data.json` dosyasini okur
- her veri grubunu ayri CSV dosyasina yazar
- ciktilari [csv_output](c:\StarProje\csv_output) klasoru altinda olusturur

Uretilen baslica CSV dosyalari:

- `model_summary.csv`
- `zones.csv`
- `walls.csv`
- `roofs.csv`
- `floors.csv`
- `windows.csv`
- `openings.csv`
- `spaces.csv`
- `materials.csv`
- `constructions.csv`
- `construction_layers.csv`

CSV dosyalari `utf-8-sig` ile yazildigi icin Excel'de daha saglikli acilmasi hedeflenmistir.

## Elde Edilen Sonuclar

Su ana kadar test edilen modelden elde edilen temel ozet veriler sunlardir:

- 9 thermal zone
- 37 duvar
- 13 cati
- 10 doseme
- 16 pencere
- 17 aciklik
- 9 space
- 16 malzeme
- 11 construction
- toplam taban alani: `176.0 m2`
- toplam hacim: `528.0 m3`

Bu sonuclar, sistemin modelden hem geometrik hem de teknik verileri cekebildigini gostermektedir.

## Dosya Yapisi

| Dosya | Aciklama |
| --- | --- |
| [check_openstudio_api.py](c:\StarProje\check_openstudio_api.py) | OpenStudio Python API erisimini kontrol eder. |
| [openstudio_model_info.py](c:\StarProje\openstudio_model_info.py) | OSM modelini yukler ve temel ozet bilgilerini yazdirir. |
| [extract_openstudio_data.py](c:\StarProje\extract_openstudio_data.py) | Modelden detayli veri cikarir, siniflandirma yapar ve JSON uretir. |
| [analyze_model_data.py](c:\StarProje\analyze_model_data.py) | JSON verisi uzerinden ozet analiz raporu uretir. |
| [export_model_data_to_csv.py](c:\StarProje\export_model_data_to_csv.py) | JSON verisini CSV tablolarina aktarir. |
| [model_data.json](c:\StarProje\model_data.json) | Yapilandirilmis veri cikti dosyasi. |
| [csv_output](c:\StarProje\csv_output) | CSV export sonucu olusan tablo dosyalari. |

## Kullanim

### 1. OpenStudio API kontrolu

```powershell
python check_openstudio_api.py
```

### 2. Model ozetini alma

```powershell
python openstudio_model_info.py
```

### 3. Detayli veri cikarma ve JSON olusturma

```powershell
python extract_openstudio_data.py
```

Bu komut sonucunda:

- model verileri terminale yazdirilir
- `model_data.json` dosyasi olusturulur

### 4. JSON verisini analiz etme

```powershell
python analyze_model_data.py
```

Bu komut sonucunda:

- `model_data.json` okunur
- analiz raporu terminale yazdirilir

### 5. JSON verisini CSV olarak disa aktarma

```powershell
python export_model_data_to_csv.py
```

Bu komut sonucunda:

- `model_data.json` okunur
- `csv_output` klasoru olusturulur
- her veri grubu icin ayri CSV dosyasi uretilir

### 6. CSV dosyalarini Excel'de acma

CSV dosyalarini kullanmak icin:

- [csv_output](c:\StarProje\csv_output) klasorunu acin
- istediginiz `.csv` dosyasina cift tiklayin
- veya Excel uzerinden `Dosya > Ac` yoluyla ilgili dosyayi secin

Pratik kullanim icin one cikan dosyalar:

- [csv_output/walls.csv](c:\StarProje\csv_output\walls.csv)
- [csv_output/windows.csv](c:\StarProje\csv_output\windows.csv)
- [csv_output/spaces.csv](c:\StarProje\csv_output\spaces.csv)
- [csv_output/materials.csv](c:\StarProje\csv_output\materials.csv)
- [csv_output/construction_layers.csv](c:\StarProje\csv_output\construction_layers.csv)
