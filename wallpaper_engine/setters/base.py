"""Abstract base class for desktop wallpaper setters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class WallpaperSetter(ABC):
    """Abstract interface for desktop wallpaper setting backends."""

    def __init__(self) -> None:
        self.active_wallpaper: Optional[Path] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the setter backend."""
        pass

    @property
    def backend_id(self) -> str:
        """Unique identifier for the backend (e.g. 'windows', 'macos', 'hyprland', 'gnome')."""
        return self.name.lower().split()[0]

    @property
    def platform_name(self) -> str:
        """Operating system / platform name this backend targets."""
        return "Linux"

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is supported and installed on current system."""
        pass

    def is_supported(self) -> bool:
        """Alias for is_available() conforming to WallpaperBackend specification."""
        return self.is_available()

    @abstractmethod
    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        """Apply the specified local image file to the desktop background.
        
        Returns (success: bool, message: str).
        """
        pass

    def set_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        """Conforming to WallpaperBackend specification."""
        return self.apply_wallpaper(image_path, mode, monitor)

    def clear_wallpaper(self) -> Tuple[bool, str]:
        """Reset or clear desktop wallpaper."""
        self.active_wallpaper = None
        return True, "Wallpaper cleared or reset."

    def get_current_wallpaper(self) -> Optional[str]:
        """Return the currently applied wallpaper path as string, if known."""
        return str(self.active_wallpaper) if self.active_wallpaper else None

    def get_active_wallpaper(self) -> Optional[Path]:
        """Return the currently applied wallpaper path as Path object, if known."""
        return self.active_wallpaper

    def capabilities(self) -> Dict[str, Any]:
        """Return capability metadata for this wallpaper backend."""
        return {
            "can_set": self.is_available(),
            "can_clear": True,
            "can_get": self.active_wallpaper is not None,
            "multi_monitor": False,
        }
