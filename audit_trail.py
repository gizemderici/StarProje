from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_audit_event(
    *,
    event_type: str,
    scenario_name: str,
    status: str,
    source: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": utc_now_iso(),
        "event_type": event_type,
        "scenario_name": scenario_name,
        "status": status,
        "source": source,
        "message": message,
        "details": details or {},
    }


def build_audit_paths(
    *,
    root_dir: Path | str,
    scenario_name: str,
    scenario_dir: Path | str | None = None,
) -> list[Path]:
    root = Path(root_dir)
    paths = [root / "_audit" / f"{scenario_name}__events.jsonl"]
    if scenario_dir is not None:
        paths.append(Path(scenario_dir) / "audit_events.jsonl")
    return paths


def write_audit_event(paths: list[Path], event: dict[str, Any]) -> None:
    if not paths:
        return

    payload = json.dumps(event, ensure_ascii=False)
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(payload + "\n")
        except OSError:
            # Telemetry should never break scenario execution.
            continue
