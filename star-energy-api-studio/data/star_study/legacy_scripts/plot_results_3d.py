import argparse
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
CSV_PATH = Path(r"C:\star\runs_parametric\summary.csv")
BATCH_SCRIPT = Path(r"C:\star\parametric_batch.py")


def refresh_summary():
    if not BATCH_SCRIPT.exists():
        raise FileNotFoundError(f"Batch script bulunamadi: {BATCH_SCRIPT}")

    cmd = [sys.executable, str(BATCH_SCRIPT)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            "OpenStudio calistirilamadi.\n"
            f"Komut: {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    print("OpenStudio verisi yenilendi.")
    if result.stdout.strip():
        print(result.stdout.strip())


parser = argparse.ArgumentParser()
parser.add_argument(
    "--refresh",
    action="store_true",
    help="OpenStudio senaryolarini yeniden calistirip summary.csv olusturur.",
)
args = parser.parse_args()

if args.refresh or not CSV_PATH.exists():
    refresh_summary()

df = pd.read_csv(CSV_PATH)

# Sayısal kolonları garantiye al
for c in ["thickness_m", "conductivity_w_mk", "heating_gj", "cooling_gj"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# Boş satırları at
df = df.dropna(subset=["thickness_m", "conductivity_w_mk", "heating_gj", "cooling_gj"])

# Toplam HVAC enerji
df["hvac_total_gj"] = df["heating_gj"] + df["cooling_gj"]

# 3D grafik
fig = plt.figure()
ax = fig.add_subplot(111, projection="3d")

ax.scatter(df["thickness_m"], df["conductivity_w_mk"], df["hvac_total_gj"])

# Türkçe eksen isimleri
ax.set_xlabel("Yalıtım Kalınlığı (m)")
ax.set_ylabel("Isı İletkenliği (W/mK)")
ax.set_zlabel("Toplam Isıtma + Soğutma Enerjisi (GJ)")

# Türkçe başlık
ax.set_title("Yalıtım Parametrelerine Göre Bina Enerji Tüketimi (3D Analiz)")

plt.show()

# En iyi senaryo
best = df.loc[df["hvac_total_gj"].idxmin()]
print("\nEN İYİ SENARYO (En düşük enerji tüketimi):")
print(best[["scenario", "thickness_m", "conductivity_w_mk", "heating_gj", "cooling_gj", "hvac_total_gj"]])

print("\nEN DÜŞÜK ENERJİ TÜKETEN 5 SENARYO:")
print(df.sort_values("hvac_total_gj").head(5)[["scenario","thickness_m","conductivity_w_mk","hvac_total_gj"]])
