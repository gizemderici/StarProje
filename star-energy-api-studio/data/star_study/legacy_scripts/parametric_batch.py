import json
import subprocess
from pathlib import Path
import re
import csv
import shutil

import openstudio  # OpenStudio Python bindings

OPENSTUDIO_EXE = r"C:\Program Files\OpenStudio\bin\openstudio.exe"

MODEL_PATH = Path(r"C:\star\denemee.osm")
WEATHER_PATH = Path(r"C:\star\weather\mugla.epw")
RUNS_ROOT = Path(r"C:\star\runs_parametric")

# ---- Burayı modelindeki isimlere göre ayarla ----
INSULATION_MATERIAL_NAME = "izolasyon kopugu"  # Materials sekmesinde gördüğün isim
# Pencereyi şimdilik kapatıyoruz (binding'lerde getSimpleGlazingSystems yok)
ENABLE_WINDOW_PARAMETRIC = False
# -----------------------------------------------

RUNS_ROOT.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def load_model(path: Path) -> openstudio.model.Model:
    vt = openstudio.osversion.VersionTranslator()
    mo = vt.loadModel(openstudio.path(str(path)))

    if mo.empty():
        raise RuntimeError(f"Model yüklenemedi: {path}")

    return mo.get()


def save_model(model: openstudio.model.Model, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(openstudio.path(str(out_path)), True)


def _to_standard_opaque_material(material):
    """
    Farklı binding isimleri olabilir:
    - to_StandardOpaqueMaterial()
    - toStandardOpaqueMaterial()
    """
    if hasattr(material, "to_StandardOpaqueMaterial"):
        return material.to_StandardOpaqueMaterial()
    if hasattr(material, "toStandardOpaqueMaterial"):
        return material.toStandardOpaqueMaterial()
    return None


def set_insulation(model: openstudio.model.Model, thickness_m=None, conductivity_w_mk=None):
    mats = model.getMaterials()
    target = None

    for m in mats:
        if m.nameString().strip().lower() == INSULATION_MATERIAL_NAME.lower():
            target = m
            break

    if target is None:
        names = [m.nameString() for m in mats]
        raise RuntimeError(
            f"Yalıtım malzemesi bulunamadı: '{INSULATION_MATERIAL_NAME}'. "
            f"Modeldeki bazı malzeme isimleri: {names[:20]} ..."
        )

    opt = _to_standard_opaque_material(target)
    if opt is None:
        raise RuntimeError("Bu OpenStudio binding'inde StandardOpaqueMaterial cast fonksiyonu bulunamadı.")

    if opt.is_initialized():
        sm = opt.get()
        if thickness_m is not None:
            sm.setThickness(float(thickness_m))
        if conductivity_w_mk is not None:
            sm.setConductivity(float(conductivity_w_mk))
        return sm.nameString(), sm.thickness(), sm.conductivity()

    raise RuntimeError(f"Malzeme türü beklenenden farklı: {target.iddObjectType().valueName()}")


def make_osw(seed_osm: Path, weather: Path, out_dir: Path):
    osw = {
        "seed_file": str(seed_osm),
        "weather_file": str(weather),
        "measure_paths": [],
        "steps": []
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    osw_path = out_dir / "in.osw"
    osw_path.write_text(json.dumps(osw, indent=2), encoding="utf-8")
    return osw_path


def parse_end_uses_from_eplustbl(run_dir: Path):
    htm = run_dir / "run" / "eplustbl.htm"
    if not htm.exists():
        return None

    txt = htm.read_text(errors="ignore")

    def get_row(label):
        m = re.search(rf">{label}<.*?</tr>", txt, flags=re.IGNORECASE | re.DOTALL)
        return m.group(0) if m else None

    def extract_numbers(row_html):
        return [float(x) for x in re.findall(r"(-?\d+\.\d+)", row_html)]

    total_row = get_row("Total End Uses")
    heat_row = get_row("Heating")
    cool_row = get_row("Cooling")

    if not total_row or not heat_row or not cool_row:
        return None

    total_nums = extract_numbers(total_row)
    heat_nums = extract_numbers(heat_row)
    cool_nums = extract_numbers(cool_row)

    total_electricity_gj = total_nums[0] if len(total_nums) > 0 else None
    heating_gj = max(heat_nums) if heat_nums else None
    cooling_gj = max(cool_nums) if cool_nums else None

    return total_electricity_gj, heating_gj, cooling_gj


# --- 20 senaryo tasarımı (yalıtım ağırlıklı) ---
THICKNESS_LEVELS = [0.03, 0.05, 0.07]       # metre
CONDUCTIVITY_LEVELS = [0.03, 0.04, 0.05]    # W/mK (daha düşük = daha iyi yalıtım)

scenarios = [{"name": "S00_baseline", "th": None, "k": None}]

idx = 1
for th in THICKNESS_LEVELS:
    for k in CONDUCTIVITY_LEVELS:
        scenarios.append({"name": f"S{idx:02d}_th{th}_k{k}", "th": th, "k": k})
        idx += 1
        if len(scenarios) >= 20:
            break
    if len(scenarios) >= 20:
        break

# 20 olmadıysa doldur
thk_pairs = [(0.04, 0.04), (0.06, 0.035), (0.08, 0.03), (0.02, 0.05)]
p = 0
while len(scenarios) < 20:
    th, k = thk_pairs[p % len(thk_pairs)]
    scenarios.append({"name": f"S{len(scenarios):02d}_th{th}_k{k}_extra", "th": th, "k": k})
    p += 1


results = []

for sc in scenarios:
    sc_dir = RUNS_ROOT / sc["name"]
    if sc_dir.exists():
        shutil.rmtree(sc_dir)
    sc_dir.mkdir(parents=True, exist_ok=True)

    model = load_model(MODEL_PATH)

    ins_info = None
    if sc["th"] is not None or sc["k"] is not None:
        ins_info = set_insulation(model, thickness_m=sc["th"], conductivity_w_mk=sc["k"])

    seed_path = sc_dir / "seed.osm"
    save_model(model, seed_path)

    osw_path = make_osw(seed_path, WEATHER_PATH, sc_dir)

    code, out, err = run_cmd([OPENSTUDIO_EXE, "run", "-w", str(osw_path)], cwd=str(sc_dir))

    (sc_dir / "stdout.txt").write_text(out or "", encoding="utf-8", errors="ignore")
    (sc_dir / "stderr.txt").write_text(err or "", encoding="utf-8", errors="ignore")

    parsed = parse_end_uses_from_eplustbl(sc_dir)

    results.append({
        "scenario": sc["name"],
        "insulation_name": ins_info[0] if ins_info else "",
        "thickness_m": float(ins_info[1]) if ins_info else "",
        "conductivity_w_mk": float(ins_info[2]) if ins_info else "",
        "total_electricity_gj": parsed[0] if parsed else "",
        "heating_gj": parsed[1] if parsed else "",
        "cooling_gj": parsed[2] if parsed else "",
        "exit_code": code,
    })

out_csv = RUNS_ROOT / "summary.csv"
with out_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)

print("Bitti")
print("CSV:", out_csv)
print("Runs:", RUNS_ROOT)