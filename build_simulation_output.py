import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from apply_scenario_definition import load_scenario_definition, run_scenario_definition
from update_csv_fields import CsvUpdateError


DEFAULT_OUTPUT_ROOT = Path("simulation_outputs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Senaryo tanimindan simulasyon icin tekrar edilebilir cikti paketi uretir."
    )
    parser.add_argument(
        "--scenario-file",
        required=True,
        help="Calistirilacak JSON senaryo dosyasi yolu.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Senaryo ciktilarinin yazilacagi kok klasor.",
    )
    return parser.parse_args()


def build_output_paths(scenario_name: str, input_path: Path, output_root: Path) -> tuple[Path, Path, Path]:
    scenario_dir = output_root / scenario_name
    data_output = scenario_dir / f"{scenario_name}__{input_path.stem}.csv"
    log_output = scenario_dir / f"{scenario_name}__changes.json"
    manifest_output = scenario_dir / f"{scenario_name}__manifest.json"
    return data_output, log_output, manifest_output


def build_manifest(
    scenario: dict,
    scenario_file: Path,
    input_path: Path,
    data_output: Path,
    log_output: Path,
    change_count: int,
) -> dict:
    return {
        "scenario_name": scenario["scenario_name"],
        "scenario_file": str(scenario_file),
        "input_dataset": str(input_path),
        "output_dataset": str(data_output),
        "log_output": str(log_output),
        "operation_count": len(scenario["operations"]),
        "changed_field_count": change_count,
        "repeatable_flow": True,
    }


def write_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()
    scenario_file = Path(args.scenario_file)
    output_root = Path(args.output_root)

    try:
        scenario = load_scenario_definition(scenario_file)
        scenario_copy = deepcopy(scenario)
        input_path = Path(scenario_copy["input"])

        data_output, log_output, manifest_output = build_output_paths(
            scenario_copy["scenario_name"],
            input_path,
            output_root,
        )

        scenario_copy["output"] = str(data_output)
        scenario_copy["log_output"] = str(log_output)

        output_path, written_log_output, change_count = run_scenario_definition(scenario_copy)
        manifest = build_manifest(
            scenario_copy,
            scenario_file,
            input_path,
            output_path,
            written_log_output,
            change_count,
        )
        write_manifest(manifest_output, manifest)

        print(
            f"Simulasyon cikti paketi olusturuldu: {scenario_copy['scenario_name']}. "
            f"Veri cikti: {output_path}. Log: {written_log_output}. Manifest: {manifest_output}"
        )
        return 0

    except CsvUpdateError as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
