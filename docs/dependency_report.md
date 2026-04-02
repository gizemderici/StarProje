# Bagimlilik Etki Raporu

- Veri seti: `materials.csv`
- Eslesen satir sayisi: `1`
- Eslesen kosul: `name=beton`
- Degistigi varsayilan kolon: `conductivity_w_per_mk`

## name=beton

Eslesen satir:

```json
{
  "name": "beton",
  "thickness_m": "0.2",
  "conductivity_w_per_mk": "1.75",
  "thermal_resistance_m2k_per_w": ""
}
```

Dogrudan etkiler:
- `construction_layers.csv` | satir: `4` | neden: Malzeme 'beton' construction katmanlarinda referans aliniyor; 'conductivity_w_per_mk' degisimi bu katmanlarin davranisini etkiler.

Dolayli etkiler:
- `constructions.csv` | satir: `4` | neden: Malzeme etkisi once construction katmanina, ardindan ilgili construction tanimlarina yayilir.
- `walls.csv` | satir: `17` | neden: Bu veri setindeki kayitlar, etkilenen construction'lari kullandigi icin 'conductivity_w_per_mk' degisiminden dolayli olarak etkilenir.
- `floors.csv` | satir: `10` | neden: Bu veri setindeki kayitlar, etkilenen construction'lari kullandigi icin 'conductivity_w_per_mk' degisiminden dolayli olarak etkilenir.
- `roofs.csv` | satir: `13` | neden: Bu veri setindeki kayitlar, etkilenen construction'lari kullandigi icin 'conductivity_w_per_mk' degisiminden dolayli olarak etkilenir.
