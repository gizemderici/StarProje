"""Prepare a simulation with the official OpenStudio embedded Python SDK."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import openstudio


def prepare_simulation(
    osm_path: Path,
    output_idf: Path,
    output_osm: Path,
    target_construction: str,
    thickness_cm: float,
    conductivity_w_mk: float,
    density_kg_m3: float,
    specific_heat_j_kgk: float,
) -> dict[str, object]:
    translator = openstudio.osversion.VersionTranslator()
    optional_model = translator.loadModel(openstudio.path(str(osm_path)))
    if optional_model.empty():
        raise RuntimeError(f"OpenStudio modeli açamadı: {osm_path}")
    model = optional_model.get()

    optional_construction = model.getConstructionByName(target_construction)
    if optional_construction.empty():
        raise ValueError(f"Konstrüksiyon bulunamadı: {target_construction}")
    construction = optional_construction.get()

    eps = openstudio.model.StandardOpaqueMaterial(model)
    eps.setName(f"eps {thickness_cm:g} cm")
    eps.setRoughness("MediumRough")
    eps.setThickness(thickness_cm / 100.0)
    eps.setConductivity(conductivity_w_mk)
    eps.setDensity(density_kg_m3)
    eps.setSpecificHeat(specific_heat_j_kgk)

    layers = list(construction.layers())
    replaced_layers = []
    for index, layer in enumerate(layers):
        if "eps" in layer.nameString().casefold():
            replaced_layers.append(layer.nameString())
            layers[index] = eps
    if not replaced_layers:
        raise ValueError(f"{target_construction} içinde EPS katmanı bulunamadı.")
    if not construction.setLayers(layers):
        raise RuntimeError("OpenStudio konstrüksiyon katmanlarını güncelleyemedi.")

    reports = model.getOutputTableSummaryReports()
    existing_reports = {str(item) for item in reports.summaryReports()}
    for report_name in [
        "AnnualBuildingUtilityPerformanceSummary",
        "InputVerificationandResultsSummary",
    ]:
        if report_name not in existing_reports:
            reports.addSummaryReport(report_name)
    model.getOutputSQLite().setOptionType("SimpleAndTabular")

    output_osm.parent.mkdir(parents=True, exist_ok=True)
    if not model.save(openstudio.path(str(output_osm)), True):
        raise RuntimeError(f"Değiştirilmiş model kaydedilemedi: {output_osm}")

    forward_translator = openstudio.energyplus.ForwardTranslator()
    workspace = forward_translator.translateModel(model)
    output_idf.parent.mkdir(parents=True, exist_ok=True)
    if not workspace.save(openstudio.path(str(output_idf)), True):
        raise RuntimeError(f"EnergyPlus girdisi kaydedilemedi: {output_idf}")

    return {
        "openstudio_version": openstudio.openStudioVersion(),
        "target_construction": target_construction,
        "thickness_cm": thickness_cm,
        "replaced_layers": replaced_layers,
        "idf_objects": len(workspace.objects()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", required=True)
    parser.add_argument("--output-idf", required=True)
    parser.add_argument("--output-osm", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--target-construction", required=True)
    parser.add_argument("--thickness-cm", required=True, type=float)
    parser.add_argument("--conductivity", required=True, type=float)
    parser.add_argument("--density", required=True, type=float)
    parser.add_argument("--specific-heat", required=True, type=float)
    args = parser.parse_args()

    payload = prepare_simulation(
        osm_path=Path(args.osm).resolve(),
        output_idf=Path(args.output_idf).resolve(),
        output_osm=Path(args.output_osm).resolve(),
        target_construction=args.target_construction,
        thickness_cm=args.thickness_cm,
        conductivity_w_mk=args.conductivity,
        density_kg_m3=args.density,
        specific_heat_j_kgk=args.specific_heat,
    )
    manifest_path = Path(args.manifest).resolve()
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
