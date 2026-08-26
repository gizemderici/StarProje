from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class EnergyApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ApiMaterial:
    handle: str
    name: str
    material_type: str
    thickness_m: float | None
    conductivity_w_mk: float | None
    density_kg_m3: float | None
    specific_heat_j_kgk: float | None
    thermal_resistance_m2k_w: float | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiMaterial":
        return cls(
            handle=str(payload.get("handle", "")),
            name=str(payload.get("name", "Bilinmeyen katman")),
            material_type=str(payload.get("type", "unknown")),
            thickness_m=payload.get("thickness_m"),
            conductivity_w_mk=payload.get("conductivity_w_mk"),
            density_kg_m3=payload.get("density_kg_m3"),
            specific_heat_j_kgk=payload.get("specific_heat_j_kgk"),
            thermal_resistance_m2k_w=payload.get("r_value_m2k_w"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "name": self.name,
            "type": self.material_type,
            "thickness_m": self.thickness_m,
            "thickness_cm": round(self.thickness_m * 100, 3)
            if self.thickness_m is not None
            else None,
            "conductivity_w_mk": self.conductivity_w_mk,
            "density_kg_m3": self.density_kg_m3,
            "specific_heat_j_kgk": self.specific_heat_j_kgk,
            "r_value_m2k_w": self.thermal_resistance_m2k_w,
        }


@dataclass(frozen=True, slots=True)
class ApiConstruction:
    handle: str
    name: str
    layers: list[ApiMaterial]
    surface_count: int
    resolved_surface_count: int
    r_layers_m2k_w: float
    r_total_with_films_m2k_w: float
    u_value_w_m2k: float

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiConstruction":
        return cls(
            handle=str(payload.get("handle", "")),
            name=str(payload.get("name", "")),
            layers=[ApiMaterial.from_payload(item) for item in payload.get("layers", [])],
            surface_count=int(payload.get("surface_count", 0)),
            resolved_surface_count=int(payload.get("resolved_surface_count", 0)),
            r_layers_m2k_w=float(payload.get("r_layers_m2k_w", 0.0)),
            r_total_with_films_m2k_w=float(
                payload.get("r_total_with_films_m2k_w", 0.0)
            ),
            u_value_w_m2k=float(payload.get("u_value_w_m2k", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class ApiModel:
    model_id: str
    name: str
    source: str
    openstudio_version: str
    building_name: str
    spaces: int
    thermal_zones: int
    surfaces: int
    subsurfaces: int
    zones: list[dict[str, Any]]
    constructions: list[ApiConstruction]
    materials: dict[str, ApiMaterial]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiModel":
        model = payload.get("model", {})
        materials = [ApiMaterial.from_payload(item) for item in payload.get("materials", [])]
        return cls(
            model_id=str(model.get("id", "")),
            name=str(model.get("name", "")),
            source=str(payload.get("source", "")),
            openstudio_version=str(payload.get("openstudio_version", "")),
            building_name=str(payload.get("building_name", "")),
            spaces=int(payload.get("spaces", 0)),
            thermal_zones=int(payload.get("thermal_zones", 0)),
            surfaces=int(payload.get("surfaces", 0)),
            subsurfaces=int(payload.get("subsurfaces", 0)),
            zones=list(payload.get("zones", [])),
            constructions=[
                ApiConstruction.from_payload(item)
                for item in payload.get("constructions", [])
            ],
            materials={item.handle: item for item in materials},
        )

    def find_construction(self, name: str) -> ApiConstruction | None:
        lowered = name.casefold()
        return next(
            (item for item in self.constructions if item.name.casefold() == lowered),
            None,
        )


@dataclass(frozen=True, slots=True)
class ApiIssue:
    severity: str
    message: str
    occurrences: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiIssue":
        return cls(
            severity=str(payload.get("severity", "Bilinmiyor")),
            message=str(payload.get("message", "")),
            occurrences=int(payload.get("occurrences", 1)),
        )


@dataclass(frozen=True, slots=True)
class ApiArchivedScenario:
    thickness_cm: int | None
    run_status: str
    site_energy_gj: float
    source_energy_gj: float
    eui_mj_m2: float
    total_area_m2: float
    conditioned_area_m2: float
    unmet_heating_hours: float
    unmet_cooling_hours: float
    discomfort_hours: float
    end_uses_gj: dict[str, float]
    fuels_gj: dict[str, float]
    monthly_gj: dict[str, list[float]]
    general: dict[str, str]
    window_wall_ratio: dict[str, float]
    zones: list[dict[str, Any]]
    issues: list[ApiIssue]
    warnings: int
    severe_errors: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiArchivedScenario":
        return cls(
            thickness_cm=(
                int(payload["thickness_cm"])
                if payload.get("thickness_cm") is not None
                else None
            ),
            run_status=str(payload.get("run_status", "Unknown")),
            site_energy_gj=float(payload.get("site_energy_gj", 0.0)),
            source_energy_gj=float(payload.get("source_energy_gj", 0.0)),
            eui_mj_m2=float(payload.get("eui_mj_m2", 0.0)),
            total_area_m2=float(payload.get("total_area_m2", 0.0)),
            conditioned_area_m2=float(payload.get("conditioned_area_m2", 0.0)),
            unmet_heating_hours=float(payload.get("unmet_heating_hours", 0.0)),
            unmet_cooling_hours=float(payload.get("unmet_cooling_hours", 0.0)),
            discomfort_hours=float(payload.get("discomfort_hours", 0.0)),
            end_uses_gj={str(k): float(v) for k, v in payload.get("end_uses_gj", {}).items()},
            fuels_gj={str(k): float(v) for k, v in payload.get("fuels_gj", {}).items()},
            monthly_gj={
                str(k): [float(value) for value in values]
                for k, values in payload.get("monthly_gj", {}).items()
            },
            general={str(k): str(v) for k, v in payload.get("general", {}).items()},
            window_wall_ratio={
                str(k): float(v) for k, v in payload.get("window_wall_ratio", {}).items()
            },
            zones=list(payload.get("zones", [])),
            issues=[ApiIssue.from_payload(item) for item in payload.get("issues", [])],
            warnings=int(payload.get("warnings", 0)),
            severe_errors=int(payload.get("severe_errors", 0)),
        )


@dataclass(frozen=True, slots=True)
class ApiArchivedResults:
    model: dict[str, Any]
    source: str
    archived_runs_are_identical: bool
    scenarios: dict[int, ApiArchivedScenario]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiArchivedResults":
        return cls(
            model=dict(payload.get("model", {})),
            source=str(payload.get("source", "")),
            archived_runs_are_identical=bool(payload.get("archived_runs_are_identical", False)),
            scenarios={
                int(key): ApiArchivedScenario.from_payload(value)
                for key, value in payload.get("scenarios", {}).items()
            },
        )


@dataclass(frozen=True, slots=True)
class ApiStarScenario:
    scenario: str
    thickness_cm: float | None
    conductivity_w_mk: float | None
    electricity_gj: float
    heating_gj: float
    cooling_gj: float
    exit_code: int
    duplicate: bool
    hvac_gj: float
    site_energy_gj: float
    insulation_r_m2k_w: float | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiStarScenario":
        return cls(
            scenario=str(payload.get("scenario", "")),
            thickness_cm=payload.get("thickness_cm"),
            conductivity_w_mk=payload.get("conductivity_w_mk"),
            electricity_gj=float(payload.get("electricity_gj", 0.0)),
            heating_gj=float(payload.get("heating_gj", 0.0)),
            cooling_gj=float(payload.get("cooling_gj", 0.0)),
            exit_code=int(payload.get("exit_code", 0)),
            duplicate=bool(payload.get("duplicate", False)),
            hvac_gj=float(payload.get("hvac_gj", 0.0)),
            site_energy_gj=float(payload.get("site_energy_gj", 0.0)),
            insulation_r_m2k_w=payload.get("insulation_r_m2k_w"),
        )


@dataclass(frozen=True, slots=True)
class ApiStarStudy:
    model: dict[str, Any]
    source: str
    scenarios: list[ApiStarScenario]
    sql_validation: dict[str, dict[str, float]]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiStarStudy":
        return cls(
            model=dict(payload.get("model", {})),
            source=str(payload.get("source", "")),
            scenarios=[ApiStarScenario.from_payload(item) for item in payload.get("scenarios", [])],
            sql_validation=dict(payload.get("sql_validation", {})),
        )

    @property
    def baseline(self) -> ApiStarScenario:
        return next(item for item in self.scenarios if item.thickness_cm is None)

    @property
    def unique_scenarios(self) -> list[ApiStarScenario]:
        return [item for item in self.scenarios if not item.duplicate]

    @property
    def tested_scenarios(self) -> list[ApiStarScenario]:
        return [item for item in self.unique_scenarios if item.thickness_cm is not None]

    @property
    def best_tested(self) -> ApiStarScenario:
        return min(self.tested_scenarios, key=lambda item: item.hvac_gj)

    @property
    def duplicate_count(self) -> int:
        return sum(item.duplicate for item in self.scenarios)

    @property
    def baseline_beats_all_tested(self) -> bool:
        return self.baseline.hvac_gj < self.best_tested.hvac_gj


@dataclass(frozen=True, slots=True)
class ApiEstimatePoint:
    thickness_cm: float
    conductivity_w_mk: float
    wall_r_m2k_w: float
    wall_u_w_m2k: float
    site_energy_gj: float
    eui_mj_m2: float
    heating_gj: float
    cooling_gj: float
    fan_gj: float
    pump_gj: float
    savings_gj: float
    savings_percent: float
    method: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiEstimatePoint":
        return cls(**{field: payload[field] for field in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, float | str]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class ApiQuickStudy:
    model_id: str
    source: str
    assumptions: dict[str, float]
    results: list[ApiEstimatePoint]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ApiQuickStudy":
        return cls(
            model_id=str(payload.get("model_id", "")),
            source=str(payload.get("source", "")),
            assumptions={str(k): float(v) for k, v in payload.get("assumptions", {}).items()},
            results=[ApiEstimatePoint.from_payload(item) for item in payload.get("results", [])],
        )

class EnergyApiClient:
    """Small loopback HTTP client; the NiceGUI layer never receives OSM paths."""

    def __init__(self, base_url: str, retries: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.retries = retries

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        timeout: float = 1800,
        raw_body: bytes | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        if payload is not None and raw_body is not None:
            raise ValueError("JSON ve ham istek gövdesi birlikte gönderilemez.")
        body = raw_body
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type is not None:
            headers["Content-Type"] = content_type
        request = Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        for attempt in range(self.retries):
            try:
                with urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                try:
                    detail = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    detail = str(exc)
                raise EnergyApiError(f"API {exc.code}: {detail}") from exc
            except (URLError, TimeoutError, ConnectionError) as exc:
                if attempt + 1 == self.retries:
                    raise EnergyApiError(
                        f"Enerji API'ye ulaşılamadı: {self.base_url}"
                    ) from exc
                time.sleep(0.25)
        raise EnergyApiError(f"Enerji API'ye ulaşılamadı: {self.base_url}")

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/health", timeout=10)

    def list_models(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/v1/models", timeout=30).get("models", []))

    def get_model(self, model_id: str, refresh: bool = False) -> ApiModel:
        suffix = "?refresh=true" if refresh else ""
        return ApiModel.from_payload(
            self._request("GET", f"/api/v1/models/{model_id}{suffix}", timeout=180)
        )

    def upload_model(
        self,
        *,
        name: str,
        osm_filename: str,
        osm_bytes: bytes,
        weather_filename: str | None = None,
        weather_bytes: bytes | None = None,
    ) -> ApiModel:
        boundary = f"----EnergyApi{uuid.uuid4().hex}"
        chunks: list[bytes] = []

        def field(field_name: str, value: str) -> None:
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ])

        def file_part(field_name: str, filename: str, content: bytes) -> None:
            safe_name = Path(filename).name.replace('"', "").replace("\r", "").replace("\n", "")
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{field_name}"; filename="{safe_name}"\r\n'.encode(),
                b"Content-Type: application/octet-stream\r\n\r\n",
                content,
                b"\r\n",
            ])

        field("name", name)
        file_part("osm", osm_filename, osm_bytes)
        if weather_filename is not None and weather_bytes is not None:
            file_part("weather", weather_filename, weather_bytes)
        chunks.append(f"--{boundary}--\r\n".encode())
        response = self._request(
            "POST",
            "/api/v1/models",
            timeout=180,
            raw_body=b"".join(chunks),
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        return ApiModel.from_payload(response)

    def get_archived_results(self, model_id: str) -> ApiArchivedResults:
        return ApiArchivedResults.from_payload(
            self._request("GET", f"/api/v1/models/{model_id}/archived-results", timeout=180)
        )

    def get_baseline_results(self, model_id: str) -> ApiArchivedScenario:
        """Faz 1 onarimi sonrasi taban kosusunu getirir.

        Arsiv ucu eski eps_{kalinlik}cm kosularini dondurur; bu uc ise
        calisma modelinin guncel taban cizgisidir.
        """
        payload = self._request(
            "GET", f"/api/v1/models/{model_id}/baseline-results", timeout=180
        )
        return ApiArchivedScenario.from_payload(payload["baseline"])

    def get_study_results(self, model_id: str) -> ApiStarStudy:
        return ApiStarStudy.from_payload(
            self._request("GET", f"/api/v1/models/{model_id}/study-results", timeout=180)
        )

    def quick_study(
        self,
        model_id: str,
        thicknesses_cm: list[float],
        conductivity_w_mk: float = 0.039,
    ) -> ApiQuickStudy:
        return ApiQuickStudy.from_payload(
            self._request(
                "POST",
                f"/api/v1/models/{model_id}/quick-study",
                {
                    "thicknesses_cm": thicknesses_cm,
                    "conductivity_w_mk": conductivity_w_mk,
                },
            )
        )

    @staticmethod
    def _simulation_payload(
        thicknesses_cm: list[float],
        conductivity_w_mk: float,
        target_construction: str = "duvr_std_eps",
    ) -> dict[str, object]:
        return {
            "thicknesses_cm": thicknesses_cm,
            "conductivity_w_mk": conductivity_w_mk,
            "target_construction": target_construction,
        }

    def prepare_simulations(
        self,
        model_id: str,
        thicknesses_cm: list[float],
        conductivity_w_mk: float,
        target_construction: str = "duvr_std_eps",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/models/{model_id}/workflows",
            self._simulation_payload(thicknesses_cm, conductivity_w_mk, target_construction),
        )

    def run_simulations(
        self,
        model_id: str,
        thicknesses_cm: list[float],
        conductivity_w_mk: float,
        target_construction: str = "duvr_std_eps",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/models/{model_id}/simulations",
            self._simulation_payload(thicknesses_cm, conductivity_w_mk, target_construction),
        )

    def list_simulations(self, model_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/models/{model_id}/simulations")
