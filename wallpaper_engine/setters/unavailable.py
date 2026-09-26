"""Fallback wallpaper backend when no supported desktop environment or OS setter is available."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class UnavailableWallpaperSetter(WallpaperSetter):
    """Graceful degradation backend when no native wallpaper setter is available.
    
    Allows browsing, previewing, downloading, and favoriting wallpapers
    without crashing or breaking the application.
    """

    @property
    def name(self) -> str:
        return "Unavailable (No supported wallpaper setter)"

    @property
    def backend_id(self) -> str:
        return "unavailable"

    @property
    def platform_name(self) -> str:
        return "Unavailable"

    def is_available(self) -> bool:
        """Always returns False as this is a fallback placeholder."""
        return False

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        return False, "Wallpaper setting is unavailable on this system."

    def clear_wallpaper(self) -> Tuple[bool, str]:
        return False, "Wallpaper setting is unavailable on this system."

    def get_current_wallpaper(self) -> Optional[str]:
        return None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "can_set": False,
            "can_clear": False,
            "can_get": False,
            "multi_monitor": False,
            "reason": "No supported wallpaper backend available on this system.",
        }
