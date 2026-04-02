# CSV Bagimlilik Analizi

Bu dokuman, `csv_output` altindaki veri setleri icin ilk bagimlilik haritasini tanimlar.
Amac, tek bir deger degistiginde hangi kayitlarin dogrudan ve dolayli etkilenebilecegini ortak bir dille gostermektir.

## Kapsamdaki ana veri setleri

- `materials.csv`
- `construction_layers.csv`
- `constructions.csv`
- `walls.csv`
- `floors.csv`
- `roofs.csv`
- `windows.csv`
- `openings.csv`
- `spaces.csv`
- `zones.csv`

## Ana degistirilebilir alanlar

### `materials.csv`

- `name`
- `thickness_m`
- `conductivity_w_per_mk`
- `thermal_resistance_m2k_per_w`
- `u_factor_w_per_m2k`
- `shgc`

### `construction_layers.csv`

- `construction_name`
- `layer_index`
- `name`
- `thickness_m`
- `conductivity_w_per_mk`
- `thermal_resistance_m2k_per_w`
- `u_factor_w_per_m2k`
- `shgc`

### `constructions.csv`

- `name`

### Yuzey veri setleri

- `walls.csv`: `name`, `construction_name`, `space_name`
- `floors.csv`: `name`, `construction_name`, `space_name`
- `roofs.csv`: `name`, `construction_name`, `space_name`
- `windows.csv`: `name`, `construction_name`, `host_surface_name`
- `openings.csv`: `name`, `construction_name`, `host_surface_name`

### Mekansal veri setleri

- `spaces.csv`: `name`, `thermal_zone_name`
- `zones.csv`: `name`

## Dogrudan bagimliliklar

### Malzeme zinciri

- `materials.csv.name` -> `construction_layers.csv.name`
- Bir malzeme adi katman satirlarinda referans olarak kullanilir.

### Construction zinciri

- `constructions.csv.name` -> `construction_layers.csv.construction_name`
- `constructions.csv.name` -> `walls.csv.construction_name`
- `constructions.csv.name` -> `floors.csv.construction_name`
- `constructions.csv.name` -> `roofs.csv.construction_name`
- `constructions.csv.name` -> `windows.csv.construction_name`
- `constructions.csv.name` -> `openings.csv.construction_name`

### Mekan ve zone zinciri

- `zones.csv.name` -> `spaces.csv.thermal_zone_name`
- `spaces.csv.name` -> `walls.csv.space_name`
- `spaces.csv.name` -> `floors.csv.space_name`
- `spaces.csv.name` -> `roofs.csv.space_name`

### Host surface zinciri

- `walls.csv.name` -> `windows.csv.host_surface_name`
- `walls.csv.name` -> `openings.csv.host_surface_name`

## Dolayli etki zincirleri

### 1. Malzeme ozelligi degisirse

Ornek: `materials.csv` icinde `beton.conductivity_w_per_mk` degisirse

- Dogrudan etkilenenler:
- `construction_layers.csv` icinde `name=beton` olan katmanlar

- Dolayli etkilenenler:
- Bu katmanlari kullanan `constructions.csv` kayitlari
- Bu construction'lari kullanan `walls.csv`
- Bu construction'lari kullanan `floors.csv`
- Bu construction'lari kullanan `roofs.csv`
- Bu construction'lari kullanan `windows.csv`
- Bu construction'lari kullanan `openings.csv`

### 2. Katman ozelligi degisirse

Ornek: `construction_layers.csv` icinde belirli bir katmanin `thickness_m` degeri degisirse

- Dogrudan etkilenenler:
- Ilgili `constructions.csv` kaydi
- Referanslanan `materials.csv` kaydi

- Dolayli etkilenenler:
- Ayni `construction_name` degerini kullanan tum yuzey ve alt-yuzey kayitlari

### 3. Construction adi veya atamasi degisirse

Ornek: `constructions.csv.name` veya bir yuzeyin `construction_name` degeri degisirse

- Dogrudan etkilenenler:
- Ilgili `construction_layers.csv` kayitlari
- Bu construction'a bagli tum yuzeyler

- Dolayli etkilenenler:
- Yuzeye bagli alt-yuzeyler
- Uzerinden hesaplanan analiz/rapor katmanlari

### 4. Mekan veya zone baglantisi degisirse

Ornek: `spaces.csv.thermal_zone_name` veya `zones.csv.name` degisirse

- Dogrudan etkilenenler:
- `spaces.csv`
- `walls.csv`, `floors.csv`, `roofs.csv`

- Dolayli etkilenenler:
- Zone veya mekan bazli alan/hacim analizleri

## Teknik cikti araci

Bu backlog maddesi kapsaminda `analyze_csv_dependencies.py` eklendi.

Script iki amacla kullanilir:

- Genel bagimlilik ozetini uretmek
- Belirli bir satir/deger degisiminin etki raporunu cikarmak

## Ornek kullanim

Genel bagimlilik haritasi:

```powershell
python analyze_csv_dependencies.py --format md
```

Belirli bir malzeme degisiminin etkisi:

```powershell
python analyze_csv_dependencies.py `
  --dataset materials.csv `
  --match-column name `
  --match-value beton `
  --changed-column conductivity_w_per_mk `
  --format md
```

Dosyaya yazmak icin:

```powershell
python analyze_csv_dependencies.py --format md --output docs/dependency_report.md
```

## Bu asamanin teslimati

- Ana degistirilebilir alanlar listelendi
- Dogrudan bagimliliklar tanimlandi
- Dolayli etki zincirleri ayrildi
- Teknik ekip icin tekrar kullanilabilir bir analiz scripti eklendi
- Dokumantasyon olusturuldu

## Sonraki adimlar

- Bu script ciktisini UI icinde gostermek
- Etki sonucunu grafik node-edge modeline cevirmek
- Degisim oncesi ve sonrasi farklari tek ekranda birlestirmek
