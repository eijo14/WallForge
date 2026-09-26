"""Tests for BingProvider using mocked daily feed responses."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.providers.bing import BingProvider


class TestBingProvider(unittest.TestCase):
    def setUp(self):
        self.provider = BingProvider()

    @patch("urllib.request.urlopen")
    def test_feed_and_normalization(self, mock_urlopen):
        mock_payload = {
            "images": [
                {
                    "startdate": "20260926",
                    "fullstartdate": "202609260700",
                    "url": "/th?id=OHR.Sample_1920x1080.jpg",
                    "urlbase": "/th?id=OHR.Sample",
                    "copyright": "Misty Alpine Lake (© John Doe/Getty Images)",
                    "copyrightlink": "https://www.bing.com/search?q=Alps",
                    "title": "Quiet Waters",
                    "hsh": "abc123hash",
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Prefer UHD is True by default
        featured = self.provider.get_featured(page=1)
        self.assertEqual(len(featured), 1)
        wp = featured[0]
        self.assertEqual(wp.id, "bing-abc123hash")
        self.assertEqual(wp.title, "Quiet Waters")
        self.assertEqual(wp.author, "John Doe/Getty Images")
        self.assertEqual(wp.license, "Copyrighted (Personal Desktop Use Only)")
        self.assertTrue(wp.attribution_required)
        self.assertTrue(wp.image_url.endswith("_UHD.jpg"))
        self.assertEqual(wp.width, 3840)
        self.assertEqual(wp.height, 2160)


if __name__ == "__main__":
    unittest.main()
