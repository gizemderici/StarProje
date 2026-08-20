from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from api_layer.schemas import QuickStudyRequest, SimulationRequest
from engine.estimator import EstimatorAssumptions, run_parametric
from engine.openstudio_runner import OpenStudioCase
from engine.sql_results import ResultsRepository
from engine.star_study import StarStudy
from model_store import ModelRepository
from services import OpenStudioService, OpenStudioUnavailable


ROOT = Path(__file__).resolve().parents[1]
repository = ModelRepository(ROOT)
service = OpenStudioService(ROOT)

api = FastAPI(
    title="Enerji Simülasyon API",
    version="1.0.0",
    description="NiceGUI ile OpenStudio arasında HTTP servis katmanı.",
)

MAX_OSM_BYTES = 100 * 1024 * 1024
MAX_EPW_BYTES = 50 * 1024 * 1024


def _model(model_id: str):
    try:
        return repository.get(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _cases(payload: SimulationRequest) -> list[OpenStudioCase]:
    return [
        OpenStudioCase(
            thickness_cm=value,
            conductivity_w_mk=payload.conductivity_w_mk,
            density_kg_m3=payload.density_kg_m3,
            specific_heat_j_kgk=payload.specific_heat_j_kgk,
            target_construction=payload.target_construction,
        )
        for value in payload.thicknesses_cm
    ]


def _archived_repository(model_id: str) -> ResultsRepository:
    record = _model(model_id)
    if record.archived_results_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"{model_id} için arşivlenmiş sonuç veri kümesi bulunmuyor.",
        )
    try:
        return ResultsRepository(record.archived_results_path).load()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _uploaded_bytes(
    upload: UploadFile,
    *,
    expected_suffix: str,
    maximum_size: int,
) -> bytes:
    filename = Path(upload.filename or "").name
    if Path(filename).suffix.casefold() != expected_suffix:
        raise HTTPException(
            status_code=400,
            detail=f"Beklenen {expected_suffix} dosyası: {filename or 'adsız dosya'}",
        )
    content = await upload.read(maximum_size + 1)
    await upload.close()
    if not content:
        raise HTTPException(status_code=400, detail=f"{expected_suffix} dosyası boş.")
    if len(content) > maximum_size:
        raise HTTPException(
            status_code=413,
            detail=f"{expected_suffix} dosyası izin verilen boyutu aşıyor.",
        )
    return content


@api.get("/api/v1/health", tags=["system"])
def health() -> dict[str, object]:
    return {"status": "ok", "openstudio": service.status()}


@api.get("/api/v1/models", tags=["models"])
def list_models() -> dict[str, object]:
    return {"models": [record.public_dict() for record in repository.list()]}


@api.post("/api/v1/models", status_code=201, tags=["models"])
async def upload_model(
    name: str = Form(..., min_length=1, max_length=120),
    osm: UploadFile = File(...),
    weather: UploadFile | None = File(default=None),
) -> dict[str, object]:
    osm_bytes = await _uploaded_bytes(
        osm, expected_suffix=".osm", maximum_size=MAX_OSM_BYTES
    )
    if b"OS:Version" not in osm_bytes[:16_384]:
        raise HTTPException(status_code=400, detail="Dosya OpenStudio OSM biçiminde görünmüyor.")

    weather_bytes = None
    if weather is not None:
        weather_bytes = await _uploaded_bytes(
            weather, expected_suffix=".epw", maximum_size=MAX_EPW_BYTES
        )
        if not weather_bytes.lstrip().upper().startswith(b"LOCATION,"):
            raise HTTPException(status_code=400, detail="Dosya EnergyPlus EPW biçiminde görünmüyor.")

    try:
        record = repository.register_upload(
            name=name,
            osm_bytes=osm_bytes,
            weather_bytes=weather_bytes,
        )
        return service.inspect_model(record, refresh=True)
    except OpenStudioUnavailable as exc:
        if "record" in locals():
            repository.remove_uploaded(record.model_id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        if "record" in locals():
            repository.remove_uploaded(record.model_id)
        raise HTTPException(
            status_code=400,
            detail=f"Model OpenStudio doğrulamasından geçemedi: {exc}",
        ) from exc


@api.get("/api/v1/models/{model_id}", tags=["models"])
def get_model(
    model_id: str, refresh: bool = Query(default=False)
) -> dict[str, object]:
    try:
        return service.inspect_model(_model(model_id), refresh=refresh)
    except OpenStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@api.get("/api/v1/models/{model_id}/constructions", tags=["models"])
def list_constructions(model_id: str) -> dict[str, object]:
    model = get_model(model_id)
    return {
        "model": model["model"],
        "source": model["source"],
        "constructions": model["constructions"],
    }


@api.get("/api/v1/models/{model_id}/archived-results", tags=["results"])
def archived_results(model_id: str) -> dict[str, object]:
    payload = _archived_repository(model_id).summary()
    for scenario in payload["scenarios"].values():
        scenario.pop("sql_path", None)
    payload["model"] = _model(model_id).public_dict()
    payload["source"] = "energyplus-sql-service"
    return payload


@api.get("/api/v1/models/{model_id}/study-results", tags=["results"])
def study_results(model_id: str) -> dict[str, object]:
    record = _model(model_id)
    if record.study_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"{model_id} için parametrik çalışma veri kümesi bulunmuyor.",
        )
    try:
        study = StarStudy(record.study_path).load()
        return {
            "model": record.public_dict(),
            "source": "energyplus-study-service",
            "scenarios": [item.to_dict() for item in study.scenarios],
            "sql_validation": study.validate_sql(),
        }
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.post("/api/v1/models/{model_id}/quick-study", tags=["results"])
def quick_study(model_id: str, payload: QuickStudyRequest) -> dict[str, object]:
    archived = _archived_repository(model_id)
    baseline = archived.scenarios.get(5)
    if baseline is None:
        raise HTTPException(status_code=422, detail="5 cm referans senaryosu bulunamadı.")
    assumptions = EstimatorAssumptions(
        eps_conductivity_w_mk=payload.conductivity_w_mk
    )
    points = run_parametric(payload.thicknesses_cm, baseline, assumptions)
    return {
        "model_id": model_id,
        "source": "calibrated-quick-estimate-service",
        "assumptions": {
            key: getattr(assumptions, key)
            for key in assumptions.__dataclass_fields__
        },
        "results": [point.to_dict() for point in points],
    }


@api.post("/api/v1/models/{model_id}/workflows", tags=["simulations"])
def prepare_workflows(model_id: str, payload: SimulationRequest) -> dict[str, object]:
    try:
        runs = service.prepare_workflows(_model(model_id), _cases(payload))
    except (OpenStudioUnavailable, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"model_id": model_id, "runs": runs}


@api.post("/api/v1/models/{model_id}/simulations", tags=["simulations"])
def run_simulations(model_id: str, payload: SimulationRequest) -> dict[str, object]:
    try:
        runs = service.run_simulations(_model(model_id), _cases(payload))
    except OpenStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"model_id": model_id, "runs": runs}


@api.get("/api/v1/models/{model_id}/simulations", tags=["simulations"])
def list_simulations(model_id: str) -> dict[str, object]:
    return {
        "model_id": model_id,
        "runs": service.list_simulation_results(_model(model_id)),
    }
