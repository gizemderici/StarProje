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

## Veri Sozlugu

Bu bolum, `model_data.json` ve `csv_output` altindaki temel CSV dosyalarinin alanlarini hizli okumak icin hazirlanmistir.

### Genel notlar

- `model_data.json` bu projenin ana ara veri formatidir; CSV dosyalari bu JSON'dan uretilir.
- CSV dosyalari teknik olarak duzenlenebilir, ancak `export_model_data_to_csv.py` yeniden calistirildiginda uzerine yazilir.
- Bu nedenle `csv_output` altindaki degisiklikler "kalici kaynak veri" degil, gecici tablo duzenlemesi olarak dusunulmelidir.
- `guncellenebilir` ifadesi, alanin anlamsal olarak elle guncellenmeye uygun olup olmadigini gosterir:
- `hayir (turetilmis)`: script tarafindan hesaplanir veya siniflandirilir.
- `sinirli`: referans/deger alani olarak duzenlenebilir, fakat kaynak OSM/JSON ile tutarlilik kontrolu gerekir.
- `evet`: dogrudan veri degeri olarak guncellenmesi anlamlidir.

### model_data.json

`model_data.json` su ana anahtar gruplarini icerir:

| Alan | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `model_summary` | object | Modelin sayisal ozeti ve toplamlari | hayir (turetilmis) |
| `zones` | array<object> | Thermal zone kayitlari | sinirli |
| `walls` | array<object> | Duvar yuzeyleri | sinirli |
| `roofs` | array<object> | Cati/tavan yuzeyleri | sinirli |
| `floors` | array<object> | Doseme/yuzey kayitlari | sinirli |
| `windows` | array<object> | Pencere alt-yuzeyleri | sinirli |
| `openings` | array<object> | Tum acikliklar, kapilar dahil | sinirli |
| `spaces` | array<object> | Mekan kayitlari | sinirli |
| `materials` | array<object> | Malzeme teknik verileri | evet |
| `constructions` | array<object> | Construction tanimlari ve katmanlari | evet |

### Temel CSV dosyalari

| Dosya | Amac | Birincil kullanim |
| --- | --- | --- |
| `materials.csv` | Malzeme fiziksel/termal ozellikleri | Construction ve katman analizi |
| `walls.csv` | Duvar yuzeyleri ve bagli construction bilgisi | Kabuk ve alan analizi |
| `construction_layers.csv` | Construction katmanlarini satir bazinda acar | Katman sirasi ve malzeme takibi |
| `constructions.csv` | Construction ozet listesi | Katman sayisi ve construction envanteri |
| `spaces.csv` | Mekan bazli alan ve hacim | Zone eslestirme ve alan raporu |
| `zones.csv` | Thermal zone bazli toplulastirilmis veri | Zone ozetleri |
| `windows.csv` | Pencere kayitlari | Cephe/aciklik analizi |
| `openings.csv` | Tum alt-yuzeyler | Kapi + pencere birlikte analiz |

### materials.csv

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `name` | string | Malzeme adi | evet |
| `type` | string | OpenStudio malzeme tipi (`OS_Material`, `OS_MasslessOpaqueMaterial`, `OS_SimpleGlazing` vb.) | sinirli |
| `thickness_m` | float | Katman kalinligi, metre cinsinden | evet |
| `conductivity_w_per_mk` | float | Isil iletkenlik | evet |
| `thermal_resistance_m2k_per_w` | float | Kutlesiz malzeme icin isi direnci | evet |
| `u_factor_w_per_m2k` | float | Basit camlama icin U-degeri | evet |
| `shgc` | float | Basit camlama icin solar heat gain coefficient | evet |

Not: Her satir tum kolonlari kullanmaz. Kolonlar malzeme tipine gore bos kalabilir.

### walls.csv

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `name` | string | Yuzey adi | sinirli |
| `surface_type` | string | OpenStudio yuzey tipi; bu dosyada genelde `Wall` | hayir (turetilmis) |
| `element_class` | string | Script tarafindan uretilen sinif (`dis_duvar`, `ic_duvar` vb.) | hayir (turetilmis) |
| `gross_area_m2` | float | Brut yuzey alani | sinirli |
| `outside_boundary_condition` | string | Dis sinir kosulu (`Outdoors`, `Surface` vb.) | sinirli |
| `azimuth_rad` | float | Yuzey yonlenmesi, radyan cinsinden | sinirli |
| `space_name` | string | Bagli oldugu mekan | sinirli |
| `construction_name` | string | Kullanilan construction adi | evet |

Not: `element_class`, `surface_type` ve kismen `gross_area_m2` gibi alanlar kaynaktan yeniden uretildigi icin CSV uzerinden kalici veri bakimi icin uygun degildir.

### construction_layers.csv

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `construction_name` | string | Katmanin ait oldugu construction | sinirli |
| `construction_type` | string | Construction nesne tipi | hayir (turetilmis) |
| `layer_index` | integer | Katman sirasi, 1'den baslar | evet |
| `name` | string | Katmandaki malzeme adi | evet |
| `type` | string | Katman malzeme tipi | sinirli |
| `thickness_m` | float | Katman kalinligi | evet |
| `conductivity_w_per_mk` | float | Katman malzemesinin iletkenligi | evet |
| `thermal_resistance_m2k_per_w` | float | Kutlesiz malzeme katmani isi direnci | evet |
| `u_factor_w_per_m2k` | float | Cam katman U-degeri | evet |
| `shgc` | float | Cam katman SHGC degeri | evet |

Not: Bu dosya `constructions[].layers[]` alaninin satirlastirilmis halidir; ayni construction birden fazla satirda gorunur.

### constructions.csv

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `name` | string | Construction adi | evet |
| `type` | string | Construction nesne tipi | sinirli |
| `layer_count` | integer | Katman sayisi | hayir (turetilmis) |

### spaces.csv

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `name` | string | Mekan adi | evet |
| `floor_area_m2` | float | Mekan taban alani | sinirli |
| `volume_m3` | float | Mekan hacmi | sinirli |
| `thermal_zone_name` | string | Bagli thermal zone adi | evet |

### zones.csv

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `name` | string | Thermal zone adi | evet |
| `space_count` | integer | Zone icindeki mekan sayisi | hayir (turetilmis) |
| `space_names` | string/list | Zone'a bagli mekan adlari; CSV'de ` | ` ile birlesir | hayir (turetilmis) |
| `floor_area_m2` | float | Zone toplam taban alani | hayir (turetilmis) |
| `volume_m3` | float | Zone toplam hacmi | hayir (turetilmis) |

### windows.csv ve openings.csv

Bu iki dosya ayni kolon mantigini kullanir; `windows.csv` yalnizca pencere tiplerini, `openings.csv` ise tum alt-yuzeyleri icerir.

| Kolon | Tip | Aciklama | Guncellenebilir |
| --- | --- | --- | --- |
| `name` | string | Alt-yuzey adi | sinirli |
| `sub_surface_type` | string | Alt-yuzey tipi (`FixedWindow`, `Door` vb.) | sinirli |
| `element_class` | string | Script siniflandirmasi (`dis_pencere`, `dis_kapi` vb.) | hayir (turetilmis) |
| `gross_area_m2` | float | Alt-yuzey alani | sinirli |
| `host_surface_name` | string | Bagli oldugu ana yuzey | sinirli |
| `construction_name` | string | Kullanilan construction | evet |

### roofs.csv ve floors.csv

Bu iki dosya, `walls.csv` ile ayni kolon setini kullanir:

- `name` (`string`)
- `surface_type` (`string`)
- `element_class` (`string`, turetilmis)
- `gross_area_m2` (`float`)
- `outside_boundary_condition` (`string`)
- `azimuth_rad` (`float`)
- `space_name` (`string`)
- `construction_name` (`string`)

Pratik yorum:

- `construction_name`, `thermal_zone_name`, `name` gibi baglanti ve tanim alanlari en anlamli guncellenebilir alanlardir.
- `layer_count`, `space_count`, `element_class`, `surface_type` gibi alanlar hesaplanan/turetilen alanlardir; dogrudan elle surdurulmesi onerilmez.
- Alan, hacim, azimut gibi geometrik degerler teorik olarak duzenlenebilir olsa da ana kaynak OSM modelidir; bu nedenle kalici degisiklik icin CSV degil kaynak model veya JSON uretim katmani esas alinmalidir.

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
| [update_csv_fields.py](c:\StarProje\update_csv_fields.py) | Secili CSV alanlarini kontrollu sekilde gunceller ve yeni dosyaya yazar. |
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

### 7. CSV alanlarini Python ile guncelleme

Ilk surumde `update_csv_fields.py`, yalnizca `csv_output/materials.csv` dosyasini kontrollu sekilde gunceller.

Ornek kullanim:

```powershell
python update_csv_fields.py `
  --input csv_output/materials.csv `
  --output csv_output/materials_updated.csv `
  --match-column name `
  --match-value tugla `
  --set thickness_m=0.22 `
  --set conductivity_w_per_mk=0.55
```

Bu script:

- belirtilen CSV dosyasini okur
- `match-column` ve `match-value` ile satiri bulur
- izin verilen kolonlarda degisiklik yapar
- sonucu yeni dosya adiyla kaydeder

Ilk surumde `materials.csv` icin desteklenen guncelleme kolonlari:

- `name`
- `thickness_m`
- `conductivity_w_per_mk`
- `thermal_resistance_m2k_per_w`
- `u_factor_w_per_m2k`
- `shgc`

Script su durumlarda aciklayici hata verir:

- desteklenmeyen dosya secilirse
- istenen kolon CSV icinde yoksa
- `kolon=deger` formati bozuksa
- sayisal alana gecersiz deger girilirse
- eslesen satir bulunamazsa
