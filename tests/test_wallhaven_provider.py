"""Tests for WallhavenProvider with mocked API v1 responses."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.core.models import SearchFilter
from wallpaper_engine.providers.wallhaven import WallhavenProvider


class TestWallhavenProvider(unittest.TestCase):
    def setUp(self):
        self.provider = WallhavenProvider()

    @patch("urllib.request.urlopen")
    def test_search_and_normalization(self, mock_urlopen):
        mock_payload = {
            "data": [
                {
                    "id": "w5x99p",
                    "url": "https://wallhaven.cc/w/w5x99p",
                    "category": "anime",
                    "purity": "sfw",
                    "dimension_x": 3840,
                    "dimension_y": 2160,
                    "resolution": "3840x2160",
                    "ratio": "1.78",
                    "file_size": 5242880,
                    "path": "https://w.wallhaven.cc/full/w5/wallhaven-w5x99p.jpg",
                    "thumbs": {
                        "large": "https://th.wallhaven.cc/lg/w5/w5x99p.jpg",
                        "small": "https://th.wallhaven.cc/small/w5/w5x99p.jpg",
                    },
                    "source": "https://example.com/artist",
                    "created_at": "2026-09-01 12:00:00",
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        results = self.provider.search(SearchFilter(query="cyberpunk", min_width=3840, min_height=2160))
        self.assertEqual(len(results), 1)
        wp = results[0]
        self.assertEqual(wp.id, "wallhaven-w5x99p")
        self.assertEqual(wp.width, 3840)
        self.assertEqual(wp.height, 2160)
        self.assertEqual(wp.aspect_ratio, "16:9")
        self.assertEqual(wp.license, "Unknown")
        self.assertEqual(wp.license_url, "https://example.com/artist")
        self.assertTrue(wp.attribution_required)
        self.assertEqual(wp.categories, ["Anime"])


if __name__ == "__main__":
    unittest.main()
