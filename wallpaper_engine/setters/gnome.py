"""GNOME / GSettings desktop wallpaper setter backend."""

import os
from pathlib import Path
import shutil
import subprocess
from typing import Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class GNOMEWallpaperSetter(WallpaperSetter):
    """Applies wallpapers using GNOME's gsettings (supports light and dark themes)."""

    @property
    def name(self) -> str:
        return "GNOME (gsettings)"

    @property
    def backend_id(self) -> str:
        return "gnome"

    def is_available(self) -> bool:
        has_gsettings = bool(shutil.which("gsettings"))
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        is_gnome = "gnome" in desktop or "cinnamon" in desktop or "unity" in desktop
        return has_gsettings and is_gnome

    def apply_wallpaper(self, image_path: Path, mode: str = "fill") -> Tuple[bool, str]:
        if not image_path.is_file():
            return False, f"Image file not found: {image_path}"

        uri = image_path.resolve().as_uri()
        try:
            # Set both light and dark picture-uri
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                check=True,
                capture_output=True,
                timeout=5,
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
                check=False,
                capture_output=True,
                timeout=5,
            )
            self.active_wallpaper = image_path
            return True, "Successfully applied wallpaper via gsettings."
        except subprocess.TimeoutExpired:
            return False, "gsettings command timed out."
        except Exception as exc:
            return False, f"gsettings error: {exc}"
