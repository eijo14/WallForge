"""Tests for core models and capability flags."""

import unittest
from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SourceStatus,
    Wallpaper,
)


class TestModels(unittest.TestCase):
    def test_capability_flags(self):
        caps = Capability.SEARCH | Capability.FEATURED | Capability.DIRECT_IMAGE_URL
        self.assertTrue(bool(caps & Capability.SEARCH))
        self.assertTrue(bool(caps & Capability.FEATURED))
        self.assertFalse(bool(caps & Capability.CATEGORIES))

    def test_wallpaper_resolution_helpers(self):
        wp = Wallpaper(
            id="test-1",
            provider_id="test",
            provider_name="Test Provider",
            title="Sample 4K",
            thumbnail_url="http://example.com/thumb.jpg",
            image_url="http://example.com/full.jpg",
            source_url="http://example.com",
            width=3840,
            height=2160,
            aspect_ratio="16:9",
        )
        self.assertEqual(wp.resolution_str, "3840x2160")
        self.assertTrue(wp.is_4k_or_more)
        self.assertTrue(wp.is_1440p_or_more)
        self.assertTrue(wp.is_1080p_or_more)

        wp_hd = Wallpaper(
            id="test-2",
            provider_id="test",
            provider_name="Test Provider",
            title="Sample 1080p",
            width=1920,
            height=1080,
        )
        self.assertEqual(wp_hd.resolution_str, "1920x1080")
        self.assertFalse(wp_hd.is_4k_or_more)
        self.assertTrue(wp_hd.is_1080p_or_more)

        wp_unknown = Wallpaper(
            id="test-3",
            provider_id="test",
            provider_name="Test Provider",
            title="Unknown Res",
            width=0,
            height=0,
        )
        self.assertEqual(wp_unknown.resolution_str, "Unknown")
        self.assertFalse(wp_unknown.is_4k_or_more)

    def test_search_filter_defaults(self):
        sf = SearchFilter(query="nature")
        self.assertEqual(sf.query, "nature")
        self.assertEqual(sf.page, 1)
        self.assertEqual(sf.page_size, 24)
        self.assertEqual(sf.sorting, "relevance")


if __name__ == "__main__":
    unittest.main()
