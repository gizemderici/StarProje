# Set EPS Thickness

Bu OpenStudio ModelMeasure, `duvr_std_eps` konstrüksiyonundaki adı `eps` içeren
katmanı istenen kalınlık ve malzeme özellikleriyle değiştirir.

Konstrüksiyon yerinde güncellendiği için hem yüzeylere doğrudan atamalar hem de
varsayılan konstrüksiyon setleri aynı handle üzerinden yeni katmanı kullanır. Bu,
eski Python betiğindeki “alternatifi üretip yüzeylere atamama” hatasını giderir.
