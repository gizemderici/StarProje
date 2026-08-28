# Faz 7 — Simülasyon Destekli Sayısal Doğrulama

> ## ⚠️ Bu belge önceki cepheyi anlatır
>
> Aşağıdaki dört tur, **TS 825 cam sınırı düzeltilmeden önceki** Pareto
> cephesinde yürütülmüştür. Cam sınırı düzeltilip cephe yeniden üretildikten
> sonra doğrulama yenilenememiştir: EnergyPlus, makinede Smart App Control
> tarafından engellenmektedir.
>
> **Güncel cephe doğrulanmamıştır.** Bu belge doğrulama *yöntemini* ve
> ölçülen davranışı belgeler; güncel cephenin doğruluk beyanı değildir.
>
> Ayrıntı: [ts825_duzeltmesi.md](ts825_duzeltmesi.md)

Tez başlığındaki son ifadenin karşılığı bu bölümdür: Pareto cephesinden seçilen
noktalar **gerçek EnergyPlus** ile koşulur ve vekil model tahminiyle
karşılaştırılır.

Betik: `run_validation.py` · Nokta seçimi: `validation/selection.py`
Çıktı: `data/validation/validation_report.json`, `validation_table.csv`

---

## Nokta seçimi

Seçim rastgele değildir; üç kural birlikte uygulanır:

1. **Her amacın uç noktası.** Vekil model cephenin kenarlarında en çok zorlanır.
2. **TOPSIS uzlaşı çözümü.** Tezde önerilecek çözüm budur; doğrulanması şarttır.
3. **Maksimin ile dağılım noktaları.** Cephenin orta bölgesi de temsil edilsin.

Eğitim kümesindeki çözümler aday havuzundan **çıkarılır**. Adaptif örnekleme
turlarında bu şarttır: önceki turun doğrulama noktaları eğitim kümesine
eklendiği için, yeniden seçilirlerse doğrulama dairesel hale gelir ve modelin
ezberini ölçer.

Sapma işareti tanımlıdır: **pozitif değer vekil modelin fazla tahmin ettiğini**
gösterir.

---

## Bulunan olgu: optimizasyon vekil model hatasını sömürüyor

İlk iki turun sonucu:

| Tur | Eğitim satırı | Ortalama sapma | En büyük | Sapma yönü |
|---|---|---|---|---|
| 1 | 151 | %2,72 | %5,22 | 6/8 negatif |
| 2 | 159 | %3,40 | **%8,11** | **8/8 negatif** |

Adaptif örnekleme kapıyı geçirmedi, **aksine kötüleştirdi**. 16 sapmanın 14'ü
negatifti — rastgele hata değil, sistematik yanlılık.

### Neden

NSGA-II amaç fonksiyonunu minimize ederken, modelin *gerçekten iyi* olduğu
noktalarla *modelin iyi sandığı* noktaları ayırt edemez. Az örneklenmiş bir
bölgede model iyimserse, optimizasyon tam oraya yerleşir.

Her adaptif tur cepheyi daha da dışarı ittiği için sapma büyüdü: birinci turda
en iyi EnPI 48,50 kWh/m²·yıl iken ikinci turda 44,26'ya indi. Model kendi
belirsizlik bölgesine doğru ilerledi.

Bu, vekil model tabanlı optimizasyon literatüründe bilinen bir tuzaktır ve
yöntem açısından tezin en önemli bulgularından biridir: **"vekil model eğit,
optimize et, doğrula" zinciri tek başına yeterli değildir.**

---

## Uygulanan çözüm: karamsar tahmin

Kriging yalnızca tahmin değil, tahmin **belirsizliği** de verir. Optimizasyona
ortalama yerine

```
tahmin = ortalama + k · σ
```

verilir. Model emin olmadığı yerde kendini cezalandırır ve cephe iyi
örneklenmiş bölgede kalır. Katsayı `--uncertainty-penalty` ile ayarlanır:

- `k = 0` → düz ortalama; optimizasyon hatayı sömürür (turlar 1–2)
- `k = 1` → bir standart sapma karamsar

### Etkisi

| Tur | k | Eğitim | Ortalama | En büyük | Sapma yönü | Kapı |
|---|---|---|---|---|---|---|
| 1 | 0 | 151 | %2,72 | %5,22 | 6/8 negatif | ✗ |
| 2 | 0 | 159 | %3,40 | %8,11 | 8/8 negatif | ✗ |
| 3 | 1,0 | 167 | %2,38 | %5,31 | 8/8 pozitif | ✗ |
| 4 | **0,5** | **175** | **%1,89** | **%4,57** | 7 pozitif / 1 negatif | **✓** |

Üçüncü turda yanlılık yön değiştirdi: `k = 1,0` fazla geldi ve model tutarlı
olarak yüksek tahmin etmeye başladı. `k = 0,5` ile yanlılık dengelendi ve kapı
geçildi.

**Bu bir ayardır ve tezde ayar olarak belirtilmelidir.** Dördüncü turun sekiz
doğrulama noktası, ayarın yapıldığı noktalardan tamamen farklıdır; seçim
mekanizması eğitim kümesindeki çözümleri aday havuzundan çıkarır.

---

## Vekil modelin turlar boyunca iyileşmesi

Adaptif örnekleme vekil modeli belirgin biçimde iyileştirdi:

| Tur | Eğitim | site_energy CVRMSE | R² |
|---|---|---|---|
| 1 | 151 | %6,19 | 0,972 |
| 2 | 159 | %3,87 | 0,988 |
| 3 | 167 | %2,70 | 0,994 |
| 4 | 175 | %4,56 | 0,984 |

Yani modelin kendisi mükemmele yaklaşırken doğrulama sapması aynı hızla
düşmedi. Bu da yukarıdaki teşhisi destekler: sorun modelin ortalama
doğruluğunda değil, **optimizasyonun modeli nerede sorguladığındadır.**

---

## Kapı ölçütü

Faz 7 kapısı: her doğrulama noktasında mutlak sapma **%5'in altında**.

Kapı geçilmezse iki yol vardır:

1. **Adaptif örnekleme** — sapan noktaları eğitim kümesine ekleyip Faz 4'ü
   tekrarlamak. Turlar 1→2'de görüldüğü gibi tek başına yeterli olmayabilir.
2. **Daha fazla eğitim verisi** — ikinci bir parametrik koşu turu. Pareto
   cephesinin bulunduğu bölgeye yoğunlaşmış bir tasarım en verimlisidir.

Toleransı gevşetmek çözüm değildir ve yapılmamalıdır.

---

## Nihai sonuç

**Faz 7 kapısı dördüncü turda geçildi** — düzeltme öncesi cephe için.

| case_id | Vekil | Gerçek | Sapma | Gerekçe |
|---|---|---|---|---|
| `case_eb5379b1550b` | 53,85 | 51,50 | +4,57% | uç nokta: konfor ihlali |
| `case_c7a34665633a` | 61,21 | 59,15 | +3,48% | cephe dağılımı |
| `case_e91ded845130` | 52,73 | 51,06 | +3,26% | uç nokta: EnPI |
| `case_6a20b8abe4e4` | 72,75 | 73,83 | −1,47% | TOPSIS uzlaşı çözümü |
| `case_9f6f92a7b48d` | 64,57 | 64,04 | +0,84% | cephe dağılımı |
| `case_502a05f8fd3e` | 67,26 | 66,82 | +0,66% | cephe dağılımı |
| `case_af4bc22bbcd9` | 77,83 | 77,43 | +0,51% | cephe dağılımı |
| `case_be84bc06fe25` | 110,77 | 110,37 | +0,36% | uç nokta: yatırım maliyeti |

Ortalama mutlak sapma **%1,89**, en büyük **%4,57**, tolerans %5,0.

Değerler EnPI cinsindendir (kWh/m²·yıl). Tezde önerilecek TOPSIS uzlaşı
çözümünün sapması **%1,47**'dir.

### Güncel durum

Yukarıdaki sekiz nokta, cam sınırı düzeltilmeden önceki cepheden seçilmiştir.
Düzeltilmiş cephe ile ortak noktası yoktur; `pareto_front.json` içindeki
`validated` alanı `false`'tur. Engel kalktığında tek komutla yenilenir:

```powershell
.\.venv\Scripts\python.exe .un_validation.py --points 8 --workers 4
```

### Yöntem açısından çıkarım

Vekil model tabanlı çok amaçlı optimizasyonda doğrulama, üç bileşenin
birlikte çalışmasını gerektirir:

1. **Adaptif örnekleme** — doğrulama noktalarını eğitim kümesine eklemek.
   Tek başına yeterli değildir; turlar 1→2'de sapmayı büyütmüştür.
2. **Belirsizlik cezası** — optimizasyonun modeli az örneklenmiş bölgeye
   itmesini engeller. Katsayı yanlılığı sıfırlayacak şekilde ayarlanır.
3. **Dairesel doğrulamaya karşı koruma** — eğitim kümesindeki çözümler aday
   havuzundan çıkarılır.

Bu üçü olmadan doğrulama, modelin gerçek hatasını değil ezberini ölçer.
