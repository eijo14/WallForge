"""Tests for SearchAggregator: parallel querying, deduplication, and failure isolation."""

import unittest
from unittest.mock import MagicMock

from wallpaper_engine.core.models import Capability, SearchFilter, Wallpaper
from wallpaper_engine.core.provider_base import WallpaperProvider
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager


class MockProvider(WallpaperProvider):
    def __init__(self, pid: str, wallpapers=None, should_fail=False):
        super().__init__()
        self._pid = pid
        self._wallpapers = wallpapers or []
        self._should_fail = should_fail

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def provider_name(self) -> str:
        return f"Mock {self._pid}"

    @property
    def homepage_url(self) -> str:
        return f"https://{self._pid}.example.com"

    @property
    def capabilities(self) -> Capability:
        return Capability.SEARCH | Capability.FEATURED

    def search(self, filters: SearchFilter):
        if self._should_fail:
            raise RuntimeError(f"Simulated network crash in {self._pid}")
        return list(self._wallpapers)

    def get_featured(self, page: int = 1):
        if self._should_fail:
            raise RuntimeError(f"Simulated network crash in {self._pid}")
        return list(self._wallpapers)


class TestSearchAggregator(unittest.TestCase):
    def setUp(self):
        self.sm = MagicMock(spec=SourceManager)

    def test_deduplication(self):
        aggregator = SearchAggregator(self.sm)
        wp1 = Wallpaper(
            id="1",
            provider_id="p1",
            provider_name="P1",
            title="Duplicate 1",
            image_url="https://cdn.example.com/images/cat.jpg?token=abc",
            source_url="https://example.com/w/1",
        )
        wp2 = Wallpaper(
            id="2",
            provider_id="p2",
            provider_name="P2",
            title="Duplicate 2",
            image_url="https://cdn.example.com/images/cat.jpg?token=xyz",  # Same canonical path
            source_url="https://example.com/w/1",
        )
        wp3 = Wallpaper(
            id="3",
            provider_id="p1",
            provider_name="P1",
            title="Unique 3",
            image_url="https://cdn.example.com/images/dog.jpg",
            source_url="https://example.com/w/3",
        )

        deduped = aggregator.deduplicate([wp1, wp2, wp3])
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0].id, "1")
        self.assertEqual(deduped[1].id, "3")

    def test_failure_isolation(self):
        """A failure in Provider A must never crash or prevent results from Provider B."""
        p_failing = MockProvider("fail_prov", should_fail=True)
        wp_good = Wallpaper(
            id="good-1",
            provider_id="good_prov",
            provider_name="Good",
            title="Success Wallpaper",
            image_url="https://example.com/good.jpg",
        )
        p_good = MockProvider("good_prov", wallpapers=[wp_good])

        self.sm.get_enabled_providers.return_value = [p_failing, p_good]
        aggregator = SearchAggregator(self.sm)

        results = aggregator.search(SearchFilter(query="test"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "good-1")

    def test_resolution_and_aspect_filtering(self):
        aggregator = SearchAggregator(self.sm)
        wp_4k = Wallpaper(
            id="4k",
            provider_id="p1",
            provider_name="P1",
            title="4K Ultrawide",
            image_url="https://example.com/4k.jpg",
            width=3840,
            height=1600,
            aspect_ratio="21:9",
        )
        wp_1080 = Wallpaper(
            id="1080",
            provider_id="p1",
            provider_name="P1",
            title="1080p Standard",
            image_url="https://example.com/1080.jpg",
            width=1920,
            height=1080,
            aspect_ratio="16:9",
        )

        # Filter for 4K width (>= 3840)
        filtered_res = aggregator.apply_filters([wp_4k, wp_1080], SearchFilter(min_width=3840))
        self.assertEqual(len(filtered_res), 1)
        self.assertEqual(filtered_res[0].id, "4k")

        # Filter for 21:9 aspect ratio
        filtered_ratio = aggregator.apply_filters([wp_4k, wp_1080], SearchFilter(aspect_ratio="21:9"))
        self.assertEqual(len(filtered_ratio), 1)
        self.assertEqual(filtered_ratio[0].id, "4k")

    def test_sorting(self):
        aggregator = SearchAggregator(self.sm)
        wp_lo = Wallpaper(
            id="lo",
            provider_id="p1",
            provider_name="P1",
            title="Cyberpunk Street",
            image_url="http://lo",
            width=1920,
            height=1080,
        )
        wp_hi = Wallpaper(
            id="hi",
            provider_id="p1",
            provider_name="P1",
            title="Neon City",
            image_url="http://hi",
            width=3840,
            height=2160,
        )

        # Sort by resolution
        sorted_res = aggregator.sort_results([wp_lo, wp_hi], sorting="resolution")
        self.assertEqual(sorted_res[0].id, "hi")

        # Sort by relevance to 'Cyberpunk'
        sorted_rel = aggregator.sort_results([wp_hi, wp_lo], sorting="relevance", query="Cyberpunk")
        self.assertEqual(sorted_rel[0].id, "lo")


if __name__ == "__main__":
    unittest.main()
