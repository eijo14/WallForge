"""ArchImg provider implementation using public dynamic manifest."""

import random
import re
from typing import List, Optional
import urllib.request

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider


class ArchimgProvider(WallpaperProvider):
    """Provider for archimg.cc curated Arch Linux & Hyprland wallpapers.
    
    Access Type: TYPE B (Public Manifest)
    Fetches the dynamic image manifest (image-manifest.txt) and streams
    high-resolution wallpapers directly from Cloudflare CDN.
    """

    MANIFEST_URL = "https://archimg.cc/image-manifest.txt"
    ASSET_BASE_URL = "https://archimg.cc/assets/"
    VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

    @property
    def provider_id(self) -> str:
        return "archimg"

    @property
    def provider_name(self) -> str:
        return "ArchImg"

    @property
    def homepage_url(self) -> str:
        return "https://archimg.cc/"

    @property
    def capabilities(self) -> Capability:
        return (
            Capability.FEATURED
            | Capability.SEARCH
            | Capability.DIRECT_IMAGE_URL
            | Capability.TAGS
            | Capability.CATEGORIES
            | Capability.PAGINATION
            | Capability.RANDOM
        )

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="manifest_refresh_hours",
                label="Manifest Refresh Interval (Hours)",
                field_type="int",
                default=4,
                description="How frequently to refresh the image manifest from archimg.cc",
            )
        ]

    def _fetch_manifest(self) -> List[str]:
        """Fetch and cache list of active image filenames from archimg.cc."""
        refresh_hours = int(self.config.get("manifest_refresh_hours", 4))
        cache_key = "archimg_manifest"

        if self.cache_manager:
            cached = self.cache_manager.get_meta(cache_key, max_age_seconds=refresh_hours * 3600)
            if cached and isinstance(cached, list) and len(cached) > 0:
                return cached

        req = urllib.request.Request(
            self.MANIFEST_URL,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PersonalWallpaperEngine/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                text = resp.read().decode("utf-8", errors="replace")

            filenames = []
            for line in text.splitlines():
                cleaned = line.strip()
                if cleaned.lower().endswith(self.VALID_EXTENSIONS):
                    filenames.append(cleaned)

            if filenames:
                if self.cache_manager:
                    self.cache_manager.set_meta(cache_key, filenames)
                self.record_success()
                return filenames
            else:
                raise ValueError("Manifest was empty or contained no valid image extensions.")
        except Exception as exc:
            self.record_failure(f"Failed to fetch manifest: {exc}")
            # Try to return expired cached manifest if available
            if self.cache_manager:
                fallback = self.cache_manager.get_meta(cache_key, max_age_seconds=86400 * 30)
                if fallback:
                    return fallback
            raise

    def _to_wallpaper(self, filename: str) -> Wallpaper:
        """Convert an asset filename into a normalized Wallpaper model."""
        base_name = filename.rsplit(".", 1)[0]
        # Extract number if present
        match = re.search(r"\d+", base_name)
        num_str = match.group(0) if match else base_name

        image_url = f"{self.ASSET_BASE_URL}{filename}"
        return Wallpaper(
            id=f"archimg-{num_str}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=f"Arch Linux Rice #{num_str}",
            description=f"Arch Linux & Hyprland Ricing Wallpaper ({filename})",
            thumbnail_url=image_url,
            image_url=image_url,
            source_url=self.homepage_url,
            width=0,       # Populated on thumbnail inspect
            height=0,
            aspect_ratio="16:9",  # Common default for rice wallpapers
            tags=["arch", "linux", "hyprland", "rice", "unixporn", "minimalist", "dark"],
            categories=["Linux", "Ricing", "Minimalist"],
            author="ArchImg Community",
            license="Unknown",
            license_url=self.homepage_url,
            attribution_required=False,
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        """Return wallpapers from manifest."""
        manifest = self._fetch_manifest()
        page_size = 24
        start = (page - 1) * page_size
        end = start + page_size
        slice_items = manifest[start:end]
        return [self._to_wallpaper(fn) for fn in slice_items]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        """Perform client-side matching on query, category, and tags."""
        manifest = self._fetch_manifest()
        query = filters.query.lower().strip()
        matched = []

        for fn in manifest:
            wp = self._to_wallpaper(fn)
            if not query:
                matched.append(wp)
                continue

            # Match against number, ID, title, or tags
            if (
                query in wp.id.lower()
                or query in wp.title.lower()
                or query in fn.lower()
                or any(query in t for t in wp.tags)
                or any(query in c.lower() for c in wp.categories)
            ):
                matched.append(wp)

        # Pagination
        page_size = filters.page_size or 24
        start = (filters.page - 1) * page_size
        end = start + page_size
        return matched[start:end]

    def get_categories(self) -> List[str]:
        return ["Linux", "Ricing", "Minimalist"]

    def get_wallpaper(self, wallpaper_id: str) -> Optional[Wallpaper]:
        """Fetch single wallpaper by ID (e.g. 'archimg-019')."""
        manifest = self._fetch_manifest()
        clean_id = wallpaper_id.replace("archimg-", "").strip()
        for fn in manifest:
            if clean_id in fn:
                return self._to_wallpaper(fn)
        return None
