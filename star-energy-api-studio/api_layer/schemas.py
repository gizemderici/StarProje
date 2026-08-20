from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SimulationRequest(BaseModel):
    thicknesses_cm: list[float] = Field(min_length=1, max_length=50)
    conductivity_w_mk: float = Field(default=0.039, gt=0.0, le=1.0)
    density_kg_m3: float = Field(default=16.0, gt=0.0)
    specific_heat_j_kgk: float = Field(default=1250.0, gt=0.0)
    target_construction: str = Field(default="duvr_std_eps", min_length=1, max_length=200)

    @field_validator("thicknesses_cm")
    @classmethod
    def validate_thicknesses(cls, values: list[float]) -> list[float]:
        if any(value <= 0 or value > 100 for value in values):
            raise ValueError("EPS kalınlığı 0–100 cm aralığında olmalıdır.")
        return values


class QuickStudyRequest(BaseModel):
    thicknesses_cm: list[float] = Field(min_length=1, max_length=80)
    conductivity_w_mk: float = Field(default=0.039, gt=0.0, le=1.0)

    @field_validator("thicknesses_cm")
    @classmethod
    def validate_thicknesses(cls, values: list[float]) -> list[float]:
        if any(value <= 0 or value > 100 for value in values):
            raise ValueError("EPS kalınlığı 0–100 cm aralığında olmalıdır.")
        return values
