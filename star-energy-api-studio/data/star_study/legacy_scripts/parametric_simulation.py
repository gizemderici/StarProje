import json
import subprocess
from pathlib import Path

OPENSTUDIO_EXE = r"C:\Program Files\OpenStudio\bin\openstudio.exe"
MODEL = r"C:\star\denemee.osm"
WEATHER = r"C:\star\weather\mugla.epw"

RUN_DIR = Path(r"C:\star\runs\test1")
RUN_DIR.mkdir(parents=True, exist_ok=True)

# OSW dosyasını RUN_DIR içine yazıyoruz
osw_path = RUN_DIR / "in.osw"
osw = {
    "seed_file": MODEL,
    "weather_file": WEATHER,
    "measure_paths": [],
    "steps": []
}
osw_path.write_text(json.dumps(osw, indent=2), encoding="utf-8")

# OpenStudio'yu RUN_DIR içinde çalıştır (output otomatik oluşur)
cmd = [
    OPENSTUDIO_EXE, "run",
    "-w", "in.osw"
]

print("Simülasyon başlatılıyor...")
result = subprocess.run(
    cmd,
    cwd=str(RUN_DIR),          
    capture_output=True,
    text=True
)

print("STDOUT:\n", result.stdout)
print("STDERR:\n", result.stderr)
print("Çıkış kodu:", result.returncode)
print("Simülasyon bitti.")
print("Çıktı klasörü (muhtemel):", RUN_DIR / "run")
