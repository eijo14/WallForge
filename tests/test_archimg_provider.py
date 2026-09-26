"""Exhaustive tests for ArchimgProvider verifying contract, search, parsing, and licensing."""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter, SourceStatus
from wallpaper_engine.providers.archimg import ArchimgProvider


class TestArchimgProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_archimg_test_"))
        self.cache_mgr = CacheManager(
            base_cache_dir=self.temp_dir / "cache",
            base_data_dir=self.temp_dir / "data",
        )
        self.provider = ArchimgProvider(cache_manager=self.cache_mgr)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("urllib.request.urlopen")
    def test_normalized_attributes_and_licensing(self, mock_urlopen):
        """Test normalized provider ID, image URLs, and strict 'Unknown' license representation."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"001.jpg\n"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        featured = self.provider.get_featured(page=1)
        self.assertEqual(len(featured), 1)
        wp = featured[0]

        # Normalized metadata
        self.assertEqual(wp.id, "archimg-001")
        self.assertEqual(wp.provider_id, "archimg")
        self.assertEqual(wp.provider_name, "ArchImg")
        self.assertEqual(wp.title, "Arch Linux Rice #001")
        self.assertEqual(wp.image_url, "https://archimg.cc/assets/001.jpg")
        self.assertEqual(wp.thumbnail_url, "https://archimg.cc/assets/001.jpg")
        self.assertEqual(wp.source_url, "https://archimg.cc/")

        # Strict license requirement: must be 'Unknown' when unverified
        self.assertEqual(wp.license, "Unknown")
        self.assertEqual(wp.license_url, "https://archimg.cc/")
        self.assertFalse(wp.attribution_required)
        self.assertEqual(wp.author, "ArchImg Community")

    @patch("urllib.request.urlopen")
    def test_supported_extensions(self, mock_urlopen):
        """Test that JPG, JPEG, PNG, and WebP entries are parsed in lowercase and uppercase."""
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b"001.jpg\n"
            b"002.JPEG\n"
            b"003.png\n"
            b"004.WebP\n"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        featured = self.provider.get_featured(page=1)
        self.assertEqual(len(featured), 4)
        ids = [wp.id for wp in featured]
        self.assertEqual(ids, ["archimg-001", "archimg-002", "archimg-003", "archimg-004"])

    @patch("urllib.request.urlopen")
    def test_invalid_entries_ignored(self, mock_urlopen):
        """Test that non-image entries and manifests are ignored."""
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b"image-manifest.txt\n"
            b"index.html\n"
            b"notes.txt\n"
            b"preview.gif\n"
            b"005.jpg\n"
            b"vector.svg\n"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        featured = self.provider.get_featured(page=1)
        self.assertEqual(len(featured), 1)
        self.assertEqual(featured[0].id, "archimg-005")

    @patch("urllib.request.urlopen")
    def test_malformed_manifest_lines(self, mock_urlopen):
        """Test resilience against empty lines, spaces, and messy line endings."""
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b"   \n"
            b"\n"
            b"  010.jpg   \r\n"
            b"\t\n"
            b"011.png\n\n"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        featured = self.provider.get_featured(page=1)
        self.assertEqual(len(featured), 2)
        self.assertEqual(featured[0].id, "archimg-010")
        self.assertEqual(featured[1].id, "archimg-011")

    @patch("urllib.request.urlopen")
    def test_empty_manifest(self, mock_urlopen):
        """Test that empty manifests raise an exception and mark status DEGRADED."""
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(ValueError):
            self.provider.get_featured(page=1)

        self.assertEqual(self.provider.status, SourceStatus.DEGRADED)
        self.assertIn("empty", self.provider.last_error.lower())

    @patch("urllib.request.urlopen")
    def test_search_by_id_filename_and_tags(self, mock_urlopen):
        """Test searching by filename/ID, provider tags, and non-matching query."""
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b"001.jpg\n"
            b"019.png\n"
            b"150.jpg\n"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # 1. Search by filename / numerical ID
        res_id = self.provider.search(SearchFilter(query="019"))
        self.assertEqual(len(res_id), 1)
        self.assertEqual(res_id[0].id, "archimg-019")

        # 2. Search by provider-derived tag (e.g. 'hyprland')
        res_tag = self.provider.search(SearchFilter(query="hyprland"))
        self.assertEqual(len(res_tag), 3)

        # 3. Search by provider category (e.g. 'rice')
        res_cat = self.provider.search(SearchFilter(query="rice"))
        self.assertEqual(len(res_cat), 3)

        # 4. Search with no matching query
        res_none = self.provider.search(SearchFilter(query="nonexistent_cyberpunk_query"))
        self.assertEqual(len(res_none), 0)

    @patch("urllib.request.urlopen")
    def test_network_failure_with_cached_manifest_fallback(self, mock_urlopen):
        """Test that network failures fall back gracefully to locally cached manifest."""
        # Prime cache with known manifest
        self.cache_mgr.set_meta("archimg_manifest", ["007.jpg", "008.png"])

        # Simulate network failure (e.g. offline / DNS failure)
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        # Provider should recover using cached manifest
        featured = self.provider.get_featured(page=1)
        self.assertEqual(len(featured), 2)
        self.assertEqual(featured[0].id, "archimg-007")
        self.assertEqual(featured[1].id, "archimg-008")

    @patch("urllib.request.urlopen")
    def test_get_single_wallpaper(self, mock_urlopen):
        """Test fetching single wallpaper by ID."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"001.jpg\n002.png\n"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        wp = self.provider.get_wallpaper("archimg-002")
        self.assertIsNotNone(wp)
        self.assertEqual(wp.id, "archimg-002")

        missing = self.provider.get_wallpaper("archimg-999")
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
