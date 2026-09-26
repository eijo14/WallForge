"""Local filesystem wallpaper provider."""

import hashlib
import os
from pathlib import Path
from typing import List, Optional

from PIL import Image

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider


class LocalProvider(WallpaperProvider):
    """Provider for scanning and applying user's local wallpaper collections.
    
    Access Type: TYPE E (Local Filesystem)
    Scans the application's downloaded wallpapers directory and any custom
    user directories specified in settings.
    """

    SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp")

    def __init__(self, cache_manager=None) -> None:
        super().__init__(cache_manager)
        if cache_manager:
            self.default_dir = cache_manager.wallpapers_dir
        else:
            from wallpaper_engine.core.paths import PathManager
            self.default_dir = PathManager().wallpapers_dir

        try:
            self.default_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    @property
    def provider_id(self) -> str:
        return "local"

    @property
    def provider_name(self) -> str:
        return "Local Wallpapers"

    @property
    def homepage_url(self) -> str:
        return self.default_dir.as_uri()

    @property
    def capabilities(self) -> Capability:
        return (
            Capability.FEATURED
            | Capability.SEARCH
            | Capability.CATEGORIES
            | Capability.TAGS
            | Capability.DIRECT_IMAGE_URL
            | Capability.RANDOM
        )

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="custom_folders",
                label="Custom Wallpaper Folders",
                field_type="string",
                default="",
                description="Comma-separated paths to additional local wallpaper directories",
            )
        ]

    def _get_search_directories(self) -> List[Path]:
        """Collect directories to scan for wallpapers."""
        dirs = [self.default_dir]
        custom = self.config.get("custom_folders", "").strip()
        if custom:
            for piece in custom.split(","):
                p = Path(piece.strip()).expanduser().resolve()
                if p.is_dir() and p not in dirs:
                    dirs.append(p)
        return dirs

    def _inspect_file(self, file_path: Path) -> Optional[Wallpaper]:
        """Read image header using Pillow to extract resolution and aspect ratio."""
        try:
            stat = file_path.stat()
            with Image.open(file_path) as img:
                width, height = img.size
                fmt = img.format or "IMAGE"

            # Compute aspect ratio string
            if width > 0 and height > 0:
                ratio_val = round(width / height, 2)
                if ratio_val == 1.78:
                    aspect_ratio = "16:9"
                elif ratio_val == 1.6:
                    aspect_ratio = "16:10"
                elif ratio_val == 2.33:
                    aspect_ratio = "21:9"
                elif ratio_val == 1.0:
                    aspect_ratio = "1:1"
                elif ratio_val < 1.0:
                    aspect_ratio = "Portrait"
                else:
                    aspect_ratio = f"{ratio_val}:1"
            else:
                aspect_ratio = "Unknown"

            h = hashlib.sha256(str(file_path).encode("utf-8")).hexdigest()[:16]
            file_uri = file_path.as_uri()

            # Generate or retrieve local thumbnail if cache manager is present
            thumb_url = file_uri
            if self.cache_manager:
                thumb_path = self.cache_manager.get_thumbnail_path(file_uri)
                if not thumb_path:
                    thumb_path = self.cache_manager.create_thumbnail(file_path, file_uri)
                thumb_url = thumb_path.as_uri()

            category = file_path.parent.name if file_path.parent != self.default_dir else "Downloaded"

            return Wallpaper(
                id=f"local-{h}",
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                title=file_path.stem.replace("-", " ").replace("_", " ").title(),
                description=f"Local {fmt} image from {file_path.parent.name}",
                thumbnail_url=thumb_url,
                image_url=file_uri,
                source_url=file_uri,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                file_size=stat.st_size,
                tags=["local", "saved", fmt.lower()],
                categories=[category],
                author="Local User",
                license="Local User File",
                license_url="",
                attribution_required=False,
            )
        except Exception:
            return None

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        """Scan directories and return local wallpapers."""
        wallpapers = []
        for directory in self._get_search_directories():
            if not directory.is_dir():
                continue
            for entry in directory.iterdir():
                if entry.is_file() and entry.suffix.lower() in self.SUPPORTED_EXTS:
                    wp = self._inspect_file(entry)
                    if wp:
                        wallpapers.append(wp)

        self.record_success()
        # Sort newest modified first
        return wallpapers

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        """Filter local wallpapers by title, tags, or dimensions."""
        all_local = self.get_featured(page=1)
        query = filters.query.lower().strip()
        matched = []

        for wp in all_local:
            if not query:
                matched.append(wp)
            elif (
                query in wp.title.lower()
                or query in wp.description.lower()
                or any(query in t for t in wp.tags)
                or any(query in c.lower() for c in wp.categories)
            ):
                matched.append(wp)

        return matched

    def get_categories(self) -> List[str]:
        return ["Downloaded", "Custom"]

    def get_wallpaper(self, wallpaper_id: str) -> Optional[Wallpaper]:
        all_local = self.get_featured(page=1)
        for wp in all_local:
            if wp.id == wallpaper_id:
                return wp
        return None
