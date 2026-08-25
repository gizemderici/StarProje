# Faz 2 — Measure ve Koşucu Altyapısı

Amaç: tek değişkenli (EPS) altyapıyı dokuz karar değişkenine açmak.

## Tek doğruluk kaynağı

`engine/parameters.py` dokuz karar değişkenini bir kez tanımlar. OSW adımları,
API doğrulaması ve Faz 3'ün örnekleme tasarımı aynı kayıttan beslenir; yeni bir
değişken eklemek tek satırdır.

| Anahtar | Measure | Referans | Aralık / Seçenek |
|---|---|---|---|
| `window_construction` | SetWindowConstruction | `penc_std_4mm` | 7 hazır konstrüksiyon |
| `heating_setpoint_c` | SetThermostatSetpoints | 22,0 °C | 15 – 24 |
| `cooling_setpoint_c` | SetThermostatSetpoints | 24,0 °C | 22 – 30 |
| `chiller_cop` | SetPlantEfficiency | 5,5 | 2,0 – 8,0 |
| `boiler_efficiency` | SetPlantEfficiency | 0,90 | 0,60 – 0,99 |
| `lighting_primary_w_m2` | SetLightingPower | 7,0 W/m² | 1 – 15 |
| `lighting_secondary_w_m2` | SetLightingPower | 3,0 W/m² | 0,5 – 8 |
| `eps_thickness_cm` | SetEpsThickness | 5,0 cm | 0,5 – 30 |
| `eps_conductivity_w_mk` | SetEpsThickness | 0,039 | 0,015 – 0,060 |

## Senaryo kimliği

`OpenStudioCase` artık parametre sözlüğü taşır. Kimlik, çözümlenmiş parametre
kümesinin SHA-256 özetinden türetilir:

- Aynı parametreler → aynı klasör → kesintiye uğrayan toplu koşu kaldığı yerden
  devam eder (`run_cases(skip_completed=True)`).
- Anahtar sırası kimliği etkilemez.
- Önceki `eps_10cm` deseni yalnızca tek değişkenli koşuları adlandırabiliyordu.

Belirtilmeyen parametreler referans değerle doldurulur, yani sonuç tohum modelin
o anki durumuna değil yalnızca senaryo tanımına bağlıdır.

## Tek koşu yolu

Faz 2 öncesinde aynı işi yapan iki uygulama vardı:

- `engine/openstudio_runner.py` → OSW + measure + `openstudio run`
- `services/openstudio_service.py` → `execute_python_script` → ForwardTranslator
  → doğrudan `energyplus.exe`

İkincisi kaldırıldı; `integrations/OpenStudio/simulation_api_worker.py` silindi.
Bu, her yeni measure'ın iki kez yazılması zorunluluğunu ortadan kaldırdı ve
measure ile worker arasındaki `MediumSmooth` / `MediumRough` tutarsızlığını da
kendiliğinden çözdü.

## Bulunan iki kusur

**`SetEpsThickness` OpenStudio 3.11'de hiç çalışmıyormuş.**

```
Set EPS Thickness failed: can't modify frozen Array
```

`construction.layers.to_a` donmuş bir dizi döndürüyor; `layers[index] = eps`
satırı hata veriyor. Bu satır measure'ın ilk halinde de vardı, yani bu ortamda
hiçbir zaman başarıyla koşmamış. `.dup` eklenerek giderildi.

**`measure.xml` şemaya uymuyormuş.** `<measure_type>` bu şemada üst düzey öge
değildir; tür zaten `<attribute><name>Measure Type</name>` olarak verilir. Öge
beş measure'dan da kaldırıldı.

## Duman testi

Beş measure'ı birden değiştiren tek koşu:

```
window_construction  = penc_lowe_argon_4mm
heating_setpoint_c   = 20.0      cooling_setpoint_c = 26.0
chiller_cop          = 4.0       lighting_primary_w_m2 = 5.0
```

Sonuç: yedi adımın yedisi `Success`, **0 Severe**, 4 dk 56 sn.

| Adım | Bildirilen sonuç |
|---|---|
| SetEpsThickness | `duvr_std_eps` içindeki `eps 5 cm` değiştirildi, konstrüksiyon adı korundu |
| SetWindowConstruction | 114 pencere + 8 varsayılan alan |
| SetThermostatSetpoints | 8 termostat, ölü bant 6,0 K |
| SetPlantEfficiency | 1 chiller COP 4,0 · 1 kazan verimi 0,90 |
| SetLightingPower | 1 birincil 5,0 W/m² · 1 ikincil 3,0 W/m² |

### Taban çizgisine göre fark

| Kalem (GJ/yıl) | Taban v1 | Senaryo | Fark |
|---|---|---|---|
| Soğutma | 1.119,56 | 1.276,36 | +156,80 |
| Fanlar | 239,90 | 176,02 | −63,88 |
| Aydınlatma | 230,27 | 175,53 | −54,74 |
| Isıtma | 46,20 | 0,44 | −45,76 |
| Pompalar | 22,95 | 13,06 | −9,89 |
| **Toplam saha enerjisi** | 1.920,00 | 1.902,53 | −17,47 |

Net tasarruf yalnızca %0,91. Sebep: COP'un 5,5'ten 4,0'a düşürülmesi, ayar
noktası ve aydınlatma kazançlarını neredeyse tamamen yutuyor. Değişkenlerin
birbirini dengelediğini gösteren bu davranış, Faz 6'daki çok amaçlı
optimizasyonun neden gerekli olduğunun somut kanıtıdır.

## Testler

21 test geçiyor: `tests/test_engine.py` 14, `tests/test_api_architecture.py` 7.
Yeni kapsam: measure sırası, referansa geri düşme, kimlik kararlılığı, bilinmeyen
ve sınır dışı parametre reddi, parametre kataloğu uç noktası.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Faz 3'e devir

- Örnekleme tasarımı `engine.parameters.design_space()` çıktısını kullanmalı.
- `run_cases(..., max_workers=N)` paralel çalışır, `skip_completed` ile devam eder.
- `GET /api/v1/parameters` arayüze aynı tanımı verir.
- Henüz measure'ı olmayan iki değişken: sızdırmazlık çarpanı ve asansör çalışma
  oranı. Gerekirse aynı desende eklenebilir.
