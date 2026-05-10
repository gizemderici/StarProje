import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen


class UiPlaywrightSmokeTests(unittest.TestCase):
    @staticmethod
    def _read_env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @classmethod
    def setUpClass(cls) -> None:
        if not cls._read_env_bool("RUN_UI_PLAYWRIGHT", default=False):
            raise unittest.SkipTest(
                "Set RUN_UI_PLAYWRIGHT to a truthy value (1/true/yes/on) to run Playwright UI smoke tests."
            )

        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception as error:  # pragma: no cover - depends on local setup
            raise unittest.SkipTest(f"Playwright is not available: {error}")

        cls.base_url = os.getenv("UI_BASE_URL", "http://127.0.0.1:8080")
        cls.artifact_dir = Path(os.getenv("UI_TEST_ARTIFACT_DIR", "tests/artifacts/ui"))
        cls.artifact_dir.mkdir(parents=True, exist_ok=True)
        if cls._read_env_bool("CLEAN_UI_ERROR_ARTIFACTS", default=True):
            cls._cleanup_error_artifacts()
        cls._server_process = None

        if cls._read_env_bool("START_UI_FOR_TESTS", default=False):
            cls._server_process = subprocess.Popen(
                [sys.executable, "nicegui_csv_viewer.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        cls._wait_for_server(cls.base_url, timeout_seconds=40)

        from playwright.sync_api import sync_playwright

        cls._playwright_manager = sync_playwright()
        cls._playwright = cls._playwright_manager.start()
        cls._browser = cls._playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        browser = getattr(cls, "_browser", None)
        if browser is not None:
            browser.close()

        playwright = getattr(cls, "_playwright", None)
        if playwright is not None:
            playwright.stop()

        process = getattr(cls, "_server_process", None)
        if process is not None:
            process.terminate()
            process.wait(timeout=10)

    @staticmethod
    def _wait_for_server(base_url: str, timeout_seconds: int = 30) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                with urlopen(base_url, timeout=3) as response:  # nosec B310
                    if response.status < 500:
                        return
            except URLError:
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
        raise unittest.SkipTest(f"UI server is not reachable at {base_url}")

    @classmethod
    def _cleanup_error_artifacts(cls) -> None:
        # Keep success artifacts, remove stale failure diagnostics from previous runs.
        for artifact_path in cls.artifact_dir.glob("*_error.*"):
            try:
                artifact_path.unlink()
            except OSError:
                pass

    def _save_screenshot(self, page, name: str) -> None:
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name)
        target = self.artifact_dir / f"{safe_name}.png"
        page.screenshot(path=str(target), full_page=True)

    def _save_page_dump(self, page, name: str) -> None:
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in name)
        target = self.artifact_dir / f"{safe_name}.html"
        target.write_text(page.content(), encoding="utf-8")

    def test_main_page_and_parameter_navigation(self) -> None:
        page = self._browser.new_page()
        try:
            page.goto(self.base_url, wait_until="networkidle")
            self.assertIn("CSV", page.content())

            page.get_by_role("button", name="Parametre Secimi").click()
            page.wait_for_url("**/parameters**")

            self.assertIn("Parametre Secimi", page.content())
            self.assertIn("Kategori Listesi", page.content())
            self.assertIn("Parametre Listesi", page.content())
            self._save_screenshot(page, "main_page_and_parameter_navigation")
        except Exception:
            self._save_screenshot(page, "main_page_and_parameter_navigation_error")
            self._save_page_dump(page, "main_page_and_parameter_navigation_error")
            raise
        finally:
            page.close()

    def test_parameter_selection_smoke_flow(self) -> None:
        page = self._browser.new_page()
        try:
            page.goto(f"{self.base_url}/parameters", wait_until="networkidle")

            page.get_by_label("Kategori Ara").fill("material")
            page.get_by_role("button", name="Materials 8").click()
            page.wait_for_timeout(200)

            search_box = page.get_by_placeholder(
                "Ad, aciklama, alan adi veya veri seti icinde ara"
            )
            search_box.fill("thickness")
            page.wait_for_timeout(200)

            page.get_by_role("button", name="Sec").first.click()
            page.wait_for_timeout(200)

            self.assertIn("1 parametre secildi", page.content().lower())
            self.assertIn("Hazir Durumu", page.content())
            self._save_screenshot(page, "parameter_selection_smoke_flow")
        except Exception:
            self._save_screenshot(page, "parameter_selection_smoke_flow_error")
            self._save_page_dump(page, "parameter_selection_smoke_flow_error")
            raise
        finally:
            page.close()

    def test_parameter_remove_flow(self) -> None:
        page = self._browser.new_page()
        try:
            page.goto(f"{self.base_url}/parameters", wait_until="networkidle")

            page.get_by_role("button", name="Tum Kategoriler 20").click()
            page.wait_for_timeout(200)

            page.get_by_placeholder(
                "Ad, aciklama, alan adi veya veri seti icinde ara"
            ).fill("thickness")
            page.wait_for_timeout(200)

            page.get_by_role("button", name="Sec").first.click()
            page.wait_for_timeout(200)
            self.assertIn("1 parametre secildi", page.content().lower())

            page.get_by_role("button", name="Kaldir").first.click()
            page.wait_for_timeout(200)
            self.assertIn("0 parametre secildi", page.content().lower())
            self._save_screenshot(page, "parameter_remove_flow")
        except Exception:
            self._save_screenshot(page, "parameter_remove_flow_error")
            self._save_page_dump(page, "parameter_remove_flow_error")
            raise
        finally:
            page.close()

    def test_invalid_new_value_shows_warning(self) -> None:
        page = self._browser.new_page()
        try:
            page.goto(f"{self.base_url}/parameters", wait_until="networkidle")

            page.get_by_role("button", name="Tum Kategoriler 20").click()
            page.wait_for_timeout(200)

            page.get_by_placeholder(
                "Ad, aciklama, alan adi veya veri seti icinde ara"
            ).fill("thickness")
            page.wait_for_timeout(200)
            page.get_by_role("button", name="Sec").first.click()
            page.wait_for_timeout(200)

            page.get_by_label("Yeni Deger").first.fill("")
            page.wait_for_timeout(250)

            self.assertIn("Yeni deger bos birakilamaz.", page.content())
            self._save_screenshot(page, "invalid_new_value_warning")
        except Exception:
            self._save_screenshot(page, "invalid_new_value_warning_error")
            self._save_page_dump(page, "invalid_new_value_warning_error")
            raise
        finally:
            page.close()

    def test_main_tabs_analytics_and_cost_panels_visible(self) -> None:
        page = self._browser.new_page()
        try:
            page.goto(self.base_url, wait_until="networkidle")

            page.get_by_role("tab", name="Analiz").click()
            page.wait_for_timeout(200)
            self.assertIn("Senaryo Analizi", page.content())
            self.assertIn("Bolum 7 - Aciklama ve Yorum Paneli", page.content())

            page.get_by_role("tab", name="Maliyet").click()
            page.wait_for_timeout(200)
            self.assertIn("Maliyet Analizi", page.content())
            self.assertIn("Old annual cost, new annual cost ve savings karsilastirmasi", page.content())
            self._save_screenshot(page, "analytics_and_cost_panels_visible")
        except Exception:
            self._save_screenshot(page, "analytics_and_cost_panels_visible_error")
            self._save_page_dump(page, "analytics_and_cost_panels_visible_error")
            raise
        finally:
            page.close()

    def test_parameter_flow_requires_record_and_new_value_before_run(self) -> None:
        page = self._browser.new_page()
        try:
            page.goto(f"{self.base_url}/parameters", wait_until="networkidle")

            page.get_by_role("button", name="Tum Kategoriler 20").click()
            page.wait_for_timeout(200)
            page.get_by_placeholder(
                "Ad, aciklama, alan adi veya veri seti icinde ara"
            ).fill("thickness")
            page.wait_for_timeout(200)
            page.get_by_role("button", name="Sec").first.click()
            page.wait_for_timeout(250)

            self.assertIn("Sonraki Adimlar", page.content())
            self.assertIn("Eksik", page.content())
            self.assertIn("Bu parametre icin once bir kayit secin.", page.content())
            self.assertIn("Yeni deger girilmeden senaryo olusturulamaz.", page.content())

            run_button = page.get_by_role("button", name="Senaryoyu Calistir")
            self.assertFalse(run_button.is_enabled())
            self._save_screenshot(page, "parameter_flow_requires_record_and_new_value_before_run")
        except Exception:
            self._save_screenshot(page, "parameter_flow_requires_record_and_new_value_before_run_error")
            self._save_page_dump(page, "parameter_flow_requires_record_and_new_value_before_run_error")
            raise
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
