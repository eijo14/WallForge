"""Automatic wallpaper rotation background service with offline-first recovery."""

from collections import deque
import logging
from pathlib import Path
import random
import threading
import time
from typing import Deque, List, Optional, Set

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter, Wallpaper
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.setters.base import WallpaperSetter

logger = logging.getLogger(__name__)


class RotationService:
    """Manages automatic periodic wallpaper rotation in a background thread."""

    INTERVAL_MAP = {
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "6h": 21600,
        "daily": 86400,
    }

    def __init__(
        self,
        source_manager: SourceManager,
        search_aggregator: SearchAggregator,
        cache_manager: CacheManager,
        wallpaper_setter: WallpaperSetter,
        favorites_file: Optional[Path] = None,
    ) -> None:
        self.source_manager = source_manager
        self.search_aggregator = search_aggregator
        self.cache_manager = cache_manager
        self.wallpaper_setter = wallpaper_setter
        paths = getattr(cache_manager, "paths", None)
        self.favorites_file = favorites_file or (paths.favorites_file if paths else (cache_manager.data_dir / "favorites.json"))

        self.interval_seconds = 1800  # Default 30m
        self.source_pool = "all"      # 'all', 'archimg', 'wallhaven', 'downloaded', 'favorites'
        self.history: Deque[str] = deque(maxlen=40)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def set_interval(self, interval_key: str) -> None:
        """Set rotation interval (e.g. '5m', '15m', '30m', '1h', '6h', 'daily')."""
        self.interval_seconds = self.INTERVAL_MAP.get(interval_key.lower(), 1800)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the rotation background service."""
        with self._lock:
            if self.is_running():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="WallpaperRotation")
            self._thread.start()
            logger.info("Wallpaper rotation service started (interval=%ds, pool=%s)", self.interval_seconds, self.source_pool)

    def stop(self) -> None:
        """Stop the rotation background service."""
        with self._lock:
            if not self.is_running():
                return
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=2.0)
            self._thread = None
            logger.info("Wallpaper rotation service stopped")

    def _get_offline_pool(self) -> List[Path]:
        """Collect all downloaded local wallpaper files."""
        files = []
        if self.cache_manager.wallpapers_dir.is_dir():
            for p in self.cache_manager.wallpapers_dir.iterdir():
                if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    files.append(p)
        return files

    def _pick_next_wallpaper(self) -> Optional[Wallpaper]:
        """Select a candidate wallpaper based on the configured source pool."""
        candidates: List[Wallpaper] = []

        if self.source_pool == "downloaded":
            local_files = self._get_offline_pool()
            if local_files:
                p = random.choice(local_files)
                return Wallpaper(
                    id=f"local-{p.stem}",
                    provider_id="local",
                    provider_name="Local Wallpapers",
                    title=p.stem,
                    image_url=p.as_uri(),
                )
            return None

        # Fetch candidate wallpapers from provider(s)
        try:
            if self.source_pool == "all":
                candidates = self.search_aggregator.get_featured(page=1)
            else:
                prov = self.source_manager.get_provider(self.source_pool)
                if prov and prov.status != SourceStatus.DISABLED:
                    candidates = prov.get_featured(page=1)
        except Exception as exc:
            logger.warning("Failed to fetch rotation candidates from online providers: %s", exc)
            candidates = []

        # Filter out recently applied wallpapers to avoid immediate repeats
        fresh = [wp for wp in candidates if wp.id not in self.history]
        pool = fresh if fresh else candidates

        if pool:
            return random.choice(pool)
        return None

    def rotate_now(self) -> bool:
        """Perform a single wallpaper rotation cycle immediately."""
        if not self.wallpaper_setter.is_available():
            logger.warning("Wallpaper rotation skipped: setter is unavailable.")
            return False
        candidate = self._pick_next_wallpaper()

        # Offline fallback: if no candidate could be fetched, try offline files
        local_path: Optional[Path] = None
        if not candidate:
            logger.info("No online wallpaper candidate available. Falling back to offline pool.")
            offline_files = self._get_offline_pool()
            if offline_files:
                local_path = random.choice(offline_files)
            else:
                logger.warning("No local or remote wallpapers available for rotation.")
                return False
        else:
            # If candidate is a local file URI
            if candidate.image_url.startswith("file://"):
                local_path = Path(candidate.image_url[7:])
            else:
                # Download full wallpaper
                ok, path, msg = self.cache_manager.download_wallpaper(candidate.image_url)
                if ok and path:
                    local_path = path
                    self.history.append(candidate.id)
                else:
                    logger.warning("Failed to download rotation wallpaper: %s", msg)
                    # Try offline fallback
                    offline_files = self._get_offline_pool()
                    if offline_files:
                        local_path = random.choice(offline_files)

        if local_path and local_path.is_file():
            success, msg = self.wallpaper_setter.apply_wallpaper(local_path)
            if success:
                logger.info("Rotated wallpaper to: %s", local_path.name)
                return True
            else:
                logger.error("Failed to apply rotated wallpaper: %s", msg)
                return False
        return False

    def _run_loop(self) -> None:
        """Main rotation loop."""
        while not self._stop_event.is_set():
            # Wait for interval or until stopped
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            self.rotate_now()
