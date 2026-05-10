# EPIC 13.1 Overlay Grafik Kullanilacak Metrikler

Bu dosya, EPIC 13 kapsaminda hangi metriklerin overlay line chart ile gosterilecegini ve nedenlerini netlestirir.

## Overlay Line Chart Icin Uygun Olanlar
- Monthly heating: Zaman serisi oldugu icin degisiklik oncesi-sonrasi trend iki cizgi ile net gorunur.
- Monthly cooling: Aylik sogutma profili mevsimsel etkileri cizgi karsilastirmasiyla aciklar.
- Zone temperature: Zone bazli zamansal sicakliklar konfor farkini line overlay ile dogrudan gosterir.
- Selected zone operative temperature: Secili zone icin surekli sicaklik davranisi line chart icin dogal bir seridir.
- Surface temperature: Yuzey sicakligi saatlik/gunluk degistiginden line overlay ile anlamlidir.
- Hourly profile (temperature): Saatlik seri oldugu icin iki cizgi ile pik ve sapma kolay izlenir.
- Daily profile (temperature): Gunluk zaman sirali veri line ile okunabilir trend verir.
- Unmet hours trend (eger periyot bazli uretiliyorsa): Trend varsa overlay uygundur.
- Total energy trend (eger periyot bazli uretiliyorsa): Trend varsa overlay uygundur.

## Overlay Icin Uygun Olmayanlar
- Annual heating: Tek sayilik KPI, zaman serisi degil.
- Annual cooling: Tek sayilik KPI, zaman serisi degil.
- Total annual cost: Tek sayilik finansal ozet, KPI/bar daha uygundur.
- Sadece ozet KPI degerleri: Trend ekseni olmadigi icin line overlay anlamli degil.

## Grafik Tipi Secim Gerekcesi
- Overlay line chart secimi: Sirali zaman noktalarinda iki senaryo farkini trend ve pik davranisiyla birlikte okumak icin.
- Bar/KPI secimi: Tekil ozet degerlerde hizli karsilastirma ve net mesaj vermek icin.
