"""Tests for WikimediaProvider using mocked Action API responses."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.providers.wikimedia import WikimediaProvider


class TestWikimediaProvider(unittest.TestCase):
    def setUp(self):
        self.provider = WikimediaProvider()

    @patch("urllib.request.urlopen")
    def test_featured_and_normalization(self, mock_urlopen):
        mock_payload = {
            "query": {
                "pages": {
                    "101": {
                        "pageid": 101,
                        "title": "File:Misty_Fjord_Norway.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/misty.jpg",
                                "size": 8421000,
                                "width": 5120,
                                "height": 2880,
                                "mime": "image/jpeg",
                                "extmetadata": {
                                    "Artist": {"value": "<a href='...'>Erik Landscape</a>"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                                    "ImageDescription": {"value": "Scenic fjord in western Norway."},
                                },
                            }
                        ],
                    }
                }
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        results = self.provider.get_featured(page=1)
        self.assertEqual(len(results), 1)
        wp = results[0]
        self.assertEqual(wp.id, "wikimedia-101")
        self.assertEqual(wp.title, "Misty Fjord Norway.jpg")
        self.assertEqual(wp.author, "Erik Landscape")  # HTML stripped cleanly
        self.assertEqual(wp.license, "CC BY-SA 4.0")
        self.assertTrue(wp.attribution_required)
        self.assertEqual(wp.width, 5120)
        self.assertEqual(wp.height, 2880)
        self.assertEqual(wp.aspect_ratio, "16:9")


if __name__ == "__main__":
    unittest.main()
