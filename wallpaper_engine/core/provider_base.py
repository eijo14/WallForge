"""Abstract base interface for all wallpaper providers."""

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, List, Optional, Tuple

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    SourceStatus,
    Wallpaper,
)


class WallpaperProvider(ABC):
    """Abstract Base Class for wallpaper providers.
    
    Every provider must be self-contained and independently removable.
    The core application only communicates through this interface.
    """

    def __init__(self, cache_manager=None) -> None:
        self.cache_manager = cache_manager
        self.status = SourceStatus.ONLINE
        self.last_error: str = ""
        self.last_success_time: float = 0.0
        self.config: Dict[str, Any] = {}

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique machine-readable identifier (e.g., 'archimg', 'wallhaven')."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable display name (e.g., 'ArchImg', 'Wallhaven')."""
        pass

    @property
    @abstractmethod
    def homepage_url(self) -> str:
        """Public website homepage URL."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Capability:
        """Bitmask of capabilities supported by this provider."""
        pass

    def supports(self, capability: Capability) -> bool:
        """Check if provider supports a specific capability."""
        return bool(self.capabilities & capability)

    def get_settings_schema(self) -> List[SettingField]:
        """Return provider-owned configuration settings schema."""
        return []

    def configure(self, config: Dict[str, Any]) -> None:
        """Update provider-specific configuration."""
        self.config = config

    @abstractmethod
    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        """Fetch featured / trending / curated wallpapers."""
        pass

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        """Search wallpapers matching the given criteria.
        
        Default implementation returns empty list if SEARCH is not supported.
        """
        return []

    def get_categories(self) -> List[str]:
        """Return list of categories supported by this provider."""
        return []

    def get_wallpaper(self, wallpaper_id: str) -> Optional[Wallpaper]:
        """Fetch a single wallpaper by its ID."""
        return None

    def get_download_url(self, wallpaper: Wallpaper) -> str:
        """Return direct high-resolution image download URL."""
        return wallpaper.image_url

    def test_connection(self) -> Tuple[bool, str]:
        """Test provider connectivity and return (success, message)."""
        try:
            results = self.get_featured(page=1)
            if results:
                self.record_success()
                return True, f"Successfully fetched {len(results)} items."
            return True, "Connection successful (0 items returned)."
        except Exception as exc:
            self.record_failure(str(exc))
            return False, str(exc)

    def record_success(self) -> None:
        """Mark provider as healthy following a successful request."""
        self.status = SourceStatus.ONLINE
        self.last_error = ""
        self.last_success_time = time.time()

    def record_failure(self, error_message: str) -> None:
        """Mark provider status following a failure."""
        self.status = SourceStatus.DEGRADED
        self.last_error = error_message
