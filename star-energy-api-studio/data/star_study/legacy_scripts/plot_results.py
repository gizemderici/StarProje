from pathlib import Path
import csv
import math

import matplotlib.pyplot as plt

CSV_PATH = Path(r"C:\star\runs_parametric\summary.csv")
OUT_DIR = CSV_PATH.parent

def to_float(x):
    try:
        return float(x)
    except:
        return None

rows = []
with CSV_PATH.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        th = to_float(r.get("thickness_m"))
        k  = to_float(r.get("conductivity_w_mk"))
        heat = to_float(r.get("heating_gj"))
        cool = to_float(r.get("cooling_gj"))
        elec = to_float(r.get("total_electricity_gj"))
        if th is None or k is None or heat is None or cool is None:
            continue
        rows.append({
            "scenario": r.get("scenario", ""),
            "th": th,
            "k": k,
            "heat": heat,
            "cool": cool,
            "elec": elec,
            "hvac": heat + cool
        })

if not rows:
    raise SystemExit("CSV'den veri okunamadı. thickness_m / conductivity_w_mk / heating_gj / cooling_gj boş olabilir.")

# --- Grafik 1: Kalınlık vs (Heating+Cooling) ---
x = [r["th"] for r in rows]
y = [r["hvac"] for r in rows]

plt.figure()
plt.scatter(x, y)
plt.xlabel("Yalıtım Kalınlığı (m)")
plt.ylabel("Heating + Cooling (GJ)")
plt.title("Kalınlık vs Isıtma+Soğutma")
plt.grid(True, which="both", linestyle="--", linewidth=0.5)
out1 = OUT_DIR / "plot_thickness_vs_hvac.png"
plt.savefig(out1, dpi=150, bbox_inches="tight")
plt.close()

# --- Grafik 2: İletkenlik vs (Heating+Cooling) ---
x = [r["k"] for r in rows]
y = [r["hvac"] for r in rows]

plt.figure()
plt.scatter(x, y)
plt.xlabel("Isı İletkenliği k (W/mK)")
plt.ylabel("Heating + Cooling (GJ)")
plt.title("İletkenlik vs Isıtma+Soğutma")
plt.grid(True, which="both", linestyle="--", linewidth=0.5)
out2 = OUT_DIR / "plot_conductivity_vs_hvac.png"
plt.savefig(out2, dpi=150, bbox_inches="tight")
plt.close()

# --- Grafik 3: Senaryoların HVAC toplamını çizgi grafik (sıralı) ---
rows_sorted = sorted(rows, key=lambda r: r["hvac"])
y = [r["hvac"] for r in rows_sorted]
labels = [r["scenario"] for r in rows_sorted]

plt.figure(figsize=(10, 4))
plt.plot(range(len(y)), y)
plt.xticks(range(len(y)), labels, rotation=70, ha="right", fontsize=7)
plt.ylabel("Heating + Cooling (GJ)")
plt.title("Senaryolar (En düşükten en yükseğe)")
plt.grid(True, which="both", linestyle="--", linewidth=0.5)
out3 = OUT_DIR / "plot_scenarios_sorted_hvac.png"
plt.savefig(out3, dpi=150, bbox_inches="tight")
plt.close()

best = rows_sorted[0]
print("Grafikler kaydedildi")
print("1)", out1)
print("2)", out2)
print("3)", out3)
print(f"En iyi senaryo: {best['scenario']} | th={best['th']} m | k={best['k']} W/mK | HVAC={best['hvac']:.2f} GJ")