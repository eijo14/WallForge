"""Desktop wallpaper setting backends for Linux, Windows, and macOS."""

from wallpaper_engine.setters.base import WallpaperSetter
from wallpaper_engine.setters.detector import (
    detect_environment_name,
    get_all_registered_setters,
    get_available_setters,
    get_best_setter,
)
from wallpaper_engine.setters.extended import (
    CinnamonWallpaperSetter,
    MATEWallpaperSetter,
    SwayWallpaperSetter,
    XFCEWallpaperSetter,
)
from wallpaper_engine.setters.generic import GenericLinuxWallpaperSetter
from wallpaper_engine.setters.gnome import GNOMEWallpaperSetter
from wallpaper_engine.setters.hyprland import HyprlandWallpaperSetter
from wallpaper_engine.setters.kde import KDEPlasmaWallpaperSetter
from wallpaper_engine.setters.macos import MacOSWallpaperSetter
from wallpaper_engine.setters.unavailable import UnavailableWallpaperSetter
from wallpaper_engine.setters.windows import WindowsWallpaperSetter

__all__ = [
    "WallpaperSetter",
    "WindowsWallpaperSetter",
    "MacOSWallpaperSetter",
    "HyprlandWallpaperSetter",
    "GNOMEWallpaperSetter",
    "KDEPlasmaWallpaperSetter",
    "XFCEWallpaperSetter",
    "CinnamonWallpaperSetter",
    "MATEWallpaperSetter",
    "SwayWallpaperSetter",
    "GenericLinuxWallpaperSetter",
    "UnavailableWallpaperSetter",
    "detect_environment_name",
    "get_all_registered_setters",
    "get_available_setters",
    "get_best_setter",
]
