"""Platform-aware path management for WallForge.

Provides standardized, per-user directory paths across Linux, Windows, and macOS:
- Cache directory (thumbnails, previews, API metadata)
- Data directory (downloaded wallpapers, rotation pool, logs)
- Config directory (providers configuration, themes, favorites)
"""

import os
from pathlib import Path
import platform
from typing import Optional


class PathManager:
    """Resolves platform-native directories for caching, configuration, and data."""

    def __init__(
        self,
        app_name: str = "wallforge",
        override_cache_dir: Optional[Path] = None,
        override_data_dir: Optional[Path] = None,
        override_config_dir: Optional[Path] = None,
    ) -> None:
        self.app_name = app_name
        self.system = platform.system()
        home = Path.home()

        # -------------------------------------------------------------
        # 1. Cache Directory (Thumbs, Previews, Temporary Parts)
        # -------------------------------------------------------------
        if override_cache_dir:
            self.cache_dir = Path(override_cache_dir)
        elif self.system == "Windows":
            local_app_data = os.environ.get("LOCALAPPDATA")
            base = Path(local_app_data) if local_app_data else (home / "AppData" / "Local")
            self.cache_dir = base / self.app_name / "Cache"
        elif self.system == "Darwin":
            self.cache_dir = home / "Library" / "Caches" / self.app_name
        else:
            # Linux / BSD (XDG Base Directory Specification)
            xdg_cache = os.environ.get("XDG_CACHE_HOME")
            base = Path(xdg_cache) if xdg_cache else (home / ".cache")
            self.cache_dir = base / self.app_name

        # -------------------------------------------------------------
        # 2. Configuration Directory (Themes, Sources, Settings)
        # -------------------------------------------------------------
        if override_config_dir:
            self.config_dir = Path(override_config_dir)
        elif self.system == "Windows":
            roaming_app_data = os.environ.get("APPDATA")
            base = Path(roaming_app_data) if roaming_app_data else (home / "AppData" / "Roaming")
            self.config_dir = base / self.app_name / "Config"
        elif self.system == "Darwin":
            self.config_dir = home / "Library" / "Application Support" / self.app_name
        else:
            # Linux / BSD
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            base = Path(xdg_config) if xdg_config else (home / ".config")
            default_cfg = base / self.app_name
            legacy_cfg = base / "wallpaper-engine"
            if not default_cfg.exists() and legacy_cfg.exists():
                self.config_dir = legacy_cfg
            else:
                self.config_dir = default_cfg

        # -------------------------------------------------------------
        # 3. Data Directory (Downloaded Wallpapers, Favorites, Logs)
        # -------------------------------------------------------------
        if override_data_dir:
            self.data_dir = Path(override_data_dir)
        elif self.system == "Windows":
            local_app_data = os.environ.get("LOCALAPPDATA")
            base = Path(local_app_data) if local_app_data else (home / "AppData" / "Local")
            self.data_dir = base / self.app_name / "Data"
        elif self.system == "Darwin":
            self.data_dir = home / "Library" / "Application Support" / self.app_name / "Data"
        else:
            # Linux / BSD
            xdg_data = os.environ.get("XDG_DATA_HOME")
            base = Path(xdg_data) if xdg_data else (home / ".local" / "share")
            self.data_dir = base / self.app_name

        # Sub-directories
        self.thumbs_dir = self.cache_dir / "thumbs"
        self.previews_dir = self.cache_dir / "previews"
        self.meta_dir = self.cache_dir / "meta"
        self.wallpapers_dir = self.data_dir / "wallpapers"
        self.logs_dir = self.data_dir / "logs"

        # Key configuration files
        self.config_file = self.config_dir / "config.json"
        self.theme_file = self.config_dir / "theme.json"
        self.favorites_file = self.data_dir / "favorites.json"

    def ensure_directories(self) -> None:
        """Create all required directories if they do not yet exist."""
        for d in (
            self.cache_dir,
            self.config_dir,
            self.data_dir,
            self.thumbs_dir,
            self.previews_dir,
            self.meta_dir,
            self.wallpapers_dir,
            self.logs_dir,
        ):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

    @property
    def pictures_dir(self) -> Path:
        """Return native user Pictures directory for wallpaper saving/exports."""
        home = Path.home()
        if self.system == "Windows":
            user_profile = os.environ.get("USERPROFILE")
            return (Path(user_profile) / "Pictures") if user_profile else (home / "Pictures")
        return home / "Pictures"


# Global singleton instance for easy retrieval
_default_path_manager: Optional[PathManager] = None


def get_path_manager() -> PathManager:
    """Return shared PathManager instance."""
    global _default_path_manager
    if _default_path_manager is None:
        _default_path_manager = PathManager()
        _default_path_manager.ensure_directories()
    return _default_path_manager
