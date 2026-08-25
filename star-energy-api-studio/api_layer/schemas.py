from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from engine.parameters import BY_KEY, design_space, validate_parameters


class ScenarioRequest(BaseModel):
    """Bir veya daha fazla senaryo; her senaryo bir parametre sozlugudur.

    Yalnizca referanstan sapan parametreler verilir; eksik kalanlar
    engine.parameters icindeki referans degerlerle doldurulur.
    """

    scenarios: list[dict[str, Any]] = Field(min_length=1, max_length=250)

    @field_validator("scenarios")
    @classmethod
    def validate_scenarios(cls, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Dogrulama tek yerde: engine.parameters. Sinirlar degisince veya yeni
        # bir degisken eklenince bu sema kendiliginden guncel kalir.
        return [validate_parameters(item) for item in values]


class SimulationRequest(ScenarioRequest):
    """Gercek EnergyPlus kosusu istegi."""


class QuickStudyRequest(BaseModel):
    """Hizli tahmin yalnizca EPS kalinligina duyarlidir; ayri kalir."""

    thicknesses_cm: list[float] = Field(min_length=1, max_length=80)
    conductivity_w_mk: float = Field(default=0.039, gt=0.0, le=1.0)

    @field_validator("thicknesses_cm")
    @classmethod
    def validate_thicknesses(cls, values: list[float]) -> list[float]:
        spec = BY_KEY["eps_thickness_cm"]
        for value in values:
            spec.validate(value)
        return values


def parameter_catalog() -> dict[str, object]:
    """Arayuzun ve Faz 3 ornekleme tasariminin okudugu makine okunur tanim."""
    return {"parameters": design_space()}
