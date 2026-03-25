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

## Simulasyona Etkili Alanlar

Bu bolum, simulasyon sonucunu dogrudan veya dolayli etkileyebilecek veri alanlarini ayirmak icin hazirlanmistir. Amac, kontrolsuz veri degisikligi yapilmasini onlemek ve hangi alanlarin teknik olarak dikkatle ele alinmasi gerektigini netlestirmektir.

### Degistirilebilir alanlar

Bu alanlar simulasyona etki eder ve teknik amacla degistirilebilir; ancak degisiklikler bilincli yapilmalidir.

| Veri grubu | Alan | Teknik aciklama |
| --- | --- | --- |
| `materials.csv` | `thickness_m` | Malzeme katman kalinligini belirler; isi iletimi ve toplam katman direncini etkiler. |
| `materials.csv` | `conductivity_w_per_mk` | Malzemenin isil iletkenligidir; U-degeri ve isi gecisi hesaplarina etki eder. |
| `materials.csv` | `thermal_resistance_m2k_per_w` | Kutlesiz malzemelerde isi direnci olarak kullanilir; kabuk performansini dogrudan etkiler. |
| `materials.csv` | `u_factor_w_per_m2k` | Camsi veya pencere bilesenlerinde isi gecis katsayisidir; pencere performansini etkiler. |
| `materials.csv` | `shgc` | Gunes kazancini belirler; gunes yukleri ve ic kazanc uzerinde etkilidir. |
| `constructions.csv` | `name` | Construction atamasinda referans olarak kullanilir; degisirse bagli yuzey ve katman eslesmeleri gozden gecirilmelidir. |
| `construction_layers.csv` | `layer_index` | Katman sirasini belirler; katman dizilimi degistiginde construction davranisi etkilenebilir. |
| `construction_layers.csv` | `name` | Katmanda hangi malzemenin kullanildigini belirler; malzeme degisimi construction performansini degistirir. |
| `construction_layers.csv` | `thickness_m` | Katman bazli kalinlik bilgisidir; toplam construction direncini etkiler. |
| `construction_layers.csv` | `conductivity_w_per_mk` | Katman bazli iletkenliktir; isi gecis hesabina dogrudan etkir. |
| `construction_layers.csv` | `thermal_resistance_m2k_per_w` | Kutlesiz katmanlar icin isi direncidir; construction davranisini dogrudan etkiler. |
| `construction_layers.csv` | `u_factor_w_per_m2k` | Cam katman veya glazing benzeri katmanlarda isi gecisini etkiler. |
| `construction_layers.csv` | `shgc` | Gunes kazanciyla ilgili katman davranisini etkiler. |
| Yuzey CSV'leri (`walls.csv`, `floors.csv`, `roofs.csv`, `windows.csv`) | `construction_name` | Yuzeye atanan construction'i belirler; dogrudan simulasyon girdisini degistirir. |

### Sabit kalmali veya dikkatle korunmali alanlar

Bu alanlar genelde kimlik, iliski, siniflandirma veya turetilmis bilgi niteligindedir. Rastgele degistirilmeleri onerilmez.

| Veri grubu | Alan | Teknik aciklama |
| --- | --- | --- |
| `materials.csv` | `name` | Malzeme referans adidir; degisirse construction ve katman baglantilari bozulabilir. |
| `materials.csv` | `type` | OpenStudio malzeme tipidir; veri yorumlama mantigini belirler, gelisiguzel degistirilmemelidir. |
| `constructions.csv` | `type` | Construction nesne tipidir; sistem tarafindan yorumlanan yapi bilgisidir. |
| `constructions.csv` | `layer_count` | Turetilmis alandir; katman listesinden hesaplanir, elle bakimi onerilmez. |
| `construction_layers.csv` | `construction_name` | Katmanin ait oldugu construction referansidir; dikkatli degistirilmelidir. |
| `construction_layers.csv` | `construction_type` | Turetilmis/teknik tip bilgisidir; elle degistirilmesi onerilmez. |
| `construction_layers.csv` | `type` | Katman malzeme tipidir; teknik veri yorumunu degistirebilir, kontrollu ele alinmalidir. |
| `walls.csv`, `floors.csv`, `roofs.csv` | `surface_type` | Yuzey tipi sinifidir; genelde model geometrisinden gelir ve sabit kabul edilmelidir. |
| `walls.csv`, `floors.csv`, `roofs.csv`, `windows.csv`, `openings.csv` | `element_class` | Script tarafindan uretilen siniflandirma bilgisidir; simulasyon girdisi degil, analiz etiketidir. |
| `walls.csv`, `floors.csv`, `roofs.csv` | `outside_boundary_condition` | Geometrik/iliskisel sinir kosuludur; ana kaynagi modeldir, CSV uzerinden rastgele degistirilmemelidir. |
| `walls.csv`, `floors.csv`, `roofs.csv` | `space_name` | Mekan baglantisini gosterir; iliski alanidir, yanlis degisiklik model bagini bozar. |
| `windows.csv`, `openings.csv` | `host_surface_name` | Acikligin bagli oldugu ana yuzeyi tanimlar; referans bilgisidir. |

### Kisa kontrol kurali

- Isil davranis, gunes kazanci veya construction atamasi degistirecek alanlar simulasyona etkilidir.
- Kimlik, baglanti, siniflandirma ve turetilmis alanlar varsayilan olarak sabit kabul edilmelidir.
- Bir alan degistirilmeden once, ayni alanin baska bir CSV veya JSON iliskisini etkileyip etkilemedigi kontrol edilmelidir.

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
| [apply_update_scenarios.py](c:\StarProje\apply_update_scenarios.py) | Parametreli senaryolarla toplu CSV guncellemesi yapar ve ayri cikti uretir. |
| [apply_scenario_definition.py](c:\StarProje\apply_scenario_definition.py) | JSON tabanli senaryo dosyasini okuyup veri guncellemesi uygular. |
| [build_simulation_output.py](c:\StarProje\build_simulation_output.py) | Senaryo tanimindan simulasyon icin tekrar edilebilir cikti paketi uretir. |
| [validate_csv_data.py](c:\StarProje\validate_csv_data.py) | CSV dosyalarinda eksik kolon, bos alan, sayisal format ve tekrarli kayit denetimi yapar. |
| [compare_csv_versions.py](c:\StarProje\compare_csv_versions.py) | Bir CSV dosyasinin eski ve yeni surumu arasindaki farklari raporlar. |
| [nicegui_csv_viewer.py](c:\StarProje\nicegui_csv_viewer.py) | CSV dosyalarini NiceGUI ile secip tablo olarak gosterir. |
| [scenario_definitions](c:\StarProje\scenario_definitions) | Standart simulasyon senaryo tanim dosyalarini icerir. |
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

### 6.1 Rainbow CSV ile hizli kontrol

Gelistirme sirasinda CSV dosyalarindaki veri hatalarini erken fark etmek icin Rainbow CSV kullanimini standart yaklasim olarak benimsemek onerilir.

Kisa kullanim:

- VS Code icinde ilgili `.csv` dosyasini acin
- Rainbow CSV eklentisinin delimiter algilamasini kontrol edin
- bu projedeki CSV dosyalari varsayilan olarak `,` delimiter kullanir
- kolonlari renkli gorunumde satir satir inceleyin
- supheli kayitlarda ayni kolonu asagi dogru takip ederek tutarsizlik arayin

Oncelikli kontrol edilmesi gereken CSV dosyalari:

- [csv_output/materials.csv](c:\StarProje\csv_output\materials.csv)
- [csv_output/construction_layers.csv](c:\StarProje\csv_output\construction_layers.csv)
- [csv_output/walls.csv](c:\StarProje\csv_output\walls.csv)
- [csv_output/floors.csv](c:\StarProje\csv_output\floors.csv)
- [csv_output/windows.csv](c:\StarProje\csv_output\windows.csv)

Kolon bazli kontrol yaklasimi:

- `materials.csv`:
- `name` ve `type` kolonlarinin bos olmadigini kontrol edin
- `thickness_m`, `conductivity_w_per_mk`, `thermal_resistance_m2k_per_w` kolonlarinda sayisal format ve beklenmeyen bosluklari kontrol edin
- benzer malzeme adlarinda yazim farki veya tekrar kayit olup olmadigina bakin

- `construction_layers.csv`:
- `construction_name`, `layer_index`, `name` kolonlarini birlikte izleyin
- ayni construction icinde katman sirasinin bozulup bozulmadigini kontrol edin
- `thickness_m` ve `conductivity_w_per_mk` kolonlarinda katman tipine uymayan bos veya hatali degerleri arayin

- `walls.csv`, `floors.csv`, `windows.csv`:
- `name` ve bagli iliski kolonlarini (`space_name`, `construction_name`, `host_surface_name`) kontrol edin
- alan kolonlarinda (`gross_area_m2`) metin, bosluk veya beklenmeyen sifir degerleri gozden gecirin
- `element_class` ve `surface_type` gibi siniflandirma kolonlarinda beklenmeyen deger olup olmadigina bakin

Pratik notlar:

- Rainbow CSV, kolon kaymalarini ve delimiter kaynakli bozulmalari erken fark etmek icin ozellikle faydalidir
- once renkli kolon kontrolu, sonra `validate_csv_data.py` gibi script tabanli dogrulama kullanmak daha hizli bir akis saglar
- cikti CSV dosyalarinda beklenmeyen kolon sayisi veya hizalama bozulmasi gorurseniz once delimiter ayarini kontrol edin

### 6.2 NiceGUI ile CSV izleme

CSV verilerini ve veri degisikliklerini tarayabilmek icin baslangic seviyesinde bir NiceGUI arayuzu eklenmistir.

Ilk surumde arayuz:

- ana ekran acar
- kullanicinin CSV dosyasi secmesini saglar
- secilen CSV dosyasini tablo olarak gosterir

Desteklenen kaynaklar:

- `csv_output` altindaki CSV dosyalari
- `simulation_outputs` altindaki CSV dosyalari

Calistirma ornegi:

```powershell
python nicegui_csv_viewer.py
```

Not:

- NiceGUI kurulumu yoksa once `pip install nicegui` gerekebilir
- performans icin ilk surumde tabloda en fazla ilk 200 satir gosterilir
- amac sade ama calisir bir izleme iskeleti sunmaktir

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
- her alan degisikligi icin ayri bir log kaydi olusturur

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

Varsayilan olarak log dosyasi, cikti CSV ile ayni klasorde `*_changes.csv` adiyla olusur. Ornek:

- cikti: `csv_output/materials_updated.csv`
- log: `csv_output/materials_updated_changes.csv`

Istenirse `--log-output` ile JSON veya CSV log yolu acikca verilebilir:

```powershell
python update_csv_fields.py `
  --input csv_output/materials.csv `
  --output csv_output/materials_updated.csv `
  --log-output csv_output/materials_updated_changes.json `
  --match-column name `
  --match-value tugla `
  --set thickness_m=0.22
```

Uretilen log kayitlarinda en az su alanlar yer alir:

- `dosya`
- `satir`
- `kolon`
- `eski_deger`
- `yeni_deger`

### 8. Senaryo bazli toplu veri guncelleme

`apply_update_scenarios.py`, tek tek manuel degisiklik yerine parametreli senaryolarla toplu veri guncellemesi yapar. Her senaryo:

- belirli bir kosula uyan satirlari topluca gunceller
- ayri bir cikti CSV dosyasi uretir
- ayri bir degisiklik logu olusturur

Genel kullanim:

```powershell
python apply_update_scenarios.py `
  --scenario SENARYO_ADI `
  --input GIRDI_DOSYASI `
  --output CIKTI_DOSYASI `
  --param anahtar=deger `
  --param anahtar=deger
```

Ilk surumde tanimli 3 ornek senaryo vardir:

1. `insulation_thickness_boost`

Amac:
- izolasyon veya yalitim iceren malzemelerin kalinligini carpana gore artirmak

Parametreler:
- `factor`: zorunlu, carpim katsayisi
- `keywords`: istege bagli, varsayilan `izolasyon,yalitim`

Ornek:

```powershell
python apply_update_scenarios.py `
  --scenario insulation_thickness_boost `
  --input csv_output/materials.csv `
  --output csv_output/materials_insulation_boost.csv `
  --param factor=1.15
```

2. `material_conductivity_override`

Amac:
- secilen malzemelerin iletkenlik degerlerini topluca degistirmek

Parametreler:
- `names`: zorunlu, virgul ile ayrilmis malzeme adlari
- `value`: zorunlu, yeni iletkenlik degeri

Ornek:

```powershell
python apply_update_scenarios.py `
  --scenario material_conductivity_override `
  --input csv_output/materials.csv `
  --output csv_output/materials_conductivity_override.csv `
  --param names=tugla,beton `
  --param value=0.65
```

3. `construction_layer_update`

Amac:
- belirli bir construction icindeki secili katmanlari topluca guncellemek

Parametreler:
- `construction_name`: zorunlu
- `layer_name`: istege bagli
- `layer_index`: istege bagli
- `thickness_delta`: istege bagli, mevcut kalinliga eklenir
- `conductivity_value`: istege bagli, iletkenligi dogrudan bu degere ceker

Not:
- `layer_name` veya `layer_index` parametrelerinden en az biri verilmelidir
- `thickness_delta` veya `conductivity_value` parametrelerinden en az biri verilmelidir

Ornek:

```powershell
python apply_update_scenarios.py `
  --scenario construction_layer_update `
  --input csv_output/construction_layers.csv `
  --output csv_output/construction_layers_updated.csv `
  --param construction_name=disduvar `
  --param layer_name=izolasyon kopugu `
  --param thickness_delta=0.02
```

Bu senaryolar, ozellikle simulasyon oncesi alternatif malzeme ve katman varyasyonlari hazirlamak icin kullanilabilir.

### 9. CSV veri dogrulama

`validate_csv_data.py`, CSV dosyalarindaki eksik veri, hatali format ve tekrar eden kayitlari otomatik olarak tespit eder.

Ilk surumde yalnizca `csv_output/materials.csv` dosyasi desteklenir.

Bu script su kontrolleri yapar:

- gerekli kolonlar var mi
- kritik alanlar bos mu
- sayisal alanlarda gecersiz veri var mi
- tekrar eden kayit var mi

Terminale yazdirma ornegi:

```powershell
python validate_csv_data.py `
  --input csv_output/materials.csv
```

Raporu dosyaya yazdirma ornegi:

```powershell
python validate_csv_data.py `
  --input csv_output/materials.csv `
  --report-output csv_output/materials_validation_report.json
```

veya

```powershell
python validate_csv_data.py `
  --input csv_output/materials.csv `
  --report-output csv_output/materials_validation_report.csv
```

Ilk surumde `materials.csv` icin uygulanan kurallar:

- gerekli kolonlar: `name`, `type`, `thickness_m`, `conductivity_w_per_mk`, `thermal_resistance_m2k_per_w`
- kritik alanlar: `name`, `type`
- sayisal alanlar: `thickness_m`, `conductivity_w_per_mk`, `thermal_resistance_m2k_per_w`
- tekrar kontrolu: `name` kolonuna gore

Raporlanan baslica sorun kategorileri:

- `eksik_kolon`
- `bos_kritik_alan`
- `gecersiz_sayisal_deger`
- `tekrarli_kayit`

### 10. CSV surum karsilastirma

`compare_csv_versions.py`, bir CSV dosyasinin eski ve yeni surumu arasindaki farklari otomatik olarak gosterir.

Ilk surumde yalnizca `materials.csv` icin karsilastirma desteklenir.

Bu script su farklari raporlar:

- eklenen satirlar
- silinen satirlar
- degisen hucreler

Terminale yazdirma ornegi:

```powershell
python compare_csv_versions.py `
  --old csv_output/materials.csv `
  --new csv_output/materials_updated.csv
```

Raporu dosyaya yazdirma ornegi:

```powershell
python compare_csv_versions.py `
  --old csv_output/materials.csv `
  --new csv_output/materials_updated.csv `
  --report-output csv_output/materials_diff_report.json
```

veya

```powershell
python compare_csv_versions.py `
  --old csv_output/materials.csv `
  --new csv_output/materials_updated.csv `
  --report-output csv_output/materials_diff_report.csv
```

Ilk surumde `materials.csv` icin eslestirme anahtari:

- `name`

Okunabilir rapor icerigi:

- eklenen kayitlarda anahtar ve yeni satir verisi
- silinen kayitlarda anahtar ve eski satir verisi
- degisen hucrelerde kolon, eski deger ve yeni deger bilgisi

### 11. Standart simulasyon senaryo formati

Simulasyon akisi ile otomatik veri guncelleme arasinda ortak bir format kullanmak icin JSON tabanli senaryo tanimi eklenmistir.

Bu formatin amaci:

- hangi dosyanin guncellenecegini standartlastirmak
- hangi alanlarin hangi degerlere degisecegini acikca yazmak
- Python tarafinda dogrudan okunabilir bir yapi saglamak

Senaryo JSON icindeki temel alanlar:

| Alan | Aciklama |
| --- | --- |
| `scenario_name` | Senaryonun kisa adi |
| `description` | Senaryonun teknik amaci |
| `input` | Girdi CSV dosyasi |
| `output` | Uretilecek yeni CSV dosyasi |
| `log_output` | Uretilecek log dosyasi |
| `operations` | Uygulanacak degisikliklerin listesi |

Her `operation` icinde su alanlar bulunur:

| Alan | Aciklama |
| --- | --- |
| `name` | Islem adi |
| `match.column` | Hangi kolona gore satir secilecegi |
| `match.value` | Hangi degerin aranacagi |
| `updates` | Hangi alanlarin hangi yeni degerlere guncellenecegi |

Ornek senaryo dosyasi:

- [materials_upgrade_scenario.json](c:\StarProje\scenario_definitions\materials_upgrade_scenario.json)

Bu ornek dosyada:

- `tugla` kaydinin `thickness_m` alani `0.22` yapilir
- `beton` kaydinin `conductivity_w_per_mk` alani `1.9` yapilir

Senaryo dosyasini calistirmak icin:

```powershell
python apply_scenario_definition.py `
  --scenario-file scenario_definitions/materials_upgrade_scenario.json
```

Bu komut sonucunda:

- senaryo JSON dosyasi okunur
- ilgili CSV kayitlari guncellenir
- yeni cikti dosyasi olusturulur
- degisiklik logu uretilir

Ilk surumde bu yapi `materials.csv` ve `construction_layers.csv` gibi `update_csv_fields.py` tarafindan desteklenen CSV yapilarini kullanacak sekilde tasarlanmistir.

### 12. Simulasyon icin cikti uretme akisi

Guncellenen veri setlerinden simulasyon icin kullanilacak ciktiyi standart ve tekrar edilebilir bicimde uretmek icin `build_simulation_output.py` eklenmistir.

Bu akis:

- JSON senaryo tanimini alir
- veri guncellemesini uygular
- senaryo bazli cikti dosyasi uretir
- log ve manifest dosyasi olusturur

Ornek kullanim:

```powershell
python build_simulation_output.py `
  --scenario-file scenario_definitions/materials_upgrade_scenario.json
```

Bu komut sonucunda varsayilan olarak su yapi olusur:

- `simulation_outputs/materials_upgrade_scenario/materials_upgrade_scenario__materials.csv`
- `simulation_outputs/materials_upgrade_scenario/materials_upgrade_scenario__changes.json`
- `simulation_outputs/materials_upgrade_scenario/materials_upgrade_scenario__manifest.json`

Bu isimlendirme sayesinde:

- dosya adi senaryo bazli olur
- ayni senaryo ayni yapida tekrar calistirilabilir
- veri cikti, log ve ozet bilgi tek klasorde toplanir

Manifest dosyasi su bilgileri ozetler:

- senaryo adi
- kullanilan senaryo dosyasi
- girdi veri seti
- uretilecek cikti veri seti
- log dosyasi
- degisen alan sayisi
