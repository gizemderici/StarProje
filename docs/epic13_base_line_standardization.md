# EPIC 13.3 Base Cizgisi Standartlari

Amaç: Tum overlay grafiklerde eski durumun ayni gorunum ve anlamla sunulmasi.

## Standart Kurallar
- Base cizgisi her zaman ilk sirada yer alir.
- Label her zaman "Base Scenario" olur.
- Aciklama anlami her zaman "Before / Base / Original" olarak korunur.
- Cizgi stili sabittir: duz (solid).
- Gorsel agirlik daha belirgindir: cizgi kalinligi digerlerinden yuksek tutulur.
- Legend icinde base cizgisi ilk sirada gorunur.

## Uygulama Noktasi
- Kod: [overlay_chart_model.py](../overlay_chart_model.py)
- UI tarafinda legend/etiket guncellemeleri: [nicegui_csv_viewer.py](../nicegui_csv_viewer.py)
- Testler: [tests/test_overlay_chart_model.py](../tests/test_overlay_chart_model.py)
