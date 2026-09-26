"""Tests for NasaApodProvider with mocked APOD responses."""

import json
import unittest
from unittest.mock import MagicMock, patch

from wallpaper_engine.providers.nasa import NasaApodProvider


class TestNasaProvider(unittest.TestCase):
    def setUp(self):
        self.provider = NasaApodProvider()

    @patch("urllib.request.urlopen")
    def test_apod_image_and_video_handling(self, mock_urlopen):
        mock_payload = [
            {
                "date": "2026-09-26",
                "media_type": "image",
                "title": "Cosmic Nebula",
                "explanation": "A colorful cloud of gas and dust.",
                "url": "https://apod.nasa.gov/sample_1024.jpg",
                "hdurl": "https://apod.nasa.gov/sample_4k.jpg",
                "copyright": "Jane Astronomer",
            },
            {
                "date": "2026-09-25",
                "media_type": "video",  # Must be ignored
                "title": "Rocket Launch Video",
                "url": "https://youtube.com/watch?v=123",
            },
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        featured = self.provider.get_featured(page=1)
        # Only 1 image returned (video skipped)
        self.assertEqual(len(featured), 1)
        wp = featured[0]
        self.assertEqual(wp.id, "nasa-2026-09-26")
        self.assertEqual(wp.title, "Cosmic Nebula")
        self.assertEqual(wp.image_url, "https://apod.nasa.gov/sample_4k.jpg")
        self.assertEqual(wp.author, "Jane Astronomer")
        self.assertEqual(wp.license, "Copyright Artist")
        self.assertTrue(wp.attribution_required)


if __name__ == "__main__":
    unittest.main()
