"""NiceGUI arayuzunun rapora girecek ekran goruntulerini yakalar.

Arayuz ayakta olmalidir:
    .venv\\Scripts\\python.exe app.py

Sonra:
    .venv\\Scripts\\python.exe -m reporting.ekran_goruntuleri
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data/rapor/ekran_goruntuleri"
UI_URL = "http://127.0.0.1:8090"

# Yakalama, ekran goruntusunun raporda okunabilir kalmasi icin genis ve
# yuksek cozunurluklu bir goruntu penceresiyle yapilir.
VIEWPORT = {"width": 1500, "height": 1000}
SCALE = 2


@dataclass(frozen=True, slots=True)
class Shot:
    """Bir sekme ve ondan uretilecek gorsel."""

    filename: str
    tab_label: str
    # Sekme icerigi yuklendikten sonra beklenecek ek sure (saniye).
    settle: float = 1.6
    full_page: bool = False


SHOTS = (
    Shot("ekran_1_enerji_merkezi.png", "Enerji Merkezi", settle=2.2),
    Shot("ekran_2_senaryo_kurucu.png", "Senaryo Kurucu"),
    Shot("ekran_3_model_varliklar.png", "Model ve Varlıklar"),
    Shot("ekran_4_vekil_model.png", "Vekil Model", settle=2.2),
    Shot("ekran_5_pareto.png", "Pareto", settle=2.2),
    Shot("ekran_6_iso50001.png", "ISO 50001", settle=2.0),
    Shot("ekran_7_dogrulama.png", "Doğrulama", settle=2.0),
)


def _dismiss_welcome_dialog(page) -> None:
    """Acilistaki karsilama diyalogunu kapatir.

    Diyalogun saydam kalkani sekme tiklamalarini yuttugu icin, kapatilmadan
    ekran goruntusu alinamaz.
    """
    for _ in range(3):
        if not page.query_selector(".q-dialog"):
            return
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
    # Escape ile kapanmazsa kalkana tiklamayi dener.
    backdrop = page.query_selector(".q-dialog__backdrop")
    if backdrop:
        backdrop.click(force=True)
        page.wait_for_timeout(600)


def capture(output_dir: Path = OUTPUT_DIR, url: str = UI_URL) -> list[Path]:
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=SCALE,
            locale="tr-TR",
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=60_000)
        # NiceGUI soket uzerinden dolduruldugu icin ilk cizim beklenir.
        page.wait_for_selector("text=GENEL BAKIŞ", timeout=60_000)
        time.sleep(2.0)
        _dismiss_welcome_dialog(page)

        for shot in SHOTS:
            tab = page.get_by_role("tab", name=shot.tab_label, exact=False).first
            tab.click()
            page.wait_for_timeout(int(shot.settle * 1000))
            destination = output_dir / shot.filename
            page.screenshot(path=str(destination), full_page=shot.full_page)
            written.append(destination)
            print("yakalandi:", destination.name)

        context.close()
        browser.close()
    return written


if __name__ == "__main__":
    for path in capture():
        print(path)
