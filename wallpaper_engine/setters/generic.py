"""Generic Linux wallpaper setter using feh, swww, swaybg, or nitrogen."""

from pathlib import Path
import shutil
import subprocess
from typing import Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class GenericLinuxWallpaperSetter(WallpaperSetter):
    """Fallback wallpaper setter supporting swww, swaybg, feh, and nitrogen."""

    @property
    def name(self) -> str:
        return "Generic Linux (swww/feh/swaybg)"

    @property
    def backend_id(self) -> str:
        return "generic"

    def is_available(self) -> bool:
        return bool(
            shutil.which("swww")
            or shutil.which("feh")
            or shutil.which("swaybg")
            or shutil.which("nitrogen")
        )

    def apply_wallpaper(self, image_path: Path, mode: str = "fill") -> Tuple[bool, str]:
        if not image_path.is_file():
            return False, f"Image file not found: {image_path}"

        abs_path = str(image_path.resolve())

        # Try swww first (modern Wayland)
        if shutil.which("swww"):
            try:
                subprocess.run(["swww", "img", abs_path], check=True, capture_output=True, timeout=5)
                self.active_wallpaper = image_path
                return True, "Successfully applied wallpaper via swww."
            except Exception:
                pass

        # Try feh (X11)
        if shutil.which("feh"):
            try:
                subprocess.run(["feh", "--bg-fill", abs_path], check=True, capture_output=True, timeout=5)
                self.active_wallpaper = image_path
                return True, "Successfully applied wallpaper via feh."
            except Exception:
                pass

        # Try nitrogen
        if shutil.which("nitrogen"):
            try:
                subprocess.run(["nitrogen", "--set-zoom-fill", abs_path], check=True, capture_output=True, timeout=5)
                self.active_wallpaper = image_path
                return True, "Successfully applied wallpaper via nitrogen."
            except Exception:
                pass

        return False, "No compatible generic wallpaper utility succeeded."
