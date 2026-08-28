# TS 825 cam sınır değeri düzeltmesi

**Bulunma yolu:** Rapor kaynakçasının künyeleri doğrulanırken TS 825'in
standart metnindeki **EK 1-C** çizelgesine ulaşıldı ve koddaki sınır
değerlerle karşılaştırıldı.

---

## Hata

`optimization/objectives.py` içindeki `TS825_MAX_U` tablosu hafızadan
yazılmıştı ve **pencere sütunu tamamen yanlıştı**.

| Bölge | Kod (duvar) | Standart (duvar) | Kod (pencere) | Standart (pencere) |
|---|---|---|---|---|
| 1 | 0,70 | **0,80** | 2,40 | **2,80** |
| 2 | 0,60 | 0,60 ✓ | 2,40 | **2,80** |
| 3 | 0,50 ✓ | 0,50 ✓ | **2,00** | **2,80** |
| 4 | 0,40 | 0,40 ✓ | 1,80 | **2,80** |

Çalışmada kullanılan 3. bölgede **duvar değeri doğruydu**; hata yalnızca
pencerededir. Standardın çizelgesinde pencere değeri dört iklim bölgesinde de
2,80 W/m²K'dir ve bu değer tek bir cam türü için verilmiştir; diğer kapı ve
pencere türlerinin katsayıları TS 2164'ten alınır.

---

## Birinci sonuç: yanlış bir uygunsuzluk iddiası

Taban camının ölçülen değeri **U = 2,718 W/m²K**'dir.

| | Sınır | Sonuç |
|---|---|---|
| Hatalı sürüm | 2,00 | uygun **değil** |
| Doğru sürüm | **2,80** | **uygun** |

README, proje sonuç raporu ve tez tartışması, taban camının TS 825'i
sağlamadığını yazıyordu. **Bu iddia yanlıştı ve düzeltilmiştir.** Bina kabuğu
hem opak duvarda hem camda standardı zaten sağlamaktadır.

### Ana bulguya etkisi

Merkezî bulgu — yalıtım kalınlığının bu binada belirleyici olmadığı — **ayakta
kalmaktadır**; çünkü o bulgu iki bağımsız kanıta dayanır ve ikisi de bu
hatadan etkilenmez:

1. Sobol duyarlılık analizi: EPS kalınlığı S₁ = 0,0002, on bir değişken
   arasında sonuncu.
2. SEU dağılımı: soğutma %58,3, ısıtma %2,4.

Değişen, **üçüncü kanıt hattının yönüdür**. Önceki metin "duvar uygun, cam
uygun değil → kaldıraç camda" diyordu. Doğrusu: "kabuk her iki bileşende de
uygun → mevzuata uyum gerekçesiyle kabuk yenilemesinin dayanağı yok". Cam
değişimi hâlâ savunulabilir, ancak gerekçesi uygunluk değil, **güneş
kazancının azaltılmasıyla elde edilecek soğutma tasarrufudur** (cam tipi
duyarlılık sıralamasında üçüncü basamaktadır, S₁ = 0,1234).

---

## İkinci sonuç: Pareto cephesinin maliyet ekseni etkilenmiştir

Hatalı 2,00 sınırı, **taban camının korunmasını yasaklıyordu**: mevcut
`penc_std_4mm` (U = 2,718) kısıtı ihlal ettiği için optimizasyonun erişebildiği
her çözüm bir pencere değişimi içermek zorundaydı.

İşlenmiş cephedeki 80 çözümün cam dağılımı bunu doğrular:

| Cam tipi | Çözüm sayısı |
|---|---|
| `penc_cont_6_4mm` | 71 |
| `penc_lowe_4mm` | 9 |
| `penc_std_4mm` (taban, maliyet 0) | **0** |

Cam alanı 1.628,77 m² olduğundan bu, her çözüme yaklaşık 1,5 milyon TL'lik bir
zorunlu yatırım tabanı bindirmektedir. Cephedeki en düşük maliyet ≈ 1,46 milyon
TL'dir ve bu taban **fiziksel bir sınır değil, hatalı bir kısıtın sonucudur**.

Kısıt hiçbir çözümde bağlayıcı olmamıştır (80 çözümün 80'inde gevşeklik
vardır), yani cephedeki çözümlerin **tamamı doğru sınıra göre de uygundur**.
Sonuçlar geçersiz değildir; ancak cephe **eksiktir**: doğru sınırla birlikte,
mevcut camın korunduğu düşük maliyetli bir bölge açılacaktır.

---

## Durum — cephe yeniden üretildi, doğrulama engellendi

| Öge | Durum |
|---|---|
| `TS825_MAX_U` tablosu | düzeltildi |
| Testler | düzeltildi; sınır üstü camı eleyen yeni test eklendi |
| README, rapor Bölüm 5.1 / 6.1 | düzeltildi |
| Rapor Bölüm 5.4 | **eklendi** — hatanın cepheye etkisi |
| `pareto_front.json` | **doğru sınırla yeniden üretildi** |
| `validation_report.json` | **eski cepheye ait** — yenilenemedi |

### Yeniden üretilen cephenin karşılaştırması

| Ölçüt | Düzeltme öncesi (2,00) | Düzeltme sonrası (2,80) |
|---|---|---|
| En düşük EnPİ | 52,73 kWh/m²·yıl | **46,38 kWh/m²·yıl** |
| En düşük yatırım | 1,466 milyon TL | **0 TL** |
| En yüksek yatırım | 4,253 milyon TL | 5,061 milyon TL |
| Mevcut camı koruyan çözüm | 0 / 80 | **28 / 80** |
| Cam dağılımı | `cont_6_4mm` 71, `lowe_4mm` 9 | `cont_6_4mm` 52, **`std_4mm` 28** |

Öngörü doğrulandı: doğru sınırla mevcut camın korunduğu **sıfır maliyetli**
bölge açıldı ve erişilebilir en iyi EnPİ değeri iyileşti.

### Doğrulama neden yapılamadı

Yeni cephenin Faz 7 doğrulaması başlatıldı, ancak sekiz koşunun sekizi de
başarısız oldu:

```
Found error in state 'EnergyPlus' with message:
  'CreateProcess failed: An Application Control policy has blocked this file.'
```

Makinede **Windows Application Control politikası `energyplus.exe`
dosyasının çalıştırılmasını engelliyor**. Aynı politika OpenStudio'nun Python
bağındaki `_openstudioairflow` DLL'ini de engellemektedir; bu nedenle
`tests/test_api_architecture.py::OpenStudioApiServiceTests` de hata vermektedir.
OpenStudio komut satırı aracının kendisi (`openstudio.exe --version`) çalışır
durumdadır; engellenen yalnızca EnergyPlus çalıştırılabiliridir.

Bu bir güvenlik politikasıdır ve aşılmaya çalışılmamıştır. Çözüm için
`C:\Program Files\openstudio-3.11.0\EnergyPlus\energyplus.exe` dosyasının
politikada izinli hale getirilmesi gerekir.

Engel kalktığında:

```powershell
.\.venv\Scripts\python.exe .\run_validation.py --points 8 --workers 4
```

```powershell
.\.venv\Scripts\python.exe -m reporting.sonuc_raporu
```

### Bu arada rapor ne söylüyor

Rapor, güncel cepheyi doğrulanmış gibi sunmaz. Bölüm 4.5'te cephenin
doğrulama beklediği açıkça yazılıdır; Bölüm 4.6'daki doğrulama sonuçları ise
önceki cepheye ait olduğu belirtilerek, yöntemin kurulumunu belgelemek üzere
korunmuştur. `pareto_front.json` içindeki `validated` alanı `false`'tur.

### Yol boyunca bulunan ikinci kusur

Başarısız doğrulama koşusu, mevcut doğrulama raporunun üzerine **sıfır nokta
ve `within_tolerance: true`** yazdı — yani hiçbir koşusu başarılı olmayan bir
doğrulama, kapıyı geçmiş gibi göründü. İki düzeltme yapıldı:

- `validation/selection.py::summarise` — sıfır nokta artık kapıyı geçemez.
- `run_validation.py` — hiçbir koşu hasat edilemediğinde mevcut rapor
  korunur, üzerine yazılmaz.

Bu davranışı kodlayan test (`test_empty_input_is_handled`) de düzeltildi.

## Ayrıca: standardın güncel sürümü

TS 825'in **Ekim 2024** revizyonu **1 Nisan 2025**'te yürürlüğe girmiştir ve
daha sıkı U değerleri içerir (duvar ve döşemede yaklaşık %37,5, çatı ve
pencerede %25 iyileştirme bildirilmektedir). Yukarıdaki tablo önceki sürüme
aittir.

Aynı şekilde **ISO 50006:2014**, 2023'te ikinci baskıyla değiştirilmiştir
(*Evaluating energy performance using energy performance indicators and energy
baselines*). Kaynakça buna göre güncellenmiştir.

Her iki sınır değer kümesi de **standardın resmî nüshasından** teyit
edilmelidir; buradaki değerler standart metninin EK 1-C çizelgesinden
okunmuştur, güncel revizyona göre denetlenmemiştir.
