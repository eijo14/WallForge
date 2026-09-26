"""Cross-platform wallpaper backend detector and resolver."""

import os
from pathlib import Path
import platform
import shutil
from typing import Dict, List, Optional

from wallpaper_engine.setters.base import WallpaperSetter
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


def detect_environment_name() -> str:
    """Detect human-readable name of current OS and desktop environment."""
    sys_name = platform.system()
    if sys_name == "Windows":
        release = platform.release()
        return f"Windows {release}" if release else "Windows"
    elif sys_name == "Darwin":
        mac_ver = platform.mac_ver()[0]
        return f"macOS {mac_ver}" if mac_ver else "macOS"

    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "Hyprland"
    if os.environ.get("SWAYSOCK"):
        return "Sway"

    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    if "GNOME" in xdg:
        return "GNOME"
    elif "KDE" in xdg or "PLASMA" in xdg:
        return "KDE Plasma"
    elif "XFCE" in xdg:
        return "XFCE"
    elif "CINNAMON" in xdg:
        return "Cinnamon"
    elif "MATE" in xdg:
        return "MATE"
    elif "SWAY" in xdg:
        return "Sway"
    elif "HYPRLAND" in xdg:
        return "Hyprland"

    session = os.environ.get("DESKTOP_SESSION", "")
    if session:
        return session.capitalize()

    return "Generic Linux (X11 / Wayland)"


def get_all_registered_setters() -> List[WallpaperSetter]:
    """Return an instance of every known setter."""
    return [
        WindowsWallpaperSetter(),
        MacOSWallpaperSetter(),
        HyprlandWallpaperSetter(),
        GNOMEWallpaperSetter(),
        KDEPlasmaWallpaperSetter(),
        XFCEWallpaperSetter(),
        CinnamonWallpaperSetter(),
        MATEWallpaperSetter(),
        SwayWallpaperSetter(),
        GenericLinuxWallpaperSetter(),
        UnavailableWallpaperSetter(),
    ]


def get_available_setters() -> List[WallpaperSetter]:
    """Return all wallpaper setters supported and installed on this system."""
    return [s for s in get_all_registered_setters() if s.is_available()]


def get_best_setter(preferred_id: Optional[str] = None) -> WallpaperSetter:
    """Detect and return primary wallpaper setter, or preferred if available."""
    sys_name = platform.system()
    available = get_available_setters()

    if preferred_id:
        for s in available:
            if getattr(s, "backend_id", s.name.lower()) == preferred_id:
                return s

    # 1. Windows platform
    if sys_name == "Windows":
        win = WindowsWallpaperSetter()
        if win.is_available():
            return win

    # 2. macOS platform
    if sys_name == "Darwin":
        mac = MacOSWallpaperSetter()
        if mac.is_available():
            return mac

    # 3. Linux / BSD: check desktop environment priority
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        hypr = HyprlandWallpaperSetter()
        if hypr.is_available():
            return hypr

    if os.environ.get("SWAYSOCK"):
        sway = SwayWallpaperSetter()
        if sway.is_available():
            return sway

    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    if "GNOME" in xdg:
        gnome = GNOMEWallpaperSetter()
        if gnome.is_available():
            return gnome
    elif "KDE" in xdg or "PLASMA" in xdg:
        kde = KDEPlasmaWallpaperSetter()
        if kde.is_available():
            return kde
    elif "XFCE" in xdg:
        xfce = XFCEWallpaperSetter()
        if xfce.is_available():
            return xfce
    elif "CINNAMON" in xdg:
        cinnamon = CinnamonWallpaperSetter()
        if cinnamon.is_available():
            return cinnamon
    elif "MATE" in xdg:
        mate = MATEWallpaperSetter()
        if mate.is_available():
            return mate

    # If any other available setter was detected
    if available:
        return available[0]

    # Check generic linux as final attempt if on Linux and tools exist
    if sys_name not in ("Windows", "Darwin"):
        gen = GenericLinuxWallpaperSetter()
        if gen.is_available():
            return gen

    # Graceful degradation fallback
    return UnavailableWallpaperSetter()
