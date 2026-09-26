"""Unified search aggregator: parallel provider querying, deduplication, and failure isolation."""

import concurrent.futures
import logging
from pathlib import Path
import random
from typing import Callable, Dict, List, Optional, Set
import urllib.parse

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SourceStatus,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider
from wallpaper_engine.core.source_manager import SourceManager

logger = logging.getLogger(__name__)


class SearchAggregator:
    """Aggregates search and featured results across all enabled providers.
    
    Ensures that a failure, timeout, or rate-limit on any single provider
    never crashes or interrupts the global search.
    """

    def __init__(
        self,
        source_manager: SourceManager,
        cache_manager: Optional[Any] = None,
        max_workers: int = 6,
        per_provider_timeout: float = 6.0,
    ) -> None:
        self.source_manager = source_manager
        self.cache_manager = cache_manager
        self.max_workers = max_workers
        self.per_provider_timeout = per_provider_timeout

    def _normalize_url_for_dedup(self, url: str) -> str:
        """Strip query parameters and protocols for reliable deduplication."""
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        # Combine netloc and path, strip trailing slashes
        return f"{parsed.netloc}{parsed.path}".rstrip("/").lower()

    def deduplicate(self, wallpapers: List[Wallpaper]) -> List[Wallpaper]:
        """Deduplicate wallpapers based on canonical image URLs, source URLs, and IDs."""
        seen_keys: Set[str] = set()
        unique_wallpapers: List[Wallpaper] = []

        for wp in wallpapers:
            key_img = self._normalize_url_for_dedup(wp.image_url)
            key_src = self._normalize_url_for_dedup(wp.source_url)
            key_id = f"{wp.provider_id}:{wp.id}"

            # Check if any identifier was seen
            if (key_img and key_img in seen_keys) or (key_src and key_src in seen_keys) or (key_id in seen_keys):
                continue

            if key_img:
                seen_keys.add(key_img)
            if key_src:
                seen_keys.add(key_src)
            seen_keys.add(key_id)
            unique_wallpapers.append(wp)

        return unique_wallpapers

    def apply_filters(self, wallpapers: List[Wallpaper], filters: SearchFilter) -> List[Wallpaper]:
        """Apply global resolution, aspect ratio, and keyword filters."""
        filtered = []
        for wp in wallpapers:
            # Min width / height
            if filters.min_width > 0 and wp.width > 0 and wp.width < filters.min_width:
                continue
            if filters.min_height > 0 and wp.height > 0 and wp.height < filters.min_height:
                continue

            # Aspect ratio
            if filters.aspect_ratio:
                norm_ratio = filters.aspect_ratio.lower().replace("x", ":")
                wp_ratio = wp.aspect_ratio.lower().replace("x", ":")
                if wp.aspect_ratio != "Unknown" and norm_ratio not in wp_ratio:
                    continue

            # Category filter
            if filters.category:
                cat_lower = filters.category.lower()
                if not any(cat_lower in c.lower() for c in wp.categories) and not any(cat_lower in t.lower() for t in wp.tags):
                    continue

            filtered.append(wp)
        return filtered

    def sort_results(self, wallpapers: List[Wallpaper], sorting: str, query: str = "") -> List[Wallpaper]:
        """Sort wallpapers by relevance, resolution, date, or random."""
        query_words = [w.lower() for w in query.split() if w]

        def relevance_score(wp: Wallpaper) -> int:
            score = 0
            title_lower = wp.title.lower()
            desc_lower = wp.description.lower()
            for w in query_words:
                if w in title_lower:
                    score += 5
                if any(w in t.lower() for t in wp.tags):
                    score += 3
                if w in desc_lower:
                    score += 1
            return score

        if sorting == "relevance" and query_words:
            return sorted(wallpapers, key=relevance_score, reverse=True)
        elif sorting == "resolution":
            return sorted(wallpapers, key=lambda wp: wp.width * wp.height, reverse=True)
        elif sorting == "random":
            shuffled = list(wallpapers)
            random.shuffle(shuffled)
            return shuffled
        elif sorting == "newest":
            return sorted(wallpapers, key=lambda wp: wp.created_at or wp.published_at, reverse=True)
        return wallpapers

    def _query_provider(
        self,
        provider: WallpaperProvider,
        action: Callable[[WallpaperProvider], List[Wallpaper]],
    ) -> List[Wallpaper]:
        """Execute a provider query with isolated exception handling."""
        try:
            return action(provider)
        except Exception as exc:
            provider.record_failure(str(exc))
            logger.warning("Provider '%s' failed query: %s", provider.provider_id, exc)
            return []

    def search_progressive(
        self,
        filters: SearchFilter,
        on_results: Callable[[str, List[Wallpaper]], None],
        on_complete: Optional[Callable[[], None]] = None,
        providers: Optional[List[WallpaperProvider]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Execute search progressively across providers without waiting for the slowest.
        
        Delivers results to on_results(provider_id, new_wallpapers) as each provider finishes.
        """
        import time
        import threading

        t0 = time.perf_counter()
        query = filters.query.strip()
        print(f'[SEARCH PERF] query = "{query}"', flush=True)
        print('[SEARCH PERF] search started', flush=True)

        if not query:
            if on_complete:
                on_complete()
            return

        seen_keys: Set[str] = set()
        collected_all: List[Wallpaper] = []
        first_results_displayed = False
        lock = threading.Lock()

        # Tier 1: Check search metadata cache for instant feedback (<15ms)
        cache_key = f"search_q_{query.lower()}_{filters.sorting}_{filters.aspect_ratio}"
        if self.cache_manager:
            cached_meta = self.cache_manager.get_meta(cache_key, max_age_seconds=300)
            if cached_meta and isinstance(cached_meta, list) and len(cached_meta) > 0:
                cached_wallpapers = []
                for item in cached_meta:
                    if isinstance(item, dict):
                        try:
                            cached_wallpapers.append(Wallpaper.from_dict(item))
                        except Exception:
                            pass
                if cached_wallpapers:
                    with lock:
                        for wp in cached_wallpapers:
                            k_img = self._normalize_url_for_dedup(wp.image_url)
                            k_src = self._normalize_url_for_dedup(wp.source_url)
                            k_id = f"{wp.provider_id}:{wp.id}"
                            if k_img: seen_keys.add(k_img)
                            if k_src: seen_keys.add(k_src)
                            seen_keys.add(k_id)
                            collected_all.append(wp)
                        first_results_displayed = True
                    elapsed_cached = (time.perf_counter() - t0) * 1000
                    print(f'[SEARCH PERF] first results displayed (from cache): {elapsed_cached:.1f} ms', flush=True)
                    on_results("cache", cached_wallpapers)

        target_providers = providers if providers is not None else self.source_manager.get_enabled_providers()
        searchable_providers = [
            p for p in target_providers
            if p.supports(Capability.SEARCH) or p.supports(Capability.FEATURED)
        ]

        if not searchable_providers:
            total_time = (time.perf_counter() - t0) * 1000
            print(f'[SEARCH PERF] all providers finished: {total_time:.1f} ms', flush=True)
            print(f'[SEARCH PERF] total: {total_time:.1f} ms', flush=True)
            if on_complete:
                on_complete()
            return

        def query_single_provider(provider: WallpaperProvider):
            nonlocal first_results_displayed
            if is_cancelled and is_cancelled():
                return

            p_start = time.perf_counter()
            print(f'[SEARCH PERF] provider {provider.provider_id} started', flush=True)
            try:
                raw_results = provider.search(filters)
                p_elapsed = (time.perf_counter() - p_start) * 1000
                print(f'[SEARCH PERF] provider {provider.provider_id} finished: {p_elapsed:.1f} ms', flush=True)
            except Exception as exc:
                p_elapsed = (time.perf_counter() - p_start) * 1000
                provider.record_failure(str(exc))
                print(f'[SEARCH PERF] provider {provider.provider_id} finished: {p_elapsed:.1f} ms (failed: {exc})', flush=True)
                logger.warning("Provider '%s' failed query: %s", provider.provider_id, exc)
                return

            if is_cancelled and is_cancelled():
                return

            filtered = self.apply_filters(raw_results, filters)
            if not filtered:
                return

            # Deduplicate progressively against already-delivered results
            with lock:
                if is_cancelled and is_cancelled():
                    return
                unique_batch: List[Wallpaper] = []
                for wp in filtered:
                    k_img = self._normalize_url_for_dedup(wp.image_url)
                    k_src = self._normalize_url_for_dedup(wp.source_url)
                    k_id = f"{wp.provider_id}:{wp.id}"

                    if (k_img and k_img in seen_keys) or (k_src and k_src in seen_keys) or (k_id in seen_keys):
                        continue

                    if k_img: seen_keys.add(k_img)
                    if k_src: seen_keys.add(k_src)
                    seen_keys.add(k_id)
                    unique_batch.append(wp)
                    collected_all.append(wp)

                if unique_batch:
                    if not first_results_displayed:
                        first_results_displayed = True
                        first_elapsed = (time.perf_counter() - t0) * 1000
                        print(f'[SEARCH PERF] first results displayed: {first_elapsed:.1f} ms', flush=True)

                    on_results(provider.provider_id, unique_batch)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_provider = {
                executor.submit(query_single_provider, p): p
                for p in searchable_providers
            }
            # Wait for all providers, timing out if any hangs
            done, not_done = concurrent.futures.wait(
                future_to_provider.keys(),
                timeout=self.per_provider_timeout + 1.0,
            )
            for f in not_done:
                prov = future_to_provider[f]
                prov.record_failure("Provider query timed out")
                print(f'[SEARCH PERF] provider {prov.provider_id} timed out after {self.per_provider_timeout}s', flush=True)

        total_elapsed = (time.perf_counter() - t0) * 1000
        print(f'[SEARCH PERF] all providers finished: {total_elapsed:.1f} ms', flush=True)
        print(f'[SEARCH PERF] total: {total_elapsed:.1f} ms', flush=True)

        # Cache results for rapid future searches
        if self.cache_manager and collected_all:
            try:
                self.cache_manager.set_meta(cache_key, [wp.to_dict() for wp in collected_all[:60]])
            except Exception:
                pass

        if on_complete and not (is_cancelled and is_cancelled()):
            on_complete()

    def search(self, filters: SearchFilter, providers: Optional[List[WallpaperProvider]] = None) -> List[Wallpaper]:
        """Query enabled providers in parallel, merge, deduplicate, filter, and sort."""
        import time

        t0 = time.perf_counter()
        target_providers = providers if providers is not None else self.source_manager.get_enabled_providers()
        searchable_providers = [
            p for p in target_providers
            if p.supports(Capability.SEARCH) or p.supports(Capability.FEATURED)
        ]

        if not searchable_providers:
            return []

        all_results: List[Wallpaper] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_provider = {
                executor.submit(self._query_provider, p, lambda prov: prov.search(filters)): p
                for p in searchable_providers
            }
            for future in concurrent.futures.as_completed(future_to_provider, timeout=self.per_provider_timeout + 2.0):
                provider = future_to_provider[future]
                try:
                    results = future.result()
                    if results:
                        all_results.extend(results)
                except Exception as exc:
                    logger.warning("Error collecting results from '%s': %s", provider.provider_id, exc)

        deduped = self.deduplicate(all_results)
        filtered = self.apply_filters(deduped, filters)
        sorted_results = self.sort_results(filtered, filters.sorting, filters.query)

        # Pagination slice
        page_size = filters.page_size or 24
        start = (filters.page - 1) * page_size
        end = start + page_size
        return sorted_results[start:end]

    def get_featured(self, page: int = 1, providers: Optional[List[WallpaperProvider]] = None) -> List[Wallpaper]:
        """Aggregate featured/curated feeds across all enabled providers."""
        target_providers = providers if providers is not None else self.source_manager.get_enabled_providers()
        featured_providers = [p for p in target_providers if p.supports(Capability.FEATURED)]

        if not featured_providers:
            return []

        all_results: List[Wallpaper] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_provider = {
                executor.submit(self._query_provider, p, lambda prov: prov.get_featured(page=page)): p
                for p in featured_providers
            }
            for future in concurrent.futures.as_completed(future_to_provider, timeout=self.per_provider_timeout + 2.0):
                provider = future_to_provider[future]
                try:
                    results = future.result()
                    if results:
                        all_results.extend(results)
                except Exception as exc:
                    logger.warning("Error collecting featured from '%s': %s", provider.provider_id, exc)

        # Interleave or shuffle results from different providers so the feed is diverse
        deduped = self.deduplicate(all_results)
        # Group by provider to interleave
        by_provider: Dict[str, List[Wallpaper]] = {}
        for wp in deduped:
            by_provider.setdefault(wp.provider_id, []).append(wp)

        interleaved: List[Wallpaper] = []
        max_len = max((len(items) for items in by_provider.values()), default=0)
        for i in range(max_len):
            for pid, items in by_provider.items():
                if i < len(items):
                    interleaved.append(items[i])

        return interleaved

    def get_featured_progressive(
        self,
        page: int = 1,
        providers: Optional[List[WallpaperProvider]] = None,
        on_results: Optional[Callable[[str, List[Wallpaper]], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[Wallpaper]:
        """Aggregate featured feeds with immediate streaming per responding provider."""
        import threading

        target_providers = providers if providers is not None else self.source_manager.get_enabled_providers()
        featured_providers = [p for p in target_providers if p.supports(Capability.FEATURED)]

        print(f"[DISCOVER DEBUG] active providers for initial load: {[p.provider_id for p in featured_providers]}", flush=True)

        if not featured_providers:
            if on_complete:
                on_complete()
            return []

        seen_keys: Set[str] = set()
        all_results: List[Wallpaper] = []
        lock = threading.Lock()

        def query_single_provider(prov: WallpaperProvider):
            if is_cancelled and is_cancelled():
                return
            print(f"[DISCOVER DEBUG] starting provider fetch: {prov.provider_id}", flush=True)
            res = self._query_provider(prov, lambda p: p.get_featured(page=page))
            print(f"[DISCOVER DEBUG] provider finished: {prov.provider_id}, results count: {len(res)}", flush=True)

            if is_cancelled and is_cancelled():
                return

            unique_batch = []
            with lock:
                for wp in res:
                    k_img = self._normalize_url_for_dedup(wp.image_url)
                    k_src = self._normalize_url_for_dedup(wp.source_url)
                    k_id = f"{wp.provider_id}:{wp.id}"
                    if (k_img and k_img in seen_keys) or (k_src and k_src in seen_keys) or (k_id in seen_keys):
                        continue
                    if k_img:
                        seen_keys.add(k_img)
                    if k_src:
                        seen_keys.add(k_src)
                    seen_keys.add(k_id)
                    unique_batch.append(wp)
                    all_results.append(wp)

            if unique_batch and on_results:
                on_results(prov.provider_id, unique_batch)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(query_single_provider, p) for p in featured_providers]
            concurrent.futures.wait(futures, timeout=self.per_provider_timeout + 2.0)

        print(f"[DISCOVER DEBUG] total featured results combined: {len(all_results)}", flush=True)
        if on_complete:
            on_complete()

        return all_results
