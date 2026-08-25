"""Senaryo parametrelerinin tek dogruluk kaynagi.

Her karar degiskeni burada bir kez tanimlanir. Hem OSW adimlarini uretmek, hem
istek dogrulamasi yapmak, hem de Faz 3'un ornekleme tasarimini beslemek icin
ayni kayit kullanilir. Yeni bir degisken eklemek = buraya bir satir eklemek.

Referans degerler data/input/gsf_fng_6mayis_onarilmis.osm modelinden okunmustur;
gerekceleri docs/baseline_assumptions.md dosyasindadir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """Bir karar degiskeni ve onu uygulayan measure argumani."""

    key: str
    """Senaryo sozlugunde kullanilan kanonik ad."""

    measure: str
    """Degiskeni uygulayan measure klasoru."""

    argument: str
    """Measure icindeki arguman adi."""

    baseline: float | str
    """Onarilmis modeldeki mevcut deger."""

    label: str
    """Arayuzde gosterilecek Turkce ad."""

    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()

    @property
    def is_categorical(self) -> bool:
        return bool(self.choices)

    def validate(self, value: float | str) -> float | str:
        if self.is_categorical:
            if value not in self.choices:
                raise ValueError(
                    f"{self.key}: gecersiz secim {value!r}. "
                    f"Izin verilenler: {', '.join(self.choices)}"
                )
            return value

        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{self.key}: sayisal deger bekleniyor, {value!r} geldi.") from exc
        if self.minimum is not None and number < self.minimum:
            raise ValueError(f"{self.key}: {number} < alt sinir {self.minimum}")
        if self.maximum is not None and number > self.maximum:
            raise ValueError(f"{self.key}: {number} > ust sinir {self.maximum}")
        return number


# Modelde tam tanimli yedi pencere konstruksiyonu. Bina su an listedeki en zayifi
# olan penc_std_4mm'i 114 pencerenin hepsinde kullaniyor; digerleri hic
# kosulmamistir. Bkz. docs/bulgular_faz1.md
WINDOW_CONSTRUCTIONS: tuple[str, ...] = (
    "penc_std_4mm",
    "penc_lowe_4mm",
    "penc_lowe_argon_4mm",
    "penc_cont_6_4mm",
    "penc_triple_lowe_4mm",
    "penc_snerji_4mm",
    "penc_renk_6mm",
)


PARAMETERS: tuple[ParameterSpec, ...] = (
    ParameterSpec(
        key="window_construction",
        measure="SetWindowConstruction",
        argument="target_construction",
        baseline="penc_std_4mm",
        label="Cam tipi",
        choices=WINDOW_CONSTRUCTIONS,
    ),
    ParameterSpec(
        key="heating_setpoint_c",
        measure="SetThermostatSetpoints",
        argument="heating_setpoint_c",
        baseline=22.0,
        label="Isitma ayar noktasi",
        unit="C",
        minimum=15.0,
        maximum=24.0,
    ),
    ParameterSpec(
        key="cooling_setpoint_c",
        measure="SetThermostatSetpoints",
        argument="cooling_setpoint_c",
        baseline=24.0,
        label="Sogutma ayar noktasi",
        unit="C",
        minimum=22.0,
        maximum=30.0,
    ),
    ParameterSpec(
        key="chiller_cop",
        measure="SetPlantEfficiency",
        argument="chiller_cop",
        baseline=5.5,
        label="Chiller COP",
        unit="W/W",
        minimum=2.0,
        maximum=8.0,
    ),
    ParameterSpec(
        key="boiler_efficiency",
        measure="SetPlantEfficiency",
        argument="boiler_efficiency",
        baseline=0.90,
        label="Kazan verimi",
        minimum=0.60,
        maximum=0.99,
    ),
    ParameterSpec(
        key="lighting_primary_w_m2",
        measure="SetLightingPower",
        argument="primary_w_m2",
        baseline=7.0,
        label="Aydinlatma - ofis, salon, atolye",
        unit="W/m2",
        minimum=1.0,
        maximum=15.0,
    ),
    ParameterSpec(
        key="lighting_secondary_w_m2",
        measure="SetLightingPower",
        argument="secondary_w_m2",
        baseline=3.0,
        label="Aydinlatma - koridor, merdiven, WC",
        unit="W/m2",
        minimum=0.5,
        maximum=8.0,
    ),
    ParameterSpec(
        key="infiltration_multiplier",
        measure="SetInfiltrationRate",
        argument="infiltration_multiplier",
        baseline=1.0,
        label="Sizdirmazlik carpani",
        minimum=0.3,
        maximum=1.5,
    ),
    ParameterSpec(
        key="elevator_power_w",
        measure="SetElevatorLoad",
        argument="elevator_power_w",
        baseline=5000.0,
        label="Asansor motoru gucu",
        unit="W",
        minimum=500.0,
        maximum=8000.0,
    ),
    ParameterSpec(
        key="eps_thickness_cm",
        measure="SetEpsThickness",
        argument="eps_thickness_cm",
        baseline=5.0,
        label="EPS kalinligi",
        unit="cm",
        minimum=0.5,
        maximum=30.0,
    ),
    ParameterSpec(
        key="eps_conductivity_w_mk",
        measure="SetEpsThickness",
        argument="conductivity_w_mk",
        baseline=0.039,
        label="EPS isil iletkenligi",
        unit="W/mK",
        minimum=0.015,
        maximum=0.060,
    ),
)


BY_KEY: Mapping[str, ParameterSpec] = {spec.key: spec for spec in PARAMETERS}

# Measure'lar bu sirayla calisir. Katman degisiklikleri once, isletme
# parametreleri sonra; boylece bir measure digerinin ciktisini bozmaz.
MEASURE_ORDER: tuple[str, ...] = (
    "SetEpsThickness",
    "SetWindowConstruction",
    "SetInfiltrationRate",
    "SetThermostatSetpoints",
    "SetPlantEfficiency",
    "SetLightingPower",
    "SetElevatorLoad",
)

# Her kosuya eklenen raporlama measure'lari. CreateCSVOutput her senaryo icin
# 8.760 satirlik zon verisi uretir; Faz 4'un konfor hedefi buna baglidir.
REPORTING_MEASURES: tuple[str, ...] = (
    "CreateCSVOutput",
    "OpenStudioResults",
)


def baseline_parameters() -> dict[str, float | str]:
    """Onarilmis modelin mevcut degerleri."""
    return {spec.key: spec.baseline for spec in PARAMETERS}


def validate_parameters(values: Mapping[str, float | str]) -> dict[str, float | str]:
    """Bilinmeyen anahtarlari reddeder, degerleri sinirlara gore dogrular."""
    unknown = set(values) - set(BY_KEY)
    if unknown:
        raise ValueError(
            f"Bilinmeyen parametre: {', '.join(sorted(unknown))}. "
            f"Tanimli olanlar: {', '.join(BY_KEY)}"
        )
    return {key: BY_KEY[key].validate(value) for key, value in values.items()}


def design_space() -> list[dict[str, object]]:
    """Faz 3 ornekleme tasarimi icin makine okunur tanim."""
    space: list[dict[str, object]] = []
    for spec in PARAMETERS:
        entry: dict[str, object] = {
            "key": spec.key,
            "label": spec.label,
            "unit": spec.unit,
            "baseline": spec.baseline,
            "type": "categorical" if spec.is_categorical else "continuous",
        }
        if spec.is_categorical:
            entry["choices"] = list(spec.choices)
        else:
            entry["minimum"] = spec.minimum
            entry["maximum"] = spec.maximum
        space.append(entry)
    return space
