"""Rapordaki Word alanlarini gunceller: Icindekiler, Tablo/Sekil Listesi,
sayfa numaralari.

Bu adim python-docx ile yapilamaz: sayfa numaralari ancak belgeyi sayfalayan
bir ofis uygulamasi tarafindan hesaplanabilir. Word veya WPS Office'in COM
arayuzu kullanilir.

Rapor her yeniden derlendiginde alanlar bosalir; bu betik derlemeden SONRA
calistirilmalidir:

    python -m reporting.sonuc_raporu
    python -m reporting.alanlari_guncelle
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "data/rapor/Proje_Sonuc_Raporu.docx"

# Word kurulu olmayabilir; WPS Office ayni arayuzu saglar.
PROG_IDS = ("Word.Application", "KWPS.Application", "Kwps.Application")


def _application():
    import win32com.client  # type: ignore

    errors = []
    for prog_id in PROG_IDS:
        try:
            return win32com.client.Dispatch(prog_id), prog_id
        except Exception as exc:  # pragma: no cover - ortama bagli
            errors.append(f"{prog_id}: {exc}")
    raise SystemExit(
        "Word veya WPS Office COM arayuzu bulunamadi. Denenen:\n  "
        + "\n  ".join(errors)
    )


def update(path: Path = DEFAULT_REPORT) -> int:
    """Alanlari gunceller ve belgenin sayfa sayisini dondurur."""
    if not path.is_file():
        raise SystemExit(f"Rapor bulunamadi: {path}")

    application, prog_id = _application()
    application.Visible = False
    application.DisplayAlerts = 0
    try:
        document = application.Documents.Open(str(path))
        # Once icindekiler ve listeler, sonra govdedeki diger alanlar.
        for table_of_contents in document.TablesOfContents:
            table_of_contents.Update()
        document.Fields.Update()
        for section in document.Sections:
            for footer in section.Footers:
                footer.Range.Fields.Update()
        document.Repaginate()
        pages = int(document.ComputeStatistics(2))  # wdStatisticPages
        document.Save()
        document.Close(0)
        print(f"{prog_id} ile guncellendi: {path.name} ({pages} sayfa)")
        return pages
    finally:
        application.Quit()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    update(target)
