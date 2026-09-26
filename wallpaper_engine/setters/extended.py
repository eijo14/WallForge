"""XFCE, Cinnamon, MATE, and Sway wallpaper setters."""

import os
from pathlib import Path
import shutil
import subprocess
from typing import List, Optional, Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class XFCEWallpaperSetter(WallpaperSetter):
    """XFCE desktop wallpaper setter using xfconf-query."""

    @property
    def name(self) -> str:
        return "XFCE (xfconf-query)"

    @property
    def backend_id(self) -> str:
        return "xfce"

    def is_available(self) -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        return "XFCE" in desktop and shutil.which("xfconf-query") is not None

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        try:
            # Query all backdrop image-path properties
            cmd = ["xfconf-query", "-c", "xfce4-desktop", "-l"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            props = [line.strip() for line in proc.stdout.splitlines() if "last-image" in line or "image-path" in line]

            if not props:
                props = ["/backdrop/screen0/monitor0/workspace0/last-image"]

            for prop in props:
                subprocess.run(
                    ["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", str(path)],
                    check=False,
                    timeout=5,
                )
            self.active_wallpaper = path
            return True, "Wallpaper applied via xfconf-query."
        except Exception as exc:
            return False, f"XFCE error: {exc}"


class CinnamonWallpaperSetter(WallpaperSetter):
    """Cinnamon desktop wallpaper setter using gsettings."""

    @property
    def name(self) -> str:
        return "Cinnamon (gsettings)"

    @property
    def backend_id(self) -> str:
        return "cinnamon"

    def is_available(self) -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        return "CINNAMON" in desktop and shutil.which("gsettings") is not None

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        try:
            uri = path.as_uri()
            subprocess.run(
                ["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri],
                check=True,
                timeout=5,
            )
            self.active_wallpaper = path
            return True, "Wallpaper applied via Cinnamon gsettings."
        except Exception as exc:
            return False, f"Cinnamon error: {exc}"


class MATEWallpaperSetter(WallpaperSetter):
    """MATE desktop wallpaper setter using gsettings."""

    @property
    def name(self) -> str:
        return "MATE (gsettings)"

    @property
    def backend_id(self) -> str:
        return "mate"

    def is_available(self) -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        return "MATE" in desktop and shutil.which("gsettings") is not None

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        try:
            subprocess.run(
                ["gsettings", "set", "org.mate.background", "picture-filename", str(path)],
                check=True,
                timeout=5,
            )
            self.active_wallpaper = path
            return True, "Wallpaper applied via MATE gsettings."
        except Exception as exc:
            return False, f"MATE error: {exc}"


class SwayWallpaperSetter(WallpaperSetter):
    """Sway / wlroots wallpaper setter using swaybg or swaymsg."""

    @property
    def name(self) -> str:
        return "Sway (swaymsg / swaybg)"

    @property
    def backend_id(self) -> str:
        return "sway"

    def is_available(self) -> bool:
        return "SWAYSOCK" in os.environ and (shutil.which("swaymsg") is not None or shutil.which("swaybg") is not None)

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        target_output = monitor if monitor and monitor != "All Monitors" else "*"
        if shutil.which("swaymsg"):
            try:
                # swaymsg output * bg /path/to/img fill
                res = subprocess.run(
                    ["swaymsg", "output", target_output, "bg", str(path), mode],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    self.active_wallpaper = path
                    return True, "Wallpaper applied via swaymsg."
            except Exception:
                pass

        if shutil.which("swaybg"):
            try:
                # Spawn swaybg in background
                subprocess.Popen(["swaybg", "-i", str(path), "-m", mode])
                self.active_wallpaper = path
                return True, "Wallpaper applied via swaybg."
            except Exception as exc:
                return False, f"Swaybg error: {exc}"

        return False, "Failed to apply wallpaper in Sway."
