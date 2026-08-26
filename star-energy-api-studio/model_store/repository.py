from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModelRecord:
    model_id: str
    name: str
    osm_path: Path
    weather_path: Path | None
    archived_results_path: Path | None = None
    # Faz 1 onarimi sonrasi taban kosusu; arsiv kosularindan ayridir.
    baseline_results_path: Path | None = None
    study_path: Path | None = None

    def public_dict(self) -> dict[str, object]:
        """Return metadata without exposing local filesystem paths to API clients."""
        return {
            "id": self.model_id,
            "name": self.name,
            "osm_filename": self.osm_path.name,
            "weather_available": self.weather_path is not None,
            "archived_results_available": self.archived_results_path is not None,
            "baseline_results_available": self.baseline_results_path is not None,
            "study_results_available": self.study_path is not None,
        }


class ModelRepository:
    """Resolve public model IDs to allow-listed files inside the project."""

    def __init__(self, project_root: Path, registry_path: Path | None = None) -> None:
        self.project_root = project_root.resolve()
        self.registry_path = registry_path or self.project_root / "data/model_store/models.json"
        self.imported_root = (self.project_root / "data/model_store/imported").resolve()
        self._records = self._load_registry()

    def _resolve_project_file(self, relative_path: str, suffix: str) -> Path:
        path = (self.project_root / relative_path).resolve()
        if not path.is_relative_to(self.project_root):
            raise ValueError(f"Model deposu yolu proje dışına çıkamaz: {relative_path}")
        if path.suffix.casefold() != suffix:
            raise ValueError(f"Beklenen {suffix} dosyası: {relative_path}")
        if not path.is_file():
            raise FileNotFoundError(f"Model deposu girdisi bulunamadı: {path}")
        return path

    def _resolve_project_directory(self, relative_path: str) -> Path:
        path = (self.project_root / relative_path).resolve()
        if not path.is_relative_to(self.project_root):
            raise ValueError(f"Model deposu yolu proje dışına çıkamaz: {relative_path}")
        if not path.is_dir():
            raise FileNotFoundError(f"Model deposu klasörü bulunamadı: {path}")
        return path

    def _read_registry(self) -> dict[str, object]:
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _write_registry(self, payload: dict[str, object]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.registry_path)

    def _load_registry(self) -> dict[str, ModelRecord]:
        payload = self._read_registry()
        records: dict[str, ModelRecord] = {}
        for model_id, item in payload.get("models", {}).items():
            osm_path = self._resolve_project_file(str(item["osm"]), ".osm")
            weather_value = item.get("weather")
            weather_path = (
                self._resolve_project_file(str(weather_value), ".epw")
                if weather_value
                else None
            )
            archived_value = item.get("archived_results")
            archived_results_path = (
                self._resolve_project_directory(str(archived_value))
                if archived_value
                else None
            )
            baseline_value = item.get("baseline_results")
            baseline_results_path = (
                self._resolve_project_directory(str(baseline_value))
                if baseline_value
                else None
            )
            study_value = item.get("study")
            study_path = (
                self._resolve_project_directory(str(study_value))
                if study_value
                else None
            )
            records[model_id] = ModelRecord(
                model_id=model_id,
                name=str(item["name"]),
                osm_path=osm_path,
                weather_path=weather_path,
                archived_results_path=archived_results_path,
                baseline_results_path=baseline_results_path,
                study_path=study_path,
            )
        if not records:
            raise ValueError("Model deposunda kayıtlı model bulunamadı.")
        return records

    def list(self) -> list[ModelRecord]:
        return sorted(self._records.values(), key=lambda item: item.name.casefold())

    def get(self, model_id: str) -> ModelRecord:
        try:
            return self._records[model_id]
        except KeyError as exc:
            raise KeyError(f"Bilinmeyen model kimliği: {model_id}") from exc

    def register_upload(
        self,
        *,
        name: str,
        osm_bytes: bytes,
        weather_bytes: bytes | None = None,
    ) -> ModelRecord:
        """Store uploaded content under a generated ID; never accept client paths."""

        clean_name = " ".join(name.split()).strip()
        if not clean_name:
            raise ValueError("Model adı boş olamaz.")
        if len(clean_name) > 120:
            raise ValueError("Model adı en fazla 120 karakter olabilir.")
        if not osm_bytes:
            raise ValueError("OSM dosyası boş olamaz.")

        slug = re.sub(r"[^a-z0-9]+", "-", clean_name.casefold()).strip("-")
        slug = slug[:40] or "model"
        model_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        target = (self.imported_root / model_id).resolve()
        if not target.is_relative_to(self.imported_root):
            raise ValueError("Geçersiz model depo hedefi.")

        target.mkdir(parents=True, exist_ok=False)
        osm_path = target / "model.osm"
        weather_path = target / "weather.epw" if weather_bytes is not None else None
        try:
            osm_path.write_bytes(osm_bytes)
            if weather_path is not None:
                weather_path.write_bytes(weather_bytes)

            payload = self._read_registry()
            models = payload.setdefault("models", {})
            if not isinstance(models, dict):
                raise ValueError("Model deposu kayıt biçimi geçersiz.")
            entry: dict[str, str] = {
                "name": clean_name,
                "osm": osm_path.relative_to(self.project_root).as_posix(),
            }
            if weather_path is not None:
                entry["weather"] = weather_path.relative_to(self.project_root).as_posix()
            models[model_id] = entry
            self._write_registry(payload)
            self._records = self._load_registry()
            return self.get(model_id)
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def remove_uploaded(self, model_id: str) -> None:
        """Roll back one generated import after OpenStudio validation fails."""

        record = self.get(model_id)
        target = record.osm_path.parent.resolve()
        if not target.is_relative_to(self.imported_root):
            raise ValueError("Yalnızca API ile yüklenen modeller kaldırılabilir.")

        payload = self._read_registry()
        models = payload.get("models", {})
        if isinstance(models, dict):
            models.pop(model_id, None)
        self._write_registry(payload)
        self._records = self._load_registry()
        shutil.rmtree(target)
