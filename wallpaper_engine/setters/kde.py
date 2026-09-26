"""KDE Plasma wallpaper setter."""

import os
from pathlib import Path
import shutil
import subprocess
from typing import List, Optional, Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class KDEPlasmaWallpaperSetter(WallpaperSetter):
    """Sets desktop wallpaper on KDE Plasma environments."""

    @property
    def name(self) -> str:
        return "KDE Plasma (plasma-apply-wallpaperimage)"

    @property
    def backend_id(self) -> str:
        return "kde"

    def is_available(self) -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        if "KDE" in desktop or "PLASMA" in desktop:
            return shutil.which("plasma-apply-wallpaperimage") is not None or shutil.which("qdbus") is not None
        return shutil.which("plasma-apply-wallpaperimage") is not None

    def get_monitors(self) -> List[str]:
        return ["All Monitors"]

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        if shutil.which("plasma-apply-wallpaperimage"):
            try:
                res = subprocess.run(
                    ["plasma-apply-wallpaperimage", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    self.active_wallpaper = path
                    return True, "Wallpaper applied via plasma-apply-wallpaperimage."
                return False, f"plasma-apply-wallpaperimage error: {res.stderr.strip()}"
            except Exception as exc:
                return False, f"Failed to execute plasma-apply-wallpaperimage: {exc}"

        return False, "No supported KDE Plasma wallpaper tool found."
