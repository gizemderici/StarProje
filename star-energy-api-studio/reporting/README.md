# Proje Sonuç Raporu üreteci

TÜBİTAK ARDEB Proje Sonuç Raporu'nu, analiz adımlarının ürettiği dosyalardan
otomatik olarak derler.

Önce arayüzü başlatın, ekran görüntülerini alın, sonra raporu derleyin:

```powershell
.\.venv\Scripts\python.exe app.py
```

```powershell
.\.venv\Scripts\python.exe -m reporting.ekran_goruntuleri
```

```powershell
.\.venv\Scripts\python.exe -m reporting.sonuc_raporu
```

Çıktı: `data/rapor/Proje_Sonuc_Raporu.docx`
Şekiller: `data/rapor/sekiller/` · ekran görüntüleri: `data/rapor/ekran_goruntuleri/`

Ekran görüntüsü eksikse ilgili şekil atlanır ve rapor yine de üretilir.

---

## Temel ilke: metinde elle yazılmış sonuç değeri yoktur

Rapordaki her sayı şu dosyalardan okunur:

| Kaynak | Beslediği bölüm |
|---|---|
| `data/surrogate/surrogate_report.json` | 4.2 duyarlılık, 4.4 vekil model |
| `data/iso50001/iso50001_report.json` | 4.3 SEU ve göstergeler |
| `data/optimization/pareto_front.json` | 4.5 Pareto cephesi, Ek A |
| `data/validation/validation_report.json` | 4.6 doğrulama |
| `engine/parameters.py` | Tablo 3.1 tasarım uzayı |

Analiz yeniden koşulduğunda bu üreteç de yeniden koşulmalıdır. Aksi hâlde rapor
ile veri birbirinden ayrışır.

Bölüm 4.1'deki onarım öncesi/sonrası tablosu bir istisnadır: onarım öncesi
değerler artık üretilmeyen bir koşuya aittir ve `docs/bulgular_faz1.md`
belgesinden alınmıştır.

---

## Modüller

| Dosya | Sorumluluk |
|---|---|
| `docx_kit.py` | Biçim kuralları: sayfa düzeni, başlık stilleri, tablo/şekil başlıkları, alan kodları |
| `figures.py` | Şekil 3.1 mimari şeması ve Şekil 4.1–4.4 grafiklerinin çizimi |
| `ekran_goruntuleri.py` | Arayüz ekranlarının Playwright ile yakalanması |
| `rapor_arayuz.py` | 3.10 yazılım aracı ve 4.7 arayüzde sunum bölümleri |
| `rapor_metni.py` | 1. Giriş, 2. Literatür özeti, 3. Gereç ve yöntem |
| `rapor_bulgular.py` | 4. Bulgular, 5. Tartışma, 6. Sonuç ve Öneriler, Kaynaklar |
| `rapor_ekler.py` | Ekler A–C |
| `sonuc_raporu.py` | Kapak, ön kısımlar, Özet/Abstract ve derleme |

---

## Uygulanan biçim kuralları

Kaynak: `psr_kurallari.doc` (TÜBİTAK ARDEB).

- Arial 11 punto, 1,5 satır aralığı, tek kolon
- Üst boşluk 3 cm; sağ, sol ve alt boşluk 2,5 cm
- Ana başlık ortalı, BÜYÜK HARF, koyu; alt başlık sola dayalı ve koyu
- Tablo başlığı tablonun üstünde, şekil başlığı şeklin altında; sola dayalı,
  10 punto, 1 satır aralığı
- Kapakta sayfa numarası yok; ön kısımlar romen rakamı, ana metin 1'den başlar
- Özet ve Abstract 100–300 sözcük, sonlarında anahtar kelimeler
- Kaynaklar soyadı-yıl sistemine göre alfabetik

Bunlar `tests/test_reporting.py` içinde sınanır; kural ihlali testi düşürür.

**Türkçe büyük harf.** Python'un `str.upper()` metodu noktalı i harfini `I`
yapar; doğrusu `İ`'dir. Düzeltilmezse başlıklar "GIRIS" ve "ICINDEKILER" olarak
çıkar. `docx_kit.turkish_upper()` bunu ele alır.

---

## Word'de açtıktan sonra yapılması gerekenler

1. **Alanları güncelleyin.** İçindekiler, Tablo Listesi ve Şekil Listesi birer
   Word alanıdır; sayfa numaraları ancak güncellendiğinde dolar.
   Ctrl+A ile tümünü seçip **F9** tuşuna basın.
2. **Kapak bilgilerini doldurun.** Aşağıdaki yer tutucular üreteçte tanımlıdır
   (`sonuc_raporu.py` içindeki `KUNYE` sözlüğü):
   `[PROGRAM KODU]`, `[PROJE NO]`, `[PROJE YÜRÜTÜCÜSÜ]`, `[ARAŞTIRMACI]`,
   `[DANIŞMAN]`, `[BURSİYER]`, `[AY YIL]`, `[ŞEHİR]`.
   Sözlüğü doldurup üreteci yeniden çalıştırmak, elle düzenlemeye tercih
   edilmelidir.
3. **TÜBİTAK logosunu yerleştirin.** Şablon ekindeki logo kapak sayfasına
   eklenmelidir; üreteç yerine bir yer tutucu satır koyar.
4. **Kaynakçayı doğrulayın.** Künye bilgileri (cilt, sayı, sayfa aralığı)
   gönderim öncesi asıl yayınlardan teyit edilmelidir.

---

## Fikri Ürün Bildirim Formu

Sonuç raporuyla birlikte gönderilmesi zorunludur ve bu üretecin kapsamı
dışındadır. ARDEB-PTS üzerinden ayrıca doldurulur.
