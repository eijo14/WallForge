"""Tests for key-based providers (Unsplash, Pexels, Pixabay) with and without API keys."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.core.models import SearchFilter, SourceStatus
from wallpaper_engine.providers.pexels import PexelsProvider
from wallpaper_engine.providers.pixabay import PixabayProvider
from wallpaper_engine.providers.unsplash import UnsplashProvider


class TestKeyedProviders(unittest.TestCase):
    def test_unsplash_not_configured_when_no_key(self):
        prov = UnsplashProvider()
        prov.configure({})
        self.assertEqual(prov.status, SourceStatus.NOT_CONFIGURED)
        self.assertEqual(prov.get_featured(page=1), [])
        self.assertEqual(prov.search(SearchFilter(query="trees")), [])

    @patch("urllib.request.urlopen")
    def test_unsplash_configured_success(self, mock_urlopen):
        mock_payload = [
            {
                "id": "photo-1",
                "description": "Misty Forest",
                "urls": {"full": "https://images.unsplash.com/forest.jpg"},
                "user": {"name": "Forest Photographer"},
                "width": 3840,
                "height": 2160,
            }
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        prov = UnsplashProvider()
        prov.configure({"access_key": "test_client_id"})
        self.assertEqual(prov.status, SourceStatus.ONLINE)

        wallpapers = prov.get_featured(page=1)
        self.assertEqual(len(wallpapers), 1)
        self.assertEqual(wallpapers[0].id, "unsplash-photo-1")
        self.assertEqual(wallpapers[0].license, "Unsplash License")
        self.assertTrue(wallpapers[0].attribution_required)

    def test_pexels_not_configured_when_no_key(self):
        prov = PexelsProvider()
        prov.configure({})
        self.assertEqual(prov.status, SourceStatus.NOT_CONFIGURED)
        self.assertEqual(prov.get_featured(page=1), [])

    @patch("urllib.request.urlopen")
    def test_pexels_configured_success(self, mock_urlopen):
        mock_payload = {
            "photos": [
                {
                    "id": 12345,
                    "alt": "Ocean Horizon",
                    "photographer": "Ocean Explorer",
                    "src": {"original": "https://images.pexels.com/ocean.jpg"},
                    "width": 3840,
                    "height": 2160,
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        prov = PexelsProvider()
        prov.configure({"api_key": "test_pexels_key"})
        self.assertEqual(prov.status, SourceStatus.ONLINE)

        wallpapers = prov.get_featured(page=1)
        self.assertEqual(len(wallpapers), 1)
        self.assertEqual(wallpapers[0].id, "pexels-12345")
        self.assertEqual(wallpapers[0].license, "Pexels License")

    def test_pixabay_not_configured_when_no_key(self):
        prov = PixabayProvider()
        prov.configure({})
        self.assertEqual(prov.status, SourceStatus.NOT_CONFIGURED)
        self.assertEqual(prov.get_featured(page=1), [])

    @patch("urllib.request.urlopen")
    def test_pixabay_configured_success(self, mock_urlopen):
        mock_payload = {
            "hits": [
                {
                    "id": 999,
                    "user": "Vector Artist",
                    "largeImageURL": "https://pixabay.com/vector.jpg",
                    "imageWidth": 3840,
                    "imageHeight": 2160,
                    "tags": "aurora, northern lights",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        prov = PixabayProvider()
        prov.configure({"api_key": "test_pixabay_key"})
        self.assertEqual(prov.status, SourceStatus.ONLINE)

        wallpapers = prov.get_featured(page=1)
        self.assertEqual(len(wallpapers), 1)
        self.assertEqual(wallpapers[0].id, "pixabay-999")
        self.assertEqual(wallpapers[0].license, "Pixabay License")


if __name__ == "__main__":
    unittest.main()
