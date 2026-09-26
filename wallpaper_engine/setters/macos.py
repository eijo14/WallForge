"""Native macOS desktop wallpaper setter backend."""

from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any, Dict, Optional, Tuple

from wallpaper_engine.setters.base import WallpaperSetter


class MacOSWallpaperSetter(WallpaperSetter):
    """macOS wallpaper setter using AppleScript via osascript."""

    @property
    def name(self) -> str:
        return "macOS (AppleScript / osascript)"

    @property
    def backend_id(self) -> str:
        return "macos"

    @property
    def platform_name(self) -> str:
        return "macOS"

    def is_available(self) -> bool:
        """Check if running on macOS with osascript command available."""
        return platform.system() == "Darwin" and shutil.which("osascript") is not None

    def apply_wallpaper(self, image_path: Path, mode: str = "fill", monitor: Optional[str] = None) -> Tuple[bool, str]:
        path = image_path.resolve()
        if not path.is_file():
            return False, f"Image file does not exist: {path}"

        if not self.is_available():
            return False, "macOS wallpaper backend is only available on macOS."

        try:
            # Pass image path securely via positional argv to prevent AppleScript injection
            script = (
                'on run argv\n'
                '    tell application "System Events"\n'
                '        tell every desktop\n'
                '            set picture to (item 1 of argv)\n'
                '        end tell\n'
                '    end tell\n'
                'end run'
            )

            proc = subprocess.run(
                ["osascript", "-e", script, str(path)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if proc.returncode == 0:
                self.active_wallpaper = path
                return True, "Wallpaper applied via macOS AppleScript."
            else:
                err_msg = proc.stderr.strip() or "osascript exited with error"
                return False, f"AppleScript error: {err_msg}"
        except subprocess.TimeoutExpired:
            return False, "AppleScript timed out while applying wallpaper."
        except Exception as exc:
            return False, f"macOS wallpaper error: {exc}"

    def get_current_wallpaper(self) -> Optional[str]:
        if not self.is_available():
            return super().get_current_wallpaper()

        try:
            script = 'tell application "System Events" to get picture of current desktop'
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                val = proc.stdout.strip()
                if Path(val).is_file():
                    return val
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
