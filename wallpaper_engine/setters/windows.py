"""Native Windows desktop wallpaper setter backend."""

from pathlib import Path
import platform
from typing import Any, Dict, Optional, Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class WindowsWallpaperSetter(WallpaperSetter):
    """Windows wallpaper setter using SystemParametersInfoW and registry."""

    # Win32 Constants
    SPI_SETDESKWALLPAPER = 0x0014
    SPI_GETDESKWALLPAPER = 0x0073
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    MODE_MAP = {
        "fill": ("10", "0"),
        "fit": ("6", "0"),
        "stretch": ("2", "0"),
        "tile": ("0", "1"),
        "center": ("0", "0"),
    }

    @property
    def name(self) -> str:
        return "Windows (SystemParametersInfoW)"

    @property
    def backend_id(self) -> str:
        return "windows"

    @property
    def platform_name(self) -> str:
        return "Windows"

    def is_available(self) -> bool:
        """Check if running on Windows."""
        return platform.system() == "Windows"

    def _configure_wallpaper_style(self, mode: str) -> None:
        """Update Windows registry for wallpaper display style (fill, fit, stretch, tile, center)."""
        style, tile = self.MODE_MAP.get(mode.lower(), ("10", "0"))
        try:
            import winreg  # Only available on Windows
            key_path = r"Control Panel\Desktop"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style)
                winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)
        except Exception:
            pass

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        if not self.is_available():
            return False, "Windows wallpaper backend is only available on Windows."

        try:
            import ctypes
            self._configure_wallpaper_style(mode)

            flags = self.SPIF_UPDATEINIFILE | self.SPIF_SENDCHANGE
            res = ctypes.windll.user32.SystemParametersInfoW(
                self.SPI_SETDESKWALLPAPER,
                0,
                str(path),
                flags,
            )
            if res:
                self.active_wallpaper = path
                return True, "Wallpaper applied via Windows SystemParametersInfoW."
            else:
                return False, "SystemParametersInfoW returned 0 (failed to update wallpaper)."
        except Exception as exc:
            return False, f"Windows wallpaper error: {exc}"

    def get_current_wallpaper(self) -> Optional[str]:
        if not self.is_available():
            return super().get_current_wallpaper()

        try:
            import winreg
            key_path = r"Control Panel\Desktop"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "WallPaper")
                if val and Path(val).is_file():
                    return str(val)
        except Exception:
            pass

        return super().get_current_wallpaper()

    def capabilities(self) -> Dict[str, Any]:
        return {
            "can_set": self.is_available(),
            "can_clear": False,
            "can_get": True,
            "multi_monitor": True,
        }
