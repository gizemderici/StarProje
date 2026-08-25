# Mimari

```text
NiceGUI :8090
  │ model yükleme baytları + model kimliği + JSON
  ▼
HTTP API :8091 (FastAPI)
  ▼
OpenStudioService
  ├── OpenStudio 3.11 gömülü Python SDK → model inceleme
  ├── OpenStudio SDK → EPS değişikliği + EnergyPlus girdisi
  └── EnergyPlus 25.2 → yıllık simülasyon + SQL
  ▼
ModelRepository
  ├── data/model_store/models.json → izinli OSM/EPW kayıtları
  └── data/model_store/imported/{model_id} → API ile yüklenen modeller
```

| Katman | Dosyalar | Sorumluluk |
|---|---|---|
| Sunum | `app.py`, `client/energy_api.py` | HTTP API'den JSON alır; OSM yolu bilmez ve OSM açmaz. |
| HTTP API | `api_server.py`, `api_layer/` | Sürümlü `/api/v1` uç noktaları ve istek doğrulaması. |
| Servis | `services/openstudio_service.py` | OpenStudio SDK adaptörü, OSW hazırlama ve EnergyPlus simülasyon yönetimi. |
| OpenStudio adaptörü | `integrations/OpenStudio/model_api_worker.py` | OSM'yi resmi `VersionTranslator` API'siyle açıp JSON izdüşümü üretir. |
| Simülasyon | `engine/openstudio_runner.py` | Senaryoyu OSW adımlarına çevirir, OpenStudio CLI ile paralel çalıştırır. |
| Parametre kaydı | `engine/parameters.py` | Karar değişkenlerinin tek doğruluk kaynağı; OSW adımları, doğrulama ve tasarım uzayı buradan üretilir. |
| Model onarımı | `integrations/OpenStudio/model_repair_worker.py` | Faz 1 kusurlarını resmi SDK ile giderip onarılmış modeli yazar. |
| Model deposu | `model_store/`, `data/model_store/models.json` | Dışarıya dosya yolu vermeden model kimliğini izinli dosyaya çözer. |
| Analiz | `engine/` | SQL sonuçları, hızlı tahmin ve OSW/CLI yardımcıları. |

## Veri akışı

1. NiceGUI, `main-building` gibi bir model kimliğiyle HTTP API'ye bağlanır.
   Yeni model eklenirken dosya yolu değil, `.osm` ve isteğe bağlı `.epw` içeriği
   multipart HTTP isteğiyle API'ye gönderilir.
2. API, kimliği `ModelRepository` üzerinden izinli OSM/EPW kaydına çözer.
3. `OpenStudioService`, kurulu OpenStudio CLI'nin gömülü Python SDK'sını çağırır;
   OSM yalnızca bu süreçte resmi OpenStudio API'siyle açılır.
4. SDK çıktısı JSON olarak API'ye, oradan NiceGUI istemcisine döner. Yerel model
   yolları HTTP yanıtlarında yayımlanmaz.
5. API servisindeki `ResultsRepository`, EnergyPlus SQLite tablolarını tek veri
   modeline çevirir ve yalnızca JSON döndürür. NiceGUI SQL dosyasını açmaz.
6. API servisindeki hızlı model 5 cm koşusunu referans alır ve yalnızca duvar iletimine duyarlı
   enerji paylarını U-değeri oranına göre değiştirir.
7. Gerçek koşu isteği NiceGUI'den HTTP API'ye gider; servis resmi OpenStudio SDK
   ile hedef konstrüksiyonun EPS katmanını yerinde değiştirir ve EnergyPlus
   girdisini üretir. Kurulu EnergyPlus yıllık koşuyu ve SQL çıktısını oluşturur.
   Ayrı `/workflows` uç noktası, taşınabilir OSW + Ruby measure akışını da hazırlar.
8. API servisindeki `StarStudy`, ikinci modeldeki 20 gerçek koşuyu okur, 6 tekrar koşusunu işaretler
   ve iki temsilî sonucu ham EnergyPlus SQL verisiyle doğrular.

## HTTP uç noktaları

- `GET /api/v1/health`
- `GET /api/v1/models`
- `POST /api/v1/models` — `.osm` + isteğe bağlı `.epw` yükleme ve doğrulama
- `GET /api/v1/models/{model_id}`
- `GET /api/v1/models/{model_id}/constructions`
- `GET /api/v1/models/{model_id}/archived-results`
- `GET /api/v1/models/{model_id}/study-results`
- `POST /api/v1/models/{model_id}/quick-study`
- `POST /api/v1/models/{model_id}/workflows`
- `POST /api/v1/models/{model_id}/simulations`
- `GET /api/v1/models/{model_id}/simulations`

Swagger arayüzü `http://127.0.0.1:8091/docs` adresindedir.
