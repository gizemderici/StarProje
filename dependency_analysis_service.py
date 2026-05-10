from pathlib import Path

from analyze_csv_dependencies import (
    DATASETS,
    CsvRepository,
    DependencyAnalysisError,
    SUB_SURFACE_FILES,
    SURFACE_FILES,
    analyze_construction_dependency,
    analyze_construction_layer_dependency,
    analyze_material_dependency,
    analyze_row_dependency,
    analyze_space_dependency,
    analyze_sub_surface_dependency,
    analyze_surface_dependency,
    analyze_zone_dependency,
)


def analyze_dependency_for_match(
    csv_root: Path | str,
    dataset_name: str,
    match_column: str,
    match_value: str,
    changed_column: str | None,
) -> dict:
    repo = CsvRepository(Path(csv_root))
    return analyze_row_dependency(
        repo,
        dataset_name,
        match_column,
        match_value,
        changed_column,
    )


def analyze_specific_row(
    repo: CsvRepository,
    dataset_name: str,
    row: dict,
    changed_column: str | None,
) -> dict:
    if dataset_name == "materials.csv":
        report = analyze_material_dependency(repo, row, changed_column)
    elif dataset_name == "constructions.csv":
        report = analyze_construction_dependency(repo, row, changed_column)
    elif dataset_name == "construction_layers.csv":
        report = analyze_construction_layer_dependency(repo, row, changed_column)
    elif dataset_name == "spaces.csv":
        report = analyze_space_dependency(repo, row, changed_column)
    elif dataset_name == "zones.csv":
        report = analyze_zone_dependency(repo, row, changed_column)
    elif dataset_name in SURFACE_FILES:
        report = analyze_surface_dependency(repo, dataset_name, row, changed_column)
    elif dataset_name in SUB_SURFACE_FILES:
        report = analyze_sub_surface_dependency(repo, dataset_name, row, changed_column)
    else:
        raise DependencyAnalysisError(f"Bagimlilik analizi desteklenmeyen veri seti: {dataset_name}")

    key_columns = DATASETS[dataset_name]["key_columns"]
    preview_columns = DATASETS[dataset_name]["key_columns"] + [changed_column] if changed_column else key_columns
    report["matched_row"] = {
        "row_key": " | ".join(f"{column}={row.get(column, '')}" for column in key_columns),
        "preview": {
            key: row.get(key, "")
            for key in preview_columns
            if key in row
        },
    }
    return report


def get_direct_affected_tables(impact_report: dict) -> list[dict]:
    direct_tables: dict[str, dict] = {}

    for report_item in impact_report.get("reports", []):
        for impact in report_item.get("impacts", []):
            if impact.get("impact_type") != "direct":
                continue

            dataset_name = str(impact.get("dataset", ""))
            table_summary = direct_tables.setdefault(
                dataset_name,
                {
                    "dataset": dataset_name,
                    "affected_row_count": 0,
                    "reasons": [],
                    "sources": [],
                },
            )
            table_summary["affected_row_count"] += int(impact.get("affected_row_count", 0))
            reason = str(impact.get("reason", "")).strip()
            via = str(impact.get("via", "")).strip()
            if reason and reason not in table_summary["reasons"]:
                table_summary["reasons"].append(reason)
            if via and via not in table_summary["sources"]:
                table_summary["sources"].append(via)

    return sorted(
        direct_tables.values(),
        key=lambda item: (-item["affected_row_count"], item["dataset"]),
    )


def get_indirect_affected_items(impact_report: dict) -> list[dict]:
    items = []

    for report_item in impact_report.get("reports", []):
        source_row_key = report_item.get("matched_row", {}).get("row_key", "")
        for impact in report_item.get("impacts", []):
            if impact.get("impact_type") != "indirect":
                continue

            sample_rows = impact.get("sample_rows", [])
            if not sample_rows:
                items.append(
                    {
                        "dataset": impact.get("dataset", ""),
                        "row_key": "",
                        "preview": {},
                        "via": impact.get("via", ""),
                        "reason": impact.get("reason", ""),
                        "source_row_key": source_row_key,
                        "affected_row_count": int(impact.get("affected_row_count", 0)),
                    }
                )
                continue

            for sample_row in sample_rows:
                items.append(
                    {
                        "dataset": impact.get("dataset", ""),
                        "row_key": sample_row.get("row_key", ""),
                        "preview": sample_row.get("preview", {}),
                        "via": impact.get("via", ""),
                        "reason": impact.get("reason", ""),
                        "source_row_key": source_row_key,
                        "affected_row_count": int(impact.get("affected_row_count", 0)),
                    }
                )

    return items


def get_layer_relationships(impact_report: dict) -> list[dict]:
    relationships = []

    for report_item in impact_report.get("reports", []):
        source_dataset = impact_report.get("dataset", "")
        source_row_key = report_item.get("matched_row", {}).get("row_key", "")
        changed_column = report_item.get("changed_column", "")

        if source_dataset == "construction_layers.csv":
            relationships.append(
                {
                    "source_dataset": source_dataset,
                    "source_row_key": source_row_key,
                    "target_dataset": "construction_layers.csv",
                    "target_row_key": source_row_key,
                    "relationship_type": "layer_origin",
                    "changed_column": changed_column,
                    "reason": "Degisim dogrudan bir katman kaydinda basladi.",
                }
            )

        for impact in report_item.get("impacts", []):
            impact_dataset = str(impact.get("dataset", ""))
            via = str(impact.get("via", ""))
            if impact_dataset != "construction_layers.csv" and "construction_layers.csv" not in via:
                continue

            sample_rows = impact.get("sample_rows", [])
            if not sample_rows:
                relationships.append(
                    {
                        "source_dataset": source_dataset,
                        "source_row_key": source_row_key,
                        "target_dataset": impact_dataset,
                        "target_row_key": "",
                        "relationship_type": "layer_chain",
                        "changed_column": changed_column,
                        "reason": impact.get("reason", ""),
                    }
                )
                continue

            for sample_row in sample_rows:
                relationships.append(
                    {
                        "source_dataset": source_dataset,
                        "source_row_key": source_row_key,
                        "target_dataset": impact_dataset,
                        "target_row_key": sample_row.get("row_key", ""),
                        "relationship_type": "layer_chain",
                        "changed_column": changed_column,
                        "reason": impact.get("reason", ""),
                    }
                )

    return relationships


def get_affected_layer_items(impact_report: dict) -> list[dict]:
    layer_items = []

    for report_item in impact_report.get("reports", []):
        source_dataset = str(impact_report.get("dataset", ""))
        source_row = report_item.get("matched_row", {})
        source_preview = source_row.get("preview", {})
        source_row_key = str(source_row.get("row_key", ""))
        changed_column = str(report_item.get("changed_column", "")).strip()

        if source_dataset == "construction_layers.csv":
            construction_name = str(source_preview.get("construction_name", "")).strip()
            layer_index = str(source_preview.get("layer_index", "")).strip()
            material_name = str(source_preview.get("name", "")).strip()
            layer_items.append(
                {
                    "layer_name": f"{construction_name} | {layer_index}" if construction_name or layer_index else source_row_key,
                    "material_name": material_name or "-",
                    "changed_field": changed_column or "-",
                    "construction_names": [construction_name] if construction_name else [],
                    "source_row_key": source_row_key,
                    "target_row_key": source_row_key,
                    "badge": "Degisen Layer",
                }
            )

        for impact in report_item.get("impacts", []):
            impact_dataset = str(impact.get("dataset", ""))
            via = str(impact.get("via", ""))
            if impact_dataset != "construction_layers.csv" and "construction_layers.csv" not in via:
                continue

            for sample_row in impact.get("sample_rows", []):
                preview = sample_row.get("preview", {})
                construction_name = str(preview.get("construction_name", "")).strip()
                layer_index = str(preview.get("layer_index", "")).strip()
                material_name = str(preview.get("name", "")).strip()
                target_row_key = str(sample_row.get("row_key", ""))
                layer_items.append(
                    {
                        "layer_name": f"{construction_name} | {layer_index}" if construction_name or layer_index else target_row_key,
                        "material_name": material_name or "-",
                        "changed_field": changed_column or "-",
                        "construction_names": [construction_name] if construction_name else [],
                        "source_row_key": source_row_key,
                        "target_row_key": target_row_key,
                        "badge": (
                            "Degisen Layer"
                            if source_dataset == "construction_layers.csv" and target_row_key == source_row_key
                            else "Etkilenen Layer"
                        ),
                    }
                )

    deduped = {}
    for item in layer_items:
        key = (
            item["target_row_key"],
            item["changed_field"],
            tuple(item["construction_names"]),
            item["badge"],
        )
        deduped[key] = item
    return list(deduped.values())


def get_affected_surface_items(impact_report: dict) -> list[dict]:
    surface_items = []
    surface_labels = {
        "walls.csv": "Wall",
        "roofs.csv": "Roof",
        "floors.csv": "Floor",
    }

    for report_item in impact_report.get("reports", []):
        changed_field = str(report_item.get("changed_column", "")).strip()
        for impact in report_item.get("impacts", []):
            dataset_name = str(impact.get("dataset", "")).strip()
            if dataset_name not in surface_labels:
                continue

            for sample_row in impact.get("sample_rows", []):
                preview = sample_row.get("preview", {})
                surface_items.append(
                    {
                        "dataset": dataset_name,
                        "surface_kind": surface_labels[dataset_name],
                        "surface_name": str(preview.get("name", "")).strip() or str(sample_row.get("row_key", "")).strip(),
                        "construction_name": str(preview.get("construction_name", "")).strip() or "-",
                        "changed_field": changed_field or "-",
                        "reason": str(impact.get("reason", "")).strip() or "-",
                        "impact_type": str(impact.get("impact_type", "")).strip() or "-",
                        "source_row_key": str(report_item.get("matched_row", {}).get("row_key", "")).strip(),
                    }
                )

    deduped = {}
    for item in surface_items:
        key = (
            item["dataset"],
            item["surface_name"],
            item["construction_name"],
            item["changed_field"],
            item["reason"],
        )
        deduped[key] = item
    return list(deduped.values())


def build_dependency_service_model(
    csv_root: Path | str,
    dataset_name: str,
    match_column: str,
    match_value: str,
    changed_column: str | None,
) -> dict:
    raw_report = analyze_dependency_for_match(
        csv_root=csv_root,
        dataset_name=dataset_name,
        match_column=match_column,
        match_value=match_value,
        changed_column=changed_column,
    )
    return {
        "raw_report": raw_report,
        "direct_affected_tables": get_direct_affected_tables(raw_report),
        "indirect_affected_items": get_indirect_affected_items(raw_report),
        "layer_relationships": get_layer_relationships(raw_report),
        "affected_layers": get_affected_layer_items(raw_report),
        "affected_surfaces": get_affected_surface_items(raw_report),
    }


def build_dependency_service_model_for_row(
    repo: CsvRepository,
    dataset_name: str,
    row: dict,
    changed_column: str | None,
) -> dict:
    report_item = analyze_specific_row(
        repo=repo,
        dataset_name=dataset_name,
        row=row,
        changed_column=changed_column,
    )
    raw_report = {
        "csv_root": repo.csv_root.as_posix(),
        "dataset": dataset_name,
        "match_column": "",
        "match_value": "",
        "changed_column": changed_column,
        "matched_row_count": 1,
        "reports": [report_item],
    }
    return {
        "raw_report": raw_report,
        "direct_affected_tables": get_direct_affected_tables(raw_report),
        "indirect_affected_items": get_indirect_affected_items(raw_report),
        "layer_relationships": get_layer_relationships(raw_report),
        "affected_layers": get_affected_layer_items(raw_report),
        "affected_surfaces": get_affected_surface_items(raw_report),
    }
