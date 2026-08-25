import os
from pathlib import Path

import openstudio as openstudio


OSM_PATH = os.environ.get(
    "STAR_OSM_PATH",
    str(Path(__file__).resolve().parent / "star-energy-api-studio/data/input/gsf_fng_6mayis.osm"),
)


def main() -> None:
    translator = openstudio.osversion.VersionTranslator()
    model_optional = translator.loadModel(openstudio.path(OSM_PATH))

    if model_optional.is_initialized():
        model = model_optional.get()
        print("Model yüklendi")
        print("OpenStudio surumu:", openstudio.openStudioVersion())
        print("Space sayisi:", len(model.getSpaces()))
        print("Thermal Zone sayisi:", len(model.getThermalZones()))
        print("Surface sayisi:", len(model.getSurfaces()))
        print("Construction sayisi:", len(model.getConstructions()))
        print("Material sayisi:", len(model.getMaterials()))
        return

    print("Model yuklenemedi")


if __name__ == "__main__":
    main()
