"""Tests for progressive search, concurrency, caching, and stale generation cancellation."""

import time
import unittest
from unittest.mock import MagicMock

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import Capability, SearchFilter, Wallpaper
from wallpaper_engine.core.provider_base import WallpaperProvider
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager


class FastProvider(WallpaperProvider):
    def __init__(self, pid: str, wallpapers=None):
        super().__init__()
        self._pid = pid
        self._wallpapers = wallpapers or [
            Wallpaper(id=f"{pid}-1", provider_id=pid, provider_name=pid, title=f"Fast 1", image_url=f"https://example.com/{pid}/1.jpg")
        ]

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def provider_name(self) -> str:
        return self._pid

    @property
    def homepage_url(self) -> str:
        return f"https://example.com/{self._pid}"

    @property
    def capabilities(self) -> Capability:
        return Capability.SEARCH

    def search(self, filters: SearchFilter):
        return list(self._wallpapers)

    def get_featured(self, page: int = 1):
        return []


class SlowProvider(WallpaperProvider):
    def __init__(self, pid: str, delay: float = 0.5):
        super().__init__()
        self._pid = pid
        self._delay = delay

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def provider_name(self) -> str:
        return self._pid

    @property
    def homepage_url(self) -> str:
        return f"https://example.com/{self._pid}"

    @property
    def capabilities(self) -> Capability:
        return Capability.SEARCH

    def search(self, filters: SearchFilter):
        time.sleep(self._delay)
        return [
            Wallpaper(id=f"{self._pid}-1", provider_id=self._pid, provider_name=self._pid, title="Slow 1", image_url=f"https://example.com/{self._pid}/1.jpg")
        ]

    def get_featured(self, page: int = 1):
        return []


class FailingProvider(WallpaperProvider):
    @property
    def provider_id(self) -> str:
        return "failing"

    @property
    def provider_name(self) -> str:
        return "Failing Provider"

    @property
    def homepage_url(self) -> str:
        return "https://example.com/failing"

    @property
    def capabilities(self) -> Capability:
        return Capability.SEARCH

    def search(self, filters: SearchFilter):
        raise ConnectionResetError("Remote server closed connection")

    def get_featured(self, page: int = 1):
        return []


class TestSearchProgressive(unittest.TestCase):
    def setUp(self):
        self.sm = MagicMock(spec=SourceManager)

    def test_progressive_results_fast_before_slow(self):
        """First provider result must be delivered before slow provider completes."""
        fast = FastProvider("fast")
        slow = SlowProvider("slow", delay=0.3)
        self.sm.get_enabled_providers.return_value = [slow, fast]

        aggregator = SearchAggregator(self.sm, per_provider_timeout=2.0)

        received_batches = []
        batch_times = []
        t0 = time.perf_counter()

        def on_results(provider_id, batch):
            received_batches.append((provider_id, batch))
            batch_times.append(time.perf_counter() - t0)

        aggregator.search_progressive(
            SearchFilter(query="test"),
            on_results=on_results,
        )

        self.assertEqual(len(received_batches), 2)
        # Fast should be the first batch received
        self.assertEqual(received_batches[0][0], "fast")
        self.assertLess(batch_times[0], 0.15)  # Fast arrived well under 150ms
        self.assertEqual(received_batches[1][0], "slow")
        self.assertGreaterEqual(batch_times[1], 0.25)  # Slow arrived after delay

    def test_slow_provider_does_not_block_fast_provider(self):
        """A slow provider does not delay faster providers."""
        fast1 = FastProvider("fast1")
        fast2 = FastProvider("fast2")
        slow = SlowProvider("slow", delay=0.4)
        self.sm.get_enabled_providers.return_value = [slow, fast1, fast2]

        aggregator = SearchAggregator(self.sm, per_provider_timeout=2.0)
        received_providers = []

        aggregator.search_progressive(
            SearchFilter(query="test"),
            on_results=lambda pid, batch: received_providers.append(pid),
        )

        self.assertIn("fast1", received_providers[:2])
        self.assertIn("fast2", received_providers[:2])
        self.assertEqual(received_providers[-1], "slow")

    def test_provider_failure_is_isolated(self):
        """Failure in one provider does not prevent or delay results from other providers."""
        failing = FailingProvider()
        fast = FastProvider("fast")
        self.sm.get_enabled_providers.return_value = [failing, fast]

        aggregator = SearchAggregator(self.sm)
        received_batches = []

        aggregator.search_progressive(
            SearchFilter(query="test"),
            on_results=lambda pid, batch: received_batches.append((pid, batch)),
        )

        self.assertEqual(len(received_batches), 1)
        self.assertEqual(received_batches[0][0], "fast")

    def test_search_caching(self):
        """Repeated search serves results immediately from cache."""
        import tempfile
        from pathlib import Path
        temp_dir = Path(tempfile.mkdtemp(prefix="wp_cache_test_"))
        cache_mgr = CacheManager(base_cache_dir=temp_dir / "cache", base_data_dir=temp_dir / "data")

        fast = FastProvider("fast")
        self.sm.get_enabled_providers.return_value = [fast]

        aggregator = SearchAggregator(self.sm, cache_manager=cache_mgr)

        # First search: populates cache
        aggregator.search_progressive(SearchFilter(query="cats"), on_results=lambda pid, b: None)

        # Second search: should hit cache
        cache_hits = []
        aggregator.search_progressive(
            SearchFilter(query="cats"),
            on_results=lambda pid, b: cache_hits.append((pid, b)),
        )

        self.assertTrue(any(pid == "cache" for pid, _ in cache_hits))

    def test_empty_query_returns_immediately_without_calling_providers(self):
        """Empty query does not query providers."""
        mock_prov = MagicMock()
        mock_prov.supports.return_value = True
        self.sm.get_enabled_providers.return_value = [mock_prov]

        aggregator = SearchAggregator(self.sm)
        results = []
        aggregator.search_progressive(SearchFilter(query=""), on_results=lambda pid, b: results.append(b))

        self.assertEqual(len(results), 0)
        mock_prov.search.assert_not_called()

    def test_cancellation_check_halts_processing(self):
        """When is_cancelled returns True, processing stops immediately."""
        slow = SlowProvider("slow", delay=0.2)
        self.sm.get_enabled_providers.return_value = [slow]

        aggregator = SearchAggregator(self.sm)
        results = []

        # Immediately cancelled
        aggregator.search_progressive(
            SearchFilter(query="test"),
            on_results=lambda pid, b: results.append(b),
            is_cancelled=lambda: True,
        )

        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
