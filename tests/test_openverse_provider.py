"""Tests for OpenverseProvider using mocked API responses."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.core.models import SearchFilter
from wallpaper_engine.providers.openverse import OpenverseProvider


class TestOpenverseProvider(unittest.TestCase):
    def setUp(self):
        self.provider = OpenverseProvider()

    @patch("urllib.request.urlopen")
    def test_search_and_normalization(self, mock_urlopen):
        mock_payload = {
            "results": [
                {
                    "id": "abc-123",
                    "title": "Autumn Path",
                    "creator": "Jane Photographer",
                    "license": "by",
                    "license_version": "2.0",
                    "license_url": "https://creativecommons.org/licenses/by/2.0/",
                    "url": "https://images.example.com/autumn.jpg",
                    "thumbnail": "https://images.example.com/autumn_thumb.jpg",
                    "foreign_landing_url": "https://example.com/photo/123",
                    "width": 3840,
                    "height": 2160,
                    "tags": [{"name": "autumn"}, {"name": "trees"}],
                    "attribution": "'Autumn Path' by Jane Photographer is licensed under CC BY 2.0.",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        results = self.provider.search(SearchFilter(query="autumn"))
        self.assertEqual(len(results), 1)
        wp = results[0]
        self.assertEqual(wp.id, "openverse-abc-123")
        self.assertEqual(wp.author, "Jane Photographer")
        self.assertEqual(wp.license, "CC BY 2.0")
        self.assertTrue(wp.attribution_required)
        self.assertEqual(wp.width, 3840)
        self.assertEqual(wp.height, 2160)
        self.assertEqual(wp.aspect_ratio, "16:9")


if __name__ == "__main__":
    unittest.main()
