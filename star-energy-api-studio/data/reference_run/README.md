# Referans Koşu — 7 Mayıs 2026

Kanonik model `data/input/gsf_fng_6mayis.osm` ile üretilen tek doğrulanabilir
EnergyPlus koşusu. Kaynak: `Arşiv (1).zip`. Depoya alınmadan önce başka hiçbir
yerde yedeği yoktu.

| Dosya | Boyut | İçerik |
|---|---|---|
| `eplusout.sql` | 15.699.968 | Tam SQLite çıktısı |
| `hourly_zone.csv` | 2.765.705 | 8.760 satır x 17 kolon; 8 zonun saatlik sıcaklık ve bağıl nemi |
| `eplusout.err` | 9.728 | 3 Severe, 828 uyarı |
| `eplusout.eio` | 144.609 | Girdi özeti |
| `epluspsz.csv` | 26.342 | Plant boyutlandırma |
| `out.osw` | 123.694 | Tamamlanmış iş akışı |
| `workflow.osw` | 1.588 | Girdi iş akışı: `CreateCSVOutput`, `OpenStudioResults` |

## Ana sonuçlar

| Metrik | Değer |
|---|---|
| Toplam saha enerjisi | 2.128,85 GJ/yıl |
| EUI | 501,36 MJ/m²·yıl |
| Toplam bina alanı | 4.246,18 m² |
| Soğutma (elektrik) | 1.173,86 GJ (%55,1) |
| İç ekipman | 433,16 GJ (%20,3) |
| Fanlar | 239,52 GJ (%11,3) |
| İç aydınlatma | 230,27 GJ (%10,8) |
| Isıtma (doğalgaz) | 30,95 GJ (%1,5) |
| Pompalar | 21,11 GJ (%1,0) |

## Uyarı

Bu koşu **onarılmamış** model ile üretilmiştir. Faz 1 tamamlanana kadar taban
çizgisi olarak kullanılmamalıdır. Bilinen kusurlar: `docs/bulgular_faz1.md`.
