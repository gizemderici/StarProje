# Projeyi Adim Adim Anlatim

Bu dokuman, projeyi hic bilmeyen biri icin yazildi.
Buradaki amac sadece "bu kod ne yapiyor?" demek degil.
Asil amac su:

- Proje neden var?
- Kullanici ekranda ne yapiyor?
- Sistemin arka tarafta neleri calisiyor?
- Hangi butona basinca ne oluyor?
- Hangi dosya ne is yapiyor?
- Grafikler neden bazen doluyor, bazen bos kaliyor?

Bu metni okuyan birinin Python, NiceGUI, OpenStudio veya enerji simulasyonu bilmesine gerek yok.
Olabildigince sade, adim adim ve mantikli bir sira ile anlatilacak.

---

## Icindekiler

1. Bu proje ne icin var?
2. Bu proje hangi verilerle calisiyor?
3. Projenin genel mantigi nedir?
4. Beklenen etki ve gercek sonuc arasindaki fark nedir?
5. Kullanici uygulamada ne gorur?
6. Parametre secim sayfasi nasil calisir?
7. Degisim ozet karti ne yapar?
8. Senaryo taslagi nedir?
9. Senaryo ozeti bolumunde ne olur?
10. Run hazirlik ve gercek calistirma arasindaki fark nedir?
11. Analiz sayfasi nasil calisir?
12. Analiz sayfasindaki grafikler tek tek ne ise yariyor?
13. Grafik kartlarindaki yeni davranislar ne?
14. Proje hangi dosyalardan olusuyor?
15. Hangi klasor ne ise yariyor?
16. Kullanici bir ornek senaryoda ne yapar?
17. Grafikler neden bazen bos kaliyor?
18. Son donemde hangi iyilestirmeler yapildi?
19. Projeyi bir baskasina tek cumlede nasil anlatirsin?
20. Bu proje neden degerli?
21. Son soz
22. Ekran ekran rehber
23. Hangi durumda kullanici ne yapmali?
24. Bu dokumani nasil kullanmalisin?

---

## 1. Bu proje ne icin var?

Bu proje, bir bina modeline ait teknik verileri okuyup, bu veriler uzerinde degisiklik yapip, bu degisikliklerin etkisini gostermek icin yapildi.

En basit haliyle su isi yapiyor:

1. Elimizde bir binaya ait veriler var.
2. Bu veriler CSV dosyalarina aktarilmis durumda.
3. Kullanici bu CSV verilerindeki belirli alanlari degistirmek istiyor.
4. Sistem bu degisikligi senaryo haline getiriyor.
5. Sonra bu degisikligin etkisini grafiklerle, ozetlerle ve karsilastirma panelleriyle gosteriyor.

Yani bu proje sadece "CSV acma" araci degil.
Bu proje bir "parametrik degisiklik ve etki analizi" araci.

Bir bakima kullaniciya su soruyu cevapliyor:

"Ben bu binadaki su ozelligi degistirirsem ne olur?"

Ornek:

- Yalitimi kalinlastirirsam ne olur?
- Malzemenin iletkenligini dusurursem ne olur?
- Pencerenin U degerini degistirirsem ne olur?
- Cati yapisini degistirirsem ne olur?

Bu sorularin cevabi bu projede adim adim uretiliyor.

---

## 2. Bu proje hangi verilerle calisiyor?

Proje bir bina modelinden gelen verilerle calisir.
Bu veriler genelde su kaynaklardan gelir:

- `.osm` model dosyasi
- bu modelden uretilmis `csv_output/` altindaki CSV dosyalari
- senaryo uygulamalarindan sonra uretilen `simulation_outputs/`
- karsilastirma raporlari

CSV tarafinda tipik olarak su veri setleri vardir:

- `materials.csv`
- `constructions.csv`
- duvar, cati, doseme, pencere ile ilgili diger tablolar

Bu CSV dosyalarinin icinde su tip alanlar olabilir:

- kalinlik
- iletkenlik
- yogunluk
- ozgul isi
- termal direnç
- pencere U-Factor
- SHGC
- katman malzemesi
- katman sirasi

Yani proje, bina fiziksel davranisini etkileyen sayisal ve metinsel alanlarla ilgileniyor.

---

## 3. Projenin genel mantigi nedir?

Projede 4 ana asama var:

1. Veriyi gormek
2. Parametre secmek ve degistirmek
3. Senaryo olusturmak
4. Sonucu analiz etmek

Bu 4 asama birlikte calisiyor.

### 3.1 Veriyi gormek

Kullanici once veriyi gormek ister.
Sistem CSV dosyalarini okuyup tablo halinde gosterebilir.

### 3.2 Parametre secmek ve degistirmek

Kullanici "hangi alani degistirmek istiyorum?" diye karar verir.

Mesela:

- `Material Thickness`
- `Material Conductivity`
- `Construction Layer Thickness`
- `Window U-Factor`
- `Window SHGC`

Sonra sistem sorar:

- Bu parametrenin hangi kaydi degisecek?
- Mevcut deger ne?
- Yeni deger ne olacak?

### 3.3 Senaryo olusturmak

Kullanici bir veya birden fazla degisikligi secince sistem bunlari bir "senaryo" haline getirir.

Senaryo su anlama gelir:

"Su dosyada, su satiri, su alanla, su yeni degerle guncelle."

### 3.4 Sonucu analiz etmek

Senaryo hazir olduktan sonra sistem iki farkli tur analiz yapabilir:

- beklenen etki analizi
- gercek comparison sonucu analizi

Bu ikisini birbirinden ayirmak cok onemlidir.

---

## 4. Beklenen etki ve gercek sonuc arasindaki fark nedir?

Bu projede en kritik konulardan biri budur.

### 4.1 Beklenen Etki

Bu kisim kural tabanlidir.
Yani sistem "bu parametre degisirse genelde hangi alan etkilenir?" diye yorum yapar.

Ornek:

- kalinlik artarsa isi gecisi zorlasabilir
- iletkenlik artarsa isi daha kolay gecebilir
- R degeri artarsa yalitim daha iyi olabilir

Bu kisim simdiden bilinen fiziksel mantiga dayanir.

Bu bir tahmindir.
Gercek simulasyon sonucu degildir.

### 4.2 Gercek Sonuc

Bu kisim comparison raporundan gelir.

Yani sistem baz ve senaryo ciktilarini gercekten uretmis ise su gibi metrikleri okuyabilir:

- annual heating
- annual cooling
- total energy
- peak heating
- peak cooling
- zone temperatures
- monthly heating/cooling
- annual cost

Bu kisim gercek old/new karsilastirmasidir.

Kisaca:

- `Beklenen Etki` = teoriye dayali yorum
- `Gercek Sonuc` = comparison raporundan gelen veri

Bu ayrim tum projeyi anlamak icin cok onemlidir.

---

## 5. Kullanici uygulamada ne gorur?

Uygulamayi actiginda kullanici tek bir buyuk sistem gorur ama bunun icinde farkli bolumler vardir.

En genel anlamda sunlar vardir:

- veri inceleme alani
- parametre secimi alani
- yeni deger girisi alani
- senaryo ozeti alani
- run hazirlik ve calistirma butonlari
- analiz ve grafik sayfasi
- maliyet analizi

Her biri farkli bir ihtiyaca cevap verir.

---

## 6. Parametre secim sayfasi nasil calisir?

Bu sayfa projenin kalbidir.
Cunku degisiklik burada baslar.

### 6.1 Parametreler nasil listelenir?

Sistem kullaniciya degistirilebilir parametreleri gosterir.
Bu parametreler kafaya gore degil, katalogdan gelir.

Bu katalogda su bilgiler olur:

- parametrenin adi
- hangi CSV veri setine ait oldugu
- hangi alan adina bagli oldugu
- birimi
- sayisal mi metinsel mi oldugu
- beklenen etkileri
- onerilen araligi

Yani kullaniciya gosterilen her parametre onceden tanimlanmistir.

### 6.2 Parametre secilince ne olur?

Kullanici mesela `Material Conductivity` secerse sistem:

1. Bu parametrenin hangi veri setinden geldigini bulur.
2. Hangi satirlarin secilebilir oldugunu hesaplar.
3. Ekranda aciklamasini gosterir.
4. Mevcut degeri bulur.
5. Yeni deger girisi icin kutu acar.

Yani secim yapildigi anda arka tarafta veri eslestirme baslar.

### 6.3 Kayit secimi ne demek?

Sadece "Material Thickness" secmek yetmez.
Hangi malzeme icin oldugunu da secmek gerekir.

Ornek:

- tugla
- siva
- beton
- EPS

Bu secim onemlidir cunku ayni parametre birden fazla satirda olabilir.

### 6.4 Yeni deger girince ne olur?

Kullanici yeni deger girdiginde sistem:

1. bunu sayiya cevirmeye calisir
2. gerekiyorsa virgul ve nokta farkini duzeltir
3. mevcut deger ile yeni degeri karsilastirir
4. degisim miktarini hesaplar
5. degisim ozetini cikarir
6. canli analiz alanini gunceller

Yani daha senaryo kaydetmeden once sistem degisikligi anlamaya baslar.

---

## 7. Degisim ozet karti ne yapar?

Her parametre kartinda su fikir vardir:

"Kullanici bir sey degistirdi ama bunun yonu ne, siddeti ne, ilk bakista nasil okunur?"

Bu nedenle sistem kucuk bir degisim ozeti sunar.

Burada sunlar olabilir:

- artis mi oldu?
- azalis mi oldu?
- degisim guclu mu?
- etki sinirli mi?
- hangi boyutlar daha cok etkilenebilir?

Bu kartin amaci grafik cizmeden once insana hizli bir okuma vermektir.

---

## 8. Senaryo taslagi nedir?

Kullanici bir veya birden fazla parametre degisikligi yaptiginda sistem bunlari "senaryo"ya donusturur.

Senaryo, sistemin uygulayabilecegi net bir degisiklik paketidir.

Tipik olarak senaryo su bilgileri tasir:

- senaryo adi
- hangi girdi dosyasi kullaniyor
- hangi operasyonlar uygulanacak
- hangi eski deger hangi yeni deger olacak
- hangi satirlar etkilenecek

Bu asama cok onemlidir cunku artik degisiklik ekranda duran bir fikir olmaktan cikar, kaydedilebilir ve uygulanabilir bir yapıya donusur.

---

## 9. Senaryo ozeti bolumunde ne olur?

Bu alanda kullanici su seyleri gorur:

- secilen parametreler
- mevcut degerler
- yeni degerler
- veri setleri
- etkilenen kayitlar
- toplam operasyon sayisi

Bu bolum aslinda bir "kontrol noktasi"dir.

Kullanici burada sunu anlamalidir:

"Ben neyi degistiriyorum ve sistem bunu nasil anlayacak?"

Eger eksik alan varsa sistem burada uyari verir.
Yani daha calistirmaya gecmeden hata yakalanmis olur.

---

## 10. Run hazirlik ve gercek calistirma arasindaki fark nedir?

Bu proje kullaniciyi en cok burada karistirabilir.
Bu nedenle bu farki cok net bilmek gerekir.

### 10.1 Sadece Hazirlik

Bu akista sistem:

- run klasoru olusturur
- baz model kopyasi alir
- senaryo snapshot dosyasi yazar
- girdileri duzenler

Ama comparison raporu uretmez.

Yani bu asama sadece "calismaya hazirlama" asamasidir.

Bu yuzden bu akistan sonra bazi grafikler dolmayabilir.

### 10.2 Gercek Karsilastirmali Calistirma

Bu akista sistem:

- baseline cikti uretir
- scenario cikti uretir
- bunlari karsilastirir
- comparison raporu yazar

Iste grafiklerin dolmasi icin gerekli olan asil asama budur.

Yani:

- `Sadece Hazirlik Yap` -> comparison yok olabilir
- `Gercek Karsilastirmali Calistirma` -> comparison olusmasi beklenir

Bu proje gelistirilirken bu karisiklik azaltilmak icin:

- buton isimleri daha netlestirildi
- aciklama satirlari eklendi
- analiz sayfasina durum rozetleri konuldu

---

## 11. Analiz sayfasi nasil calisir?

Analiz sayfasi, sistemin "olan biteni anlamli hale getirdigi" yerdir.

Bu sayfa artik daha acik bir yapida calisir.

### 11.1 Ust kontrol cubugu

Sayfanin en ustunde su bilgiler vardir:

- senaryo secimi
- analizi yenile butonu
- son guncelleme saati
- veri durumu
- durum rozeti

Bu ne ise yarar?

Kullanici once hangi senaryoyu inceleyecegini secer.
Sonra isterse tum grafikleri topluca yeniler.
Sistem de su anda ne durumda oldugunu soyler:

- `GUNCEL`
- `HAZIRLIKTA`
- `COMPARISON YOK`

### 11.2 Adim karti

Kontrol cubugunun altinda 3 adimli bir durum ozeti vardir:

1. Senaryo hazirlandi
2. Comparison uretildi
3. Grafikler guncellendi

Eksik olan adimlar kirmiziya yakin, tamam olanlar yesile yakin gorunur.

Bu sayede kullanici "neden grafik yok?" sorusunun cevabini teknik log okumadan anlayabilir.

---

## 12. Analiz sayfasindaki grafikler tek tek ne ise yariyor?

Bu kisim cok onemli.
Cunku ekranda bircok grafik var ve ilk bakista karisik gelebilir.

### 12.1 Degisen Alan / Islem Sayisi

Bu grafik senaryolarda kac alan degistigini gosterir.

Bu daha cok "senaryo buyuklugu" gibi dusunulebilir.

### 12.2 Beklenen Etki / Parametre Ozeti

Bu kisim gercek simulasyon sonucu degildir.

Bu bolum su soruya cevap verir:

"Secilen parametreler teorik olarak en cok nereyi etkiler?"

Burada kullanilan mantik parameter catalog ve expected impact kurallarindan gelir.

### 12.3 Enerji Performansi

Bu grafik genelde su 3 metrik icin baz ve yeni durumu karsilastirir:

- Annual Heating
- Annual Cooling
- Total Energy

Bu grafik doluysa comparison raporu var demektir.
Bos ise genelde sunlardan biri vardir:

- comparison raporu yok
- metrik dosyada var ama degeri null
- senaryo sadece hazirlikta kalmis

### 12.4 Run-to-Run Trend

Bu grafik birden fazla comparison raporu uzerinden trend cikarir.

Yani tek bir senaryo degil, zamanla veya run sayisiyla beraber degisim gorulur.

Ornek:

- total energy her yeni run ile azaliyor mu?
- annual cost kotulesiyor mu?

### 12.5 Gercek Simulasyon Sonucu

Bu bolum old/new karsilastirmasini daha genis metriklerle verir.

Tipik olarak su metrikler gorulebilir:

- Annual Heating
- Annual Cooling
- Total Energy
- Peak Heating
- Peak Cooling
- Hot Hours
- Temp Stability Std
- Annual Cost

Bu grafik bazen normalize edilir.
Cunku tum metriklerin birimi ayni olmayabilir.

Ama tooltip gercek degerleri gostermeye devam eder.

### 12.6 Delta Ozeti

Bu grafik `Yeni - Eski` farkini dogrudan gosterir.

Genel mantik:

- pozitif fark -> kirmizi
- negatif fark -> yesil
- veri yok -> gri

Bu, kullanicinin farki hizli okumasini saglar.

### 12.7 Aylik Enerji Overlay

Bu iki panelden olusur:

- Monthly Heating
- Monthly Cooling

Burada baz ve secili overlay senaryolari ay ay karsilastirilir.

Bu grafik su sorulara cevap verir:

- fark en cok hangi ayda aciliyor?
- kis etkisi mi daha buyuk?
- yaz etkisi mi daha buyuk?

### 12.8 Zone Sicaklik Overlay

Bu grafik secilen zone icin zaman serisi karsilastirmasi yapar.

Yani:

- baz durumda zone nasil davraniyor?
- yeni senaryoda nasil davraniyor?

Eger tam zaman serisi yoksa sistem bazen fallback ile "son bilinen nokta" gosterebilir.
Bu da artik ekranda acikca belirtilir.

### 12.9 Zone Heatmap

Bu grafik zone bazinda daha toplu bir gorunum verir.

Yani tek tek cizgi yerine genel durum gosterir.

Burada kullanilan heatmap modlari olabilir:

- sicaklik vs konfor
- asiri sicak vs asiri soguk
- stabilite vs tepe sicaklik

### 12.10 Advanced Analysis

Bu bolum daha metinsel ve ozetleyici bir analizdir.

Burada sunlar bir araya gelir:

- zone bazli analiz
- peak load analizi
- konfor analizi
- sezon bazli analiz

Bu bolum grafiklerden cikan sonuclari tek bir insan okuyusuna cevirir.

---

## 13. Grafik kartlarindaki yeni davranislar ne?

Proje gelistirilirken analiz sayfasinda su iyilestirmeler yapildi:

### 13.1 Her kartta veri kaynagi yaziyor

Artik kart ustunde sunu gorebilirsin:

- `Veri Kaynagi: comparison report`
- `Veri Kaynagi: zone_temperatures`
- `Veri Kaynagi: monthly_heating_cooling`

Bu cok onemli cunku kullanici grafik bossa hangi veri katmanina bakacagini anlar.

### 13.2 Her kartta durum rozeti var

Her kartta kucuk badge vardir:

- `GUNCEL`
- `HAZIRLIKTA`
- `VERI EKSIK`
- `GEREKLI`

Bu rozetler kartin o anki saglik durumunu gosterir.

### 13.3 Her kartta Yenile butonu var

Kullanici artik tum sayfayi degil, tek bir karti yenileyebilir.

### 13.4 Her kartta Neden Bos? butonu var

Bu buton, teknik hata yerine yonlendirici metin vermek icin dusunuldu.

Mesela sunu diyebilir:

- Bu grafik icin comparison raporu gerekli.
- Bu grafik icin overlay listesinde en az bir senaryo sec.
- Bu grafik icin zone_temperatures metric'i dolu olmali.

Yani sadece hata degil, cozum de gosterilir.

---

## 14. Proje hangi dosyalardan olusuyor?

Bu kisim projeyi gelistiren biri icin cok onemlidir.

### 14.1 `nicegui_csv_viewer.py`

Bu dosya ana uygulamadir.
Kullanicinin gordugu ekranlarin buyuk bolumu burada baglanir.

Bu dosya:

- sayfalari olusturur
- butonlari baglar
- secimleri takip eder
- analiz grafiklerini gunceller
- UI davranislarini yonetir

Kisaca burasi ana orkestra sefi gibidir.

### 14.2 `parameter_catalog.py`

Bu dosya degistirilebilir parametrelerin katalogudur.

Burada her parametre icin sunlar tanimlidir:

- ad
- alan
- veri seti
- birim
- aciklama
- beklenen etkiler

### 14.3 `parameter_explanations.py`

Bu dosya kullaniciya gosterilen parametre aciklamalarini uretir.

Yani sistem "Material Thickness nedir?" gibi sorulara burada cevap hazirlar.

### 14.4 `scenario_builder.py`

Bu dosya secilen degisikliklerden senaryo taslagi uretir.

### 14.5 `apply_scenario_definition.py`

Bu dosya senaryo tanimini CSV uzerine uygular.

### 14.6 `scenario_model_preparation.py`

Bu dosya run klasoru, model kopyasi ve senaryo snapshot'ini hazirlar.

### 14.7 `simulation_runner.py`

Bu dosya gercek baseline + senaryo + comparison akisini calistirir.

### 14.8 `simulation_results_parser.py`

Bu dosya simulasyon sonuclarini okunur hale getirir.

### 14.9 `overlay_chart_model.py`

Bu dosya grafiklerin ortak overlay mantigini duzenler.

Yani:

- base cizgisi
- updated cizgisi
- stiller
- tooltip mantigi

gibi ortak yapilar burada standardize edilir.

### 14.10 `view_models/comparison_reports.py`

Bu dosya comparison raporlarini okur ve ozetler.

Burada sistem sunlari bulur:

- hangi metric var
- hangi metric eksik
- hangisinin degeri null
- hangi senaryolarda sadece hazirlik yapilmis

### 14.11 `view_models/parameter_effects.py`

Bu dosya beklenen etki mantigini tasir.

Yani kullanicinin yaptigi degisikligi heating, cooling, cost, comfort gibi ust boyutlara cevirir.

### 14.12 `ui_sections/analytics.py`

Bu dosya analiz sayfasinin UI parcalarini toplar.

Kontrol cubugu, kartlar, durum panelleri ve yorum alanlari gibi seyler burada kurulur.

### 14.13 `actions/scenario_runner.py`

Bu dosya senaryo hazirlik akislari gibi daha operasyonel isleri ayirir.

---

## 15. Hangi klasor ne ise yariyor?

### `csv_output/`

Ham veya uretilmis CSV verileri burada bulunur.

### `scenario_definitions/`

Kaydedilen senaryo tanimlari burada tutulur.

### `scenario_runs/`

Her senaryonun run klasoru burada olusur.

Ornegin:

- baz model kopyasi
- senaryo model kopyasi
- metadata
- comparison raporu

### `simulation_outputs/`

Senaryo uygulamalarindan sonra uretilen ciktolar burada olabilir.

### `docs/`

Proje hakkindaki yardim, plan, aciklama ve rehber dosyalari burada tutulur.

### `tests/`

Test dosyalari burada bulunur.

---

## 16. Kullanici bir ornek senaryoda ne yapar?

Burayi cok somut anlatalim.

### Ornek

Kullanici su degisikligi yapmak istiyor:

- `Material Thickness`
- kayit: `tugla`
- mevcut: `0.19`
- yeni: `0.25`

### Adim adim sistemde olanlar

1. Kullanici parametreyi secer.
2. Sistem uygun kayitlari listeler.
3. Kullanici `tugla` kaydini secer.
4. Sistem `0.19` mevcut degerini bulur.
5. Kullanici `0.25` yazar.
6. Sistem farki hesaplar.
7. Degisim ozetini gunceller.
8. Senaryo taslagina bir operasyon ekler.
9. Kullanici isterse bunu kaydeder.
10. Kullanici isterse gercek karsilastirmali calistirma yapar.
11. Comparison raporu olusursa analiz sayfasindaki enerji ve diger grafikler dolar.

Eger kullanici ayni anda `Material Conductivity` de degistirirse:

1. ikinci operasyon da taslaga eklenir
2. toplam operasyon sayisi artar
3. beklenen etki ozeti daha zengin hale gelir
4. comparison sonucu artik iki degisikligin birlesik etkisini tasir

---

## 17. Grafikler neden bazen bos kaliyor?

Bu projede bu cok sorulan bir sorudur.

En yaygin sebepler sunlardir:

### 17.1 Comparison raporu yok

Bu durumda gercek sonuc grafiklerinin dolmasi beklenmez.

### 17.2 Senaryo sadece hazirlikta kalmis

Yani run klasoru vardir ama comparison uretilmemistir.

### 17.3 Metric dosyada var ama degeri null

Ornegin:

- `annual_heating` var
- ama `base_value` ve `scenario_value` bos

Bu durumda grafik teknik olarak raporu bulsa bile yine bos kalabilir.

### 17.4 Overlay secimi yapilmamis

Aylik ve zone grafiklerinde secim gerekli olabilir.

### 17.5 Zone verisi yok

Zone temperature veya heatmap icin `zone_temperatures` metrikleri gerekebilir.

Bu nedenle analiz sayfasi artik su sorulara acik cevap veriyor:

- comparison var mi?
- veri eksik mi?
- sadece hazirlikta mi kaldi?
- kullanici ne yapmali?

---

## 18. Bu projede son donemde hangi iyilestirmeler yapildi?

Bu proje zamanla daha kullanisli hale getirildi.
Ozellikle su alanlarda buyuk iyilestirmeler yapildi:

### 18.1 Virgul ile sayi girisi

Kullanici artik `8,5` gibi degerleri daha rahat girebiliyor.

### 18.2 Parametre kartlarindaki karisik mini grafiklerin kaldirilmasi

Anlasilmayan grafikler kaldirildi, yerine daha anlasilir ozetler geldi.

### 18.3 Degisim ozeti kartlari

Artis, azalis, guclu etki gibi bilgiler rozet ve ikonlarla gosterildi.

### 18.4 Analiz sayfasinda ust kontrol cubugu

Artik analiz sayfasinda neyin secili oldugu ve durumun ne oldugu daha net.

### 18.5 Grafik kartlarina veri kaynagi, yenile ve neden bos butonlari

Bu, kullanicinin grafikleri daha kolay anlamasini sagladi.

### 18.6 Gercek sonuc delta grafigi

Sadece old/new degil, `yeni - eski` farki da grafikle gosterildi.

### 18.7 Bos grafiklerin neden bos oldugunu gosteren paneller

Bu sayede kullanici log dosyasi okumadan neden bos oldugunu gorebiliyor.

### 18.8 Durum rozetleri

Hem ust kontrol cubugunda hem kartlarda:

- guncel
- hazirlikta
- veri eksik
- gerekli

gibi durumlar renkli rozetle veriliyor.

---

## 19. Projeyi bir baskasina tek cumlede nasil anlatirsin?

Kisa anlatim:

"Bu proje, bina modelindeki parametreleri secip degistirdigimizde, bu degisiklikleri senaryo haline getiren ve etkilerini hem kural tabanli hem de comparison raporlarina dayali grafiklerle gosteren NiceGUI tabanli bir analiz sistemidir."

Daha sade anlatim:

"Bu proje, binadaki bir ozelligi degistirince ne olabilecegini gormemizi saglayan akilli bir arayuzdur."

---

## 20. Bu proje neden degerli?

Cunku kullanici sadece veri gormuyor.
Veriye anlam da ekleniyor.

Sistem su sorularin hepsine birlikte cevap veriyor:

- ne degisti?
- ne kadar degisti?
- hangi kayitta degisti?
- bu teorik olarak neyi etkiler?
- gercek sonucta ne oldu?
- grafik neden bos?
- devam etmek icin ne yapmaliyim?

Bu yuzden proje sadece teknik degil, ayni zamanda ogretici ve karar destekleyici bir sistem haline geliyor.

---

## 21. Son soz

Bu projeyi anlamanin en iyi yolu su sirayi akilda tutmaktir:

1. Veri var
2. Parametre seciliyor
3. Yeni deger giriliyor
4. Senaryo taslagi olusuyor
5. Hazirlik yapiliyor veya gercek comparison calistiriliyor
6. Sonuc analiz sayfasinda okunuyor

Eger biri bu akisi anladiysa, projenin buyuk resmini anlamis olur.

Kisacasi bu sistem, "bir degisikligin bina performansina etkisini" hem teknik hem gorsel hem de operasyonel olarak anlatan bir platformdur.

---

## 22. Ekran Ekran Rehber

Bu bolumde uygulamayi acan bir kullanicinin ekranda ne gordugunu daha somut sekilde anlatalim.
Buradaki mantik su:

"Ben su an hangi ekrana bakiyorum ve burada ne yapmam gerekiyor?"

### 22.1 Parametre Secim Ekrani

Bu ekran genelde kullanicinin en cok zaman gecirdigi yerdir.

Burada sunlari gorursun:

- parametre kartlari
- secili parametrelerin kayit secimleri
- mevcut deger
- yeni deger giris kutusu
- degisim ozeti

Bu ekranda yapman gereken:

1. Ilgili parametreyi bul
2. O parametrenin hangi kaydini degistirecegini sec
3. Yeni degeri gir
4. Karttaki ozetleri kontrol et

Bu ekranin amaci:

- degisiklik yapmaya baslamak
- kullaniciya parametreyi tanitmak
- degisiklik daha senaryo olmadan once mantikli mi diye kontrol etmek

### 22.2 Senaryo Ozeti Ekrani

Bu kisim bazen ayni sayfanin altinda, bazen ayri mantikta gorulebilir.

Burada tipik olarak sunlari gorursun:

- secilen parametreler tablosu
- operasyon sayisi
- etkilenen veri seti
- taslak hazir mi degil mi bilgisi

Bu bolumde su soruya cevap aranir:

"Benim yaptigim degisiklikler sistem tarafinda dogru anlasildi mi?"

Eger burada bir uyusmazlik varsa, daha calistirmaya gecmeden duzeltilmelidir.

### 22.3 Run Hazirlik Bolumu

Bu kisim kullanici icin kritik ama ilk bakista karisik olabilir.

Burada iki farkli mantik vardir:

- sadece hazirlik
- gercek karsilastirmali calistirma

Bu ekranda yapman gereken:

1. baz model yolunu dogru girmek
2. senaryo taslaginin hazir oldugunu kontrol etmek
3. sadece klasor ve model kopyasi mi istiyorsun, yoksa comparison raporu da mi istiyorsun karar vermek

### 22.4 Analiz Sayfasi

Bu ekranin yeni hali daha acik okunacak sekilde duzenlendi.

Sayfanin en ustunde:

- `Senaryo Secimi`
- `Analizi Yenile`
- `Son Guncelleme`
- `Durum`
- renkli durum rozeti

vardir.

Bu sayfada once sunu yapmalisin:

1. Hangi senaryoyu analiz edecegini sec
2. Gerekirse `Analizi Yenile`
3. Ustteki durum kartina bak

Eger burada:

- `GUNCEL` goruyorsan
  grafiklerin dolu olma ihtimali yuksektir

- `HAZIRLIKTA` goruyorsan
  senaryo olusmus ama comparison cikmamis olabilir

- `COMPARISON YOK` goruyorsan
  gercek sonuc grafiklerinin bos kalmasi normaldir

### 22.5 Grafik Kartlari

Her grafik kartinda artik sunlar vardir:

- baslik
- ikon
- veri kaynagi
- durum rozeti
- `Yenile`
- `Neden Bos?`

Bu cok onemlidir cunku kullanici artik her kartin neye dayandigini hemen gorur.

Ornek:

- enerji karti `comparison report` kaynaklidir
- zone overlay `zone_temperatures` metric'ine dayanir
- aylik overlay `monthly_heating_cooling` metric'ine dayanir

### 22.6 Maliyet Analizi Ekrani

Bu bolum kullanicinin ekonomik yorumu gorebilmesi icin vardir.

Burada:

- secili senaryo
- baz maliyet
- yeni maliyet
- delta
- yuzde fark

gosterilir.

Bu ekran teknik analizin ekonomik yoruma donustugu yerdir.

---

## 23. Hangi Durumda Kullanici Ne Yapmali?

Bu kisim ozellikle cok pratiktir.
Kullanici uygulamada takildiginda buradaki mantikla hareket edebilir.

### Durum 1: Parametre sectim ama analiz yok

Sebep:

- henuz sadece parametre secilmistir
- gercek comparison akisi calistirilmamistir

Yapilacak:

- senaryo taslagini kontrol et
- gerekiyorsa `Gercek Karsilastirmali Calistirma` yap

### Durum 2: Grafik bos

Sebep:

- comparison raporu yok olabilir
- metric null olabilir
- sadece hazirlik yapilmis olabilir

Yapilacak:

- karttaki `Neden Bos?` butonuna bak
- ust durum rozetini kontrol et
- gerekiyorsa comparison run al

### Durum 3: Zone grafikleri bos

Sebep:

- `zone_temperatures` yok
- overlay secimi yapilmamis
- secili zone icin seri uretilmemis

Yapilacak:

- overlay secimini kontrol et
- comparison raporundaki zone verisini kontrol et

### Durum 4: Aylik grafikler bos

Sebep:

- `monthly_heating_cooling` metric'i yok veya bos

Yapilacak:

- comparison raporu uretilmis mi bak
- secilen senaryolarda aylik veri var mi kontrol et

### Durum 5: Maliyet bos

Sebep:

- annual cost yok
- ya da total energy uzerinden tahmin de kurulamamis

Yapilacak:

- ilgili metric'lerin comparison raporunda dolu oldugunu kontrol et

---

## 24. Bu Dokumani Nasil Kullanmalisin?

Bu dokuman iki sekilde kullanilabilir:

### 24.1 Projeyi ogrenmek icin

Eger projeye yeni basliyorsan:

1. once bolum 1-5 arasi oku
2. sonra ekran ekran rehberi oku
3. daha sonra dosya yapisini incele

### 24.2 Projeyi baskasina anlatmak icin

Eger bu projeyi bir hocaya, ekip arkadasina veya yeni gelen birine anlatacaksan:

- once bolum 1 ve 3 ile genel amaci anlat
- sonra bolum 10 ile `hazirlik` ve `gercek calistirma` farkini anlat
- sonra bolum 12 ile grafikleri anlat
- son olarak bolum 14 ile dosyalari goster

Bu sirayla anlatirsan karsi taraf projeyi daha rahat kavrar.
