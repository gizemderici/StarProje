"""Faz 1 model onarimi.

Kanonik modeldeki uc olculmus kusuru resmi OpenStudio SDK ile giderir ve
onarilmis modeli ayri bir dosyaya yazar. Kaynak model degistirilmez.

Kusurlar ve gerekceleri: docs/bulgular_faz1.md

Kullanim (OpenStudio'nun gomulu Python yorumlayicisi ile):
    openstudio.exe execute_python_script model_repair_worker.py \
        --input  data/input/gsf_fng_6mayis.osm \
        --output data/input/gsf_fng_6mayis_onarilmis.osm \
        --report data/input/onarim_raporu.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import openstudio


# Asansor motorunun baglanacagi tek mekan. Makine dairesi en ust katta oldugu
# icin K2 secildi; bkz. docs/baseline_assumptions.md
ELEVATOR_HOST_SPACE = "K2_ASNS_1"

# EnergyPlus'in kapali cokyuzlu kuramadigi ve 10 m3 varsayilana dustugu zonlar.
VOLUME_FIX_ZONES = ("TZ_atolye", "TZ_koridor", "TZ_WC")

# Asansor boslugu HVAC ile servis edilmiyor. Yonetmelik geregi kuyular tepeden
# havalandirilir; modelde bu havalandirma hic tanimlanmamis, bu yuzden 5 kW'lik
# motor isisi bolgede hapsoluyor.
# Boyutlandirma: Q = m*cp*dT  ->  V = 5000 / (1,2 * 1005 * 10) = 0,414 m3/s
# yani motor tepe gucundeki isiyi ~10 K sicaklik farkiyla atacak debi.
SHAFT_ZONE = "TZ_asnsr"
SHAFT_VENTILATION_M3_S = 0.414


def fix_elevator_equipment(model, report):
    """5.000 W asansor motorunu SpaceType yerine tek bir mekana bagla.

    Tanim `asnsr` SpaceType'ina bagliyken, o SpaceType'a ait dort mekanin
    (KZ/KB/K1/K2) her birinde ayri ayri ornekleniyor ve toplam 20.000 W
    olusuyor. Tek asansorun motoru bir kez sayilmalidir.
    """
    changed = []
    for equipment in model.getElectricEquipments():
        definition = equipment.electricEquipmentDefinition()
        level = definition.designLevel()
        if not level.is_initialized() or level.get() < 1000:
            continue
        space_type = equipment.spaceType()
        if not space_type.is_initialized():
            continue

        member_spaces = [s.nameString() for s in space_type.get().spaces()]
        host = model.getSpaceByName(ELEVATOR_HOST_SPACE)
        if host.empty():
            raise RuntimeError(f"Mekan bulunamadi: {ELEVATOR_HOST_SPACE}")

        equipment.resetSpaceType()
        if not equipment.setSpace(host.get()):
            raise RuntimeError(f"{equipment.nameString()} mekana baglanamadi.")

        changed.append({
            "equipment": equipment.nameString(),
            "definition": definition.nameString(),
            "design_level_w": level.get(),
            "eski_baglanti": f"SpaceType {space_type.get().nameString()}",
            "eski_ornek_sayisi": len(member_spaces),
            "eski_toplam_w": level.get() * len(member_spaces),
            "yeni_baglanti": f"Space {ELEVATOR_HOST_SPACE}",
            "yeni_toplam_w": level.get(),
        })
    report["1.1_asansor"] = changed
    return len(changed)


def fix_zone_volumes(model, report):
    """EnergyPlus'in hesaplayamadigi zon hacimlerini acikca yaz.

    Zonlar tam kapali olmadigi icin EnergyPlus hacmi cikaramiyor ve 10 m3
    varsayilana dusuyor. OpenStudio mekan geometrilerinden hacmi hesaplayabildigi
    icin toplami dogrudan zona yaziyoruz.
    """
    changed = []
    for zone in model.getThermalZones():
        if zone.nameString() not in VOLUME_FIX_ZONES:
            continue
        total = sum(space.volume() for space in zone.spaces())
        if total <= 0:
            raise RuntimeError(f"{zone.nameString()} icin hacim hesaplanamadi.")
        if not zone.setVolume(total):
            raise RuntimeError(f"{zone.nameString()} hacmi yazilamadi.")
        changed.append({
            "zone": zone.nameString(),
            "mekan_sayisi": len(zone.spaces()),
            "yazilan_hacim_m3": round(total, 2),
            "onceki_davranis": "EnergyPlus 10 m3 varsayilanina dusuyordu",
        })
    report["1.3_zon_hacmi"] = changed
    return len(changed)


def add_shaft_ventilation(model, report):
    """Asansor bosluguna dogal havalandirma tanimla.

    Bolgenin termostati var ancak ZoneHVAC cihazi yok; ayar noktasini
    karsilayacak ekipman bulunmadigi icin sicaklik serbest yuzuyor. Dogal
    havalandirma (Ventilation Type = Natural) fan enerjisi eklemez.
    """
    added = []
    optional = model.getThermalZoneByName(SHAFT_ZONE)
    if optional.empty():
        raise RuntimeError(f"Bolge bulunamadi: {SHAFT_ZONE}")
    zone = optional.get()

    always_on = model.alwaysOnDiscreteSchedule()
    ventilation = openstudio.model.ZoneVentilationDesignFlowRate(model)
    ventilation.setName("asansor boslugu havalandirmasi")
    ventilation.setSchedule(always_on)
    ventilation.setDesignFlowRate(SHAFT_VENTILATION_M3_S)
    ventilation.setVentilationType("Natural")
    ventilation.setFanPressureRise(0.0)
    ventilation.setFanTotalEfficiency(1.0)
    ventilation.addToThermalZone(zone)

    added.append({
        "zone": SHAFT_ZONE,
        "design_flow_m3_s": SHAFT_VENTILATION_M3_S,
        "ventilation_type": "Natural",
        "fan_enerjisi": "yok",
        "gerekce": "Bolgede ZoneHVAC cihazi yok; motor isisi hapsoluyordu.",
    })
    report["1.2_kuyu_havalandirmasi"] = added
    return len(added)


def remove_unused_glazing(model, report):
    """Hicbir konstruksiyonda kullanilmayan gercek disi cam tanimini sil.

    U = 0,1 W/m2K ve SHGC = 0,1 hicbir gercek camda gorulmez; yanlislikla bir
    senaryoya girerse sonucu sessizce bozar.
    """
    # directUseCount() malzemeye bagli StandardsInformation alt nesnesini de
    # sayar; gercek olcut, malzemenin bir konstruksiyon katmani olmasidir.
    used = set()
    for construction in model.getConstructions():
        for layer in construction.layers():
            used.add(layer.handle())

    removed = []
    for material in model.getSimpleGlazings():
        if material.handle() in used:
            continue
        removed.append({
            "material": material.nameString(),
            "u_factor_w_m2k": material.uFactor(),
            "shgc": material.solarHeatGainCoefficient(),
        })
        material.remove()
    report["1.5_kullanilmayan_cam"] = removed
    return len(removed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    source = Path(args.input).resolve()
    target = Path(args.output).resolve()
    if source == target:
        raise SystemExit("Kaynak model uzerine yazilamaz; farkli bir --output verin.")

    optional = openstudio.osversion.VersionTranslator().loadModel(openstudio.path(str(source)))
    if optional.empty():
        raise SystemExit(f"Model acilamadi: {source}")
    model = optional.get()

    report: dict[str, object] = {
        "openstudio_version": openstudio.openStudioVersion(),
        "kaynak_model": source.name,
    }

    counts = {
        "asansor": fix_elevator_equipment(model, report),
        "kuyu_havalandirmasi": add_shaft_ventilation(model, report),
        "zon_hacmi": fix_zone_volumes(model, report),
        "kullanilmayan_cam": remove_unused_glazing(model, report),
    }
    report["degisiklik_sayilari"] = counts

    target.parent.mkdir(parents=True, exist_ok=True)
    if not model.save(openstudio.path(str(target)), True):
        raise SystemExit(f"Onarilmis model kaydedilemedi: {target}")

    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
