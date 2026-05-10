# EPIC 6 — Simülasyon Sonuçlarını Okuma

## Amaç
Kullanıcının görmek istediği gerçek sonuçları üretmek için OpenStudio / EnergyPlus simülasyon çıktılarından net bir metrik seti çıkarmak.

## Backlog 6.1 — Sonuç Parser Planı
### Hedef
Simülasyon sonuçlarının okunması için ilk sürümde kullanılacak metrikleri netleştirmek ve projenin ileride bu metrikleri üretecek bir parser altyapısı kurmasını sağlamak.

## İlk sürüm metrikleri
Aşağıdaki metrikler, ilk parser sürümünde desteklenmesi planlanan öncelikli veri setidir.

1. annual heating
   - Yıllık ısıtma enerjisi.
   - Birim: kWh veya proje standardına göre MWh.

2. annual cooling
   - Yıllık soğutma enerjisi.
   - Birim: kWh veya MWh.

3. total energy
   - Tüm enerji tüketimi.
   - Isıtma + soğutma + diğer operasyonel enerji tüketimleri dahil.

4. EUI
   - Energy Use Intensity.
   - Birim: kWh/m²/y.
   - Binanın toplam enerji tüketiminin brüt döşeme alanına bölünmesi.

5. unmet hours
   - Konfor koşullarının sağlanmadığı saat sayısı.
   - Eğer imkân varsa hem bina hem zone bazlı olarak raporlanmalı.

6. peak heating
   - Maksimum ısıtma gücü yükü.
   - Birim: kW.

7. peak cooling
   - Maksimum soğutma gücü yükü.
   - Birim: kW.

8. zone temperatures
   - Zone sıcaklık verileri.
   - En azından zone bazlı ortalama, maksimum ve minimum sıcaklık değerleri izlenmeli.
   - Gelecekte saatlik veya günlük zone sıcaklık eğrileri eklenebilir.

9. aylık heating/cooling
   - Her ay için ısıtma ve soğutma enerji tüketimleri.
   - 12 aylık zaman serisi halinde raporlanmalı.

10. annual cost
   - Eğer simülasyon çıktısında maliyet verisi varsa yıllık maliyetler.
   - Birim ve para birimi açıkça belirtilmeli.

## Veri kaynağı ve çıktı biçimi
Parser, öncelikli olarak OpenStudio/EnergyPlus sonrası üretilen CSV veya JSON çıktılarından veri okuyacak.

- Girdi: Simülasyon çıktı dosyaları (CSV, JSON, EP-CSV, vb.)
- Çıktı: Tanımlı metriklerin bulunduğu tek bir JSON raporu veya yapılandırılmış CSV çıktısı.

## Öncelik
İlk sürümde aşağıdaki öncelik sırasına göre ilerlenmelidir:

1. annual heating
2. annual cooling
3. total energy
4. EUI
5. unmet hours
6. peak heating
7. peak cooling
8. aylık heating/cooling
9. zone temperatures
10. annual cost

## Kabul kriteri
- Metrik listesi netleşmiş olmalı.
- Her metrik için neyin ölçüleceği ve hangi birimde raporlanacağı tanımlanmış olmalı.
- Parser altyapısı için önceden planlanmış bir veri modeli ve çıktı formatı önerisi olmalı.

## Notlar
- `annual cost` sadece maliyet verisi mevcutsa çıkacak; maliyet verisi yoksa bu alan atlanabilir.
- Zone sıcaklıkları, halen desteklenen diğer metrikler tamamlandıktan sonra detaylandırılabilir.
- Bu plan, simülasyon sonuçları okuma modülü için temel bir yol haritası sağlar ve sonraki adımlarda daha fazla metriğin eklenmesini kolaylaştırır.
