from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*"
)

from fastapi.testclient import TestClient

from api_layer.server import api
from engine.sql_results import load_run
from model_store import ModelRepository
from services import OpenStudioService


ROOT = Path(__file__).resolve().parents[1]


class BaselineResultsTests(unittest.TestCase):
    """Genel Bakis sekmesi eski arsiv kosusunu gostermemelidir.

    ResultsRepository klasor adlarini "eps_{kalinlik}cm" desenine bagliydi,
    bu yuzden Faz 1 onarimi sonrasi taban kosusu arayuze hic ulasmiyor ve
    ekranda eski modelin sonuclari (1941,6 GJ) gorunuyordu.
    """

    def test_baseline_is_read_from_a_directory_outside_the_eps_pattern(self) -> None:
        scenario = load_run(ROOT / "data/baseline_v1")
        # Taban kosusu bir EPS senaryosu degildir; kalinlik anahtari tasimaz.
        self.assertIsNone(scenario.thickness_cm)
        self.assertEqual(scenario.run_status, "Success")
        # Faz 1'in kazanimi: sifir ciddi hata.
        self.assertEqual(scenario.severe_errors, 0)

    def test_baseline_endpoint_does_not_return_the_archived_run(self) -> None:
        client = TestClient(api)
        baseline = client.get(
            "/api/v1/models/main-building/baseline-results"
        ).json()["baseline"]
        archive = client.get(
            "/api/v1/models/main-building/archived-results"
        ).json()["scenarios"]["5"]

        self.assertNotAlmostEqual(
            baseline["site_energy_gj"], archive["site_energy_gj"], places=1
        )
        self.assertAlmostEqual(baseline["site_energy_gj"], 1920.00, places=1)
        self.assertAlmostEqual(baseline["eui_mj_m2"], 452.17, places=1)
        # Yerel dosya yollari istemciye sizmamalidir.
        self.assertNotIn("sql_path", baseline)

    def test_model_without_a_baseline_run_reports_404(self) -> None:
        response = TestClient(api).get(
            "/api/v1/models/legacy-eps-5cm/baseline-results"
        )
        self.assertEqual(response.status_code, 404)


class ModelRepositoryTests(unittest.TestCase):
    def test_repository_returns_public_ids_without_paths(self) -> None:
        record = ModelRepository(ROOT).get("main-building")
        public = record.public_dict()
        self.assertEqual(public["id"], "main-building")
        self.assertNotIn("osm_path", public)
        self.assertNotIn("weather_path", public)
        self.assertTrue(public["archived_results_available"])
        self.assertTrue(public["baseline_results_available"])

    def test_uploaded_model_gets_generated_id_and_stays_inside_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            registry = project / "data/model_store/models.json"
            seed = project / "data/input/seed.osm"
            seed.parent.mkdir(parents=True)
            registry.parent.mkdir(parents=True)
            seed.write_text("OS:Version,3.11.0;", encoding="utf-8")
            registry.write_text(
                '{"models":{"seed":{"name":"Seed","osm":"data/input/seed.osm"}}}',
                encoding="utf-8",
            )
            repository = ModelRepository(project)
            record = repository.register_upload(
                name="Yeni Ofis",
                osm_bytes=b"OS:Version,3.11.0;",
            )
            target = record.osm_path.parent
            self.assertTrue(record.model_id.startswith("yeni-ofis-"))
            self.assertTrue(target.is_relative_to(repository.imported_root))
            self.assertTrue(record.osm_path.is_file())
            repository.remove_uploaded(record.model_id)
            self.assertFalse(target.exists())


class OpenStudioApiServiceTests(unittest.TestCase):
    def test_official_sdk_reads_model(self) -> None:
        repository = ModelRepository(ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            service = OpenStudioService(ROOT, cache_root=Path(temporary))
            if not service.status()["installed"]:
                self.skipTest("OpenStudio CLI bu bilgisayarda kurulu değil.")
            payload = service.inspect_model(repository.get("main-building"))

        self.assertEqual(payload["source"], "openstudio-sdk")
        self.assertEqual(payload["spaces"], 127)
        self.assertEqual(payload["thermal_zones"], 8)
        self.assertEqual(payload["surfaces"], 1310)
        self.assertEqual(len(payload["zones"]), 8)
        self.assertEqual(len(payload["constructions"]), 22)
        self.assertNotIn("osm_path", payload["model"])

        construction = next(
            item for item in payload["constructions"] if item["name"] == "duvr_std_eps"
        )
        self.assertEqual(len(construction["layers"]), 6)
        self.assertEqual(construction["surface_count"], 5)
        self.assertGreater(construction["u_value_w_m2k"], 0)


class HttpApiTests(unittest.TestCase):
    def test_health_and_model_endpoints(self) -> None:
        with TestClient(api) as client:
            health = client.get("/api/v1/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")

            response = client.get("/api/v1/models/main-building")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["source"], "openstudio-sdk")
            self.assertEqual(payload["model"]["id"], "main-building")
            self.assertNotIn("osm_path", payload["model"])

            archived = client.get("/api/v1/models/main-building/archived-results")
            self.assertEqual(archived.status_code, 200)
            self.assertEqual(archived.json()["source"], "energyplus-sql-service")
            self.assertNotIn("sql_path", archived.json()["scenarios"]["5"])

            study = client.get("/api/v1/models/star-baseline/study-results")
            self.assertEqual(study.status_code, 200)
            self.assertEqual(len(study.json()["scenarios"]), 20)

            quick = client.post(
                "/api/v1/models/main-building/quick-study",
                json={"thicknesses_cm": [5, 10, 15], "conductivity_w_mk": 0.039},
            )
            self.assertEqual(quick.status_code, 200)
            self.assertEqual(len(quick.json()["results"]), 3)

    def test_parameter_catalog_lists_every_decision_variable(self) -> None:
        with TestClient(api) as client:
            response = client.get("/api/v1/parameters")
            self.assertEqual(response.status_code, 200)
            parameters = response.json()["parameters"]

        keys = {item["key"] for item in parameters}
        self.assertIn("window_construction", keys)
        self.assertIn("chiller_cop", keys)
        self.assertIn("eps_thickness_cm", keys)

        window = next(item for item in parameters if item["key"] == "window_construction")
        self.assertEqual(window["type"], "categorical")
        self.assertEqual(len(window["choices"]), 7)

        cop = next(item for item in parameters if item["key"] == "chiller_cop")
        self.assertEqual(cop["type"], "continuous")
        self.assertEqual(cop["baseline"], 5.5)

    def test_scenario_payload_rejects_unknown_and_out_of_range_values(self) -> None:
        with TestClient(api) as client:
            unknown = client.post(
                "/api/v1/models/main-building/workflows",
                json={"scenarios": [{"bilinmeyen": 1}]},
            )
            self.assertEqual(unknown.status_code, 422)

            out_of_range = client.post(
                "/api/v1/models/main-building/workflows",
                json={"scenarios": [{"chiller_cop": 99}]},
            )
            self.assertEqual(out_of_range.status_code, 422)

    def test_nicegui_has_no_direct_osm_sql_or_study_reader(self) -> None:
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("ResultsRepository(", source)
        self.assertNotIn("StarStudy(", source)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("Path(__file__)", source)


if __name__ == "__main__":
    unittest.main()
