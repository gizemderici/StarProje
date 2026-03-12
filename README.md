# OpenStudio OSM Veri Okuma Projesi

Bu proje, Python ve OpenStudio API kullanilarak bir `.osm` model dosyasini okumak, model icindeki temel bina verilerini cikarmak ve bu verileri JSON formatinda disa aktarmak amaciyla gelistirilmistir.

## Proje Ozeti

Bu calismada su ana kadar asagidaki adimlar tamamlanmistir:

- OpenStudio Python API'nin calisip calismadigi kontrol edildi
- `.osm` model dosyasi Python uzerinden yuklendi
- Modelin temel ozet bilgileri okundu
- Zone, space, duvar, pencere ve malzeme verileri cikartildi
- Elde edilen veriler terminale yazdirildi
- Ayni veriler JSON formatinda disa aktarildi

Bu yapi, sonraki asamalarda veri analizi, raporlama ve farkli formatlara donusum icin temel olusturmaktadir.

## Su Ana Kadar Yapilanlar

### 1. OpenStudio API kontrolu

Ilk olarak OpenStudio Python API'nin ortamda erisilebilir olup olmadigini kontrol etmek icin bir test scripti hazirlandi.

Dosya:

- [check_openstudio_api.py](c:\StarProje\check_openstudio_api.py)

Bu script:

- `openstudio` modulunu import etmeyi dener
- import basariliysa OpenStudio surumunu yazdirir
- import basarisizsa hata mesaji verir

Bu adim ile Python tarafinda OpenStudio API'nin kullanilabilir oldugu dogrulanmistir.

### 2. OSM modelinin yuklenmesi

Sonraki adimda `.osm` dosyasini yukleyip modelin temel bilgilerini gosteren script olusturuldu.

Dosya:

- [openstudio_model_info.py](c:\StarProje\openstudio_model_info.py)

Bu script:

- `VersionTranslator` kullanarak modeli acar
- model basarili yuklenirse temel model bilgilerini yazar

Yazdirilan temel bilgiler:

- OpenStudio surumu
- Space sayisi
- Thermal Zone sayisi
- Surface sayisi
- Construction sayisi
- Material sayisi

Bu asamada modelin Python ve OpenStudio API ile dogru sekilde okunabildigi goruldu.

### 3. Detayli model verilerinin cikartilmasi

Model icindeki daha ayrintili verileri cekmek icin yeni bir script gelistirildi.

Dosya:

- [extract_openstudio_data.py](c:\StarProje\extract_openstudio_data.py)

Bu script ile su bilgiler alinmaktadir:

- Zone bilgileri
- Duvar bilgileri
- Pencere bilgileri
- Space bilgileri
- Alan bilgileri
- Hacim bilgileri
- Malzeme bilgileri

### 4. Teknik sorunlarin cozulmesi

Gelistirme sirasinda OpenStudio Python binding yapisina bagli bazi teknik sorunlar cozuldu.

#### `openstudio.path(...)` kullanimi

`.osm` dosya yolu OpenStudio'nun bekledigi formatta verilerek model yukleme duzeltildi.

#### Optional sayisal degerlerin okunmasi

Bazi OpenStudio fonksiyonlari dogrudan sayi yerine `OptionalDouble` dondurdugu icin yardimci fonksiyonlar eklendi.

Bu sayede:

- veri varsa sayi olarak kullaniliyor
- veri yoksa hata vermek yerine `N/A` veya `None` donuluyor

Bu duzeltme ozellikle su alanlarda gerekli oldu:

- zone volume
- space volume
- floor area
- gross area
- azimuth

#### Malzeme donusum metodlarinin uyarlanmasi

OpenStudio Python API'de malzeme tip donusum metodlari Python binding kurallarina gore kullanildi.

Ornek:

- `to_StandardOpaqueMaterial()`
- `to_MasslessOpaqueMaterial()`
- `to_SimpleGlazing()`

Bu sayede malzeme verileri script tarafinda dogru okunabilir hale getirildi.

## Elde Edilen Veriler

Calistirilan modelden su ozet veriler alinmistir:

- 9 thermal zone
- 37 duvar
- 16 pencere
- 9 space
- 16 malzeme
- toplam taban alani: `176.0 m2`
- toplam hacim: `528.0 m3`

Ayrica su detaylar da listelenebilmektedir:

- Zone bazinda bagli space sayisi
- Duvar bazinda alan, sinir kosulu ve azimut
- Pencere bazinda alan ve tip
- Space bazinda alan ve hacim
- Malzeme bazinda kalinlik, iletkenlik veya thermal resistance gibi ozellikler

## JSON Ciktisi

Modelden cekilen veriler yalnizca terminale yazdirilmakla kalmamis, ayni zamanda JSON formatinda kaydedilecek sekilde gelistirilmistir.

Uretilen dosya:

- [model_data.json](c:\StarProje\model_data.json)

JSON dosyasinda su bolumler bulunmaktadir:

- `model_summary`
- `zones`
- `walls`
- `windows`
- `spaces`
- `materials`

Ayrica nesneler arasi iliskiler de eklenmistir:

- duvar icin `space_name`
- duvar icin `construction_name`
- pencere icin `host_surface_name`
- pencere icin `construction_name`
- space icin `thermal_zone_name`
- zone icin `space_names`

Bu yapi sayesinde veriler sonraki asamalarda kolayca filtrelenebilir, analiz edilebilir ve farkli formatlara donusturulebilir.

## Dosya Yapisi

| Dosya | Aciklama |
| --- | --- |
| [check_openstudio_api.py](c:\StarProje\check_openstudio_api.py) | OpenStudio Python API'nin erisilebilir olup olmadigini kontrol eder. |
| [openstudio_model_info.py](c:\StarProje\openstudio_model_info.py) | OSM modelini yukler ve temel ozet bilgileri yazdirir. |
| [extract_openstudio_data.py](c:\StarProje\extract_openstudio_data.py) | Detayli model verilerini ceker ve JSON cikti uretir. |
| [model_data.json](c:\StarProje\model_data.json) | Uretilen yapilandirilmis veri dosyasidir. |

## Nasil Calistirilir

### OpenStudio API kontrolu

```powershell
python check_openstudio_api.py
```

### Model ozetini alma

```powershell
python openstudio_model_info.py
```

### Detayli veri cikarma ve JSON olusturma

```powershell
python extract_openstudio_data.py
```

Bu komut sonucunda:

- terminale model verileri yazdirilir
- `model_data.json` dosyasi olusturulur

## Sonraki Adimlar

Bu altyapi bir sonraki asamada su gelistirmeler icin uygundur:

- Construction katmanlarini cikarma
- Yapi elemanlarini zone ve space ile daha detayli esleme
- CSV veya Excel ciktilari olusturma
- Enerji analizi icin veri hazirlama
