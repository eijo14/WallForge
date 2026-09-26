"""Tests for GitHubWallsProvider using mocked Git Tree responses."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.core.models import SearchFilter
from wallpaper_engine.providers.github_walls import GitHubWallsProvider


class TestGitHubWallsProvider(unittest.TestCase):
    def setUp(self):
        self.provider = GitHubWallsProvider()

    @patch("urllib.request.urlopen")
    def test_tree_parsing_and_normalization(self, mock_urlopen):
        mock_payload = {
            "tree": [
                {"path": "images/mountain-sunset-minimalist.jpg"},
                {"path": "images/calm-night-flat.png"},
                {"path": "README.md"},  # Ignored
                {"path": "images/preview.gif"},  # Ignored
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        results = self.provider.get_featured(page=1)
        self.assertEqual(len(results), 2)
        wp1 = results[0]
        self.assertEqual(wp1.provider_id, "github_minimal")
        self.assertEqual(wp1.title, "Mountain Sunset Minimalist")
        self.assertEqual(wp1.license, "Open Source / Community")
        self.assertFalse(wp1.attribution_required)
        self.assertIn("minimalist", wp1.tags)
        self.assertTrue(wp1.image_url.startswith("https://raw.githubusercontent.com/"))

    @patch("urllib.request.urlopen")
    def test_search(self, mock_urlopen):
        mock_payload = {
            "tree": [
                {"path": "images/mountain-sunset.jpg"},
                {"path": "images/space-station.png"},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        results = self.provider.search(SearchFilter(query="mountain"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Mountain Sunset")


if __name__ == "__main__":
    unittest.main()
