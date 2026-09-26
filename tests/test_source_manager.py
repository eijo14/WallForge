"""Tests for SourceManager: registration, enabling/disabling, config persistence."""

from pathlib import Path
import shutil
import tempfile
import unittest

from wallpaper_engine.core.models import Capability, SourceStatus, Wallpaper
from wallpaper_engine.core.provider_base import WallpaperProvider
from wallpaper_engine.core.source_manager import SourceManager


class DummyProvider(WallpaperProvider):
    @property
    def provider_id(self) -> str:
        return "dummy"

    @property
    def provider_name(self) -> str:
        return "Dummy Provider"

    @property
    def homepage_url(self) -> str:
        return "https://dummy.example.com"

    @property
    def capabilities(self) -> Capability:
        return Capability.FEATURED

    def get_featured(self, page: int = 1):
        return [
            Wallpaper(
                id="dummy-1",
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                title="Dummy 1",
            )
        ]


class TestSourceManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_sm_test_"))
        self.sm = SourceManager(config_dir=self.temp_dir)
        self.provider = DummyProvider()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_registration_and_enable(self):
        self.sm.register_provider(self.provider)
        self.assertEqual(len(self.sm.get_all_providers()), 1)
        self.assertEqual(len(self.sm.get_enabled_providers()), 1)
        self.assertTrue(self.sm.is_enabled("dummy"))
        self.assertEqual(self.provider.status, SourceStatus.ONLINE)

        # Disable
        self.sm.set_enabled("dummy", False)
        self.assertFalse(self.sm.is_enabled("dummy"))
        self.assertEqual(len(self.sm.get_enabled_providers()), 0)
        self.assertEqual(self.provider.status, SourceStatus.DISABLED)

    def test_config_persistence(self):
        self.sm.register_provider(self.provider)
        self.sm.save_provider_config("dummy", {"api_key": "secret123"})

        # Reload with a new instance pointing to same dir
        sm2 = SourceManager(config_dir=self.temp_dir)
        prov2 = DummyProvider()
        sm2.register_provider(prov2)
        self.assertEqual(prov2.config.get("api_key"), "secret123")

    def test_provider_test_connection(self):
        self.sm.register_provider(self.provider)
        ok, msg = self.sm.test_provider("dummy")
        self.assertTrue(ok)
        self.assertIn("Successfully fetched", msg)


if __name__ == "__main__":
    unittest.main()
