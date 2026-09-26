"""Bing Wallpaper Archive provider implementation using official daily JSON feed."""

import json
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


class BingProvider(WallpaperProvider):
    """Provider for Bing daily featured desktop wallpapers.
    
    Access Type: TYPE C (Public Structured Feed)
    Fetches the official HPImageArchive feed delivering high-resolution
    1080p and UHD 4K landscape photography.
    """

    FEED_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=en-US"
    BASE_URL = "https://www.bing.com"

    @property
    def provider_id(self) -> str:
        return "bing"

    @property
    def provider_name(self) -> str:
        return "Bing Daily"

    @property
    def homepage_url(self) -> str:
        return "https://www.bing.com/"

    @property
    def capabilities(self) -> Capability:
        return (
            Capability.FEATURED
            | Capability.SEARCH
            | Capability.DIRECT_IMAGE_URL
            | Capability.CATEGORIES
            | Capability.TAGS
            | Capability.AUTHOR_METADATA
            | Capability.LICENSE_METADATA
        )

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="prefer_uhd",
                label="Prefer 4K UHD Wallpapers",
                field_type="bool",
                default=True,
                description="Request 3840x2160 UHD stream instead of 1080p",
            ),
            SettingField(
                key="market",
                label="Region / Market Code",
                field_type="choice",
                default="en-US",
                description="Bing market localization for daily wallpapers",
                options=["en-US", "en-GB", "de-DE", "fr-FR", "ja-JP"],
            ),
        ]

    def _fetch_feed(self) -> List[dict]:
        """Fetch daily image archive feed."""
        market = self.config.get("market", "en-US")
        cache_key = f"bing_feed_{market}"

        if self.cache_manager:
            cached = self.cache_manager.get_meta(cache_key, max_age_seconds=7200)
            if cached and isinstance(cached, list):
                return cached

        url = f"https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt={market}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PersonalWallpaperEngine/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            images = data.get("images", [])
            if self.cache_manager and images:
                self.cache_manager.set_meta(cache_key, images)
            self.record_success()
            return images
        except Exception as exc:
            self.record_failure(f"Bing feed request failed: {exc}")
            if self.cache_manager:
                fallback = self.cache_manager.get_meta(cache_key, max_age_seconds=86400 * 7)
                if fallback:
                    return fallback
            raise

    def _to_wallpaper(self, item: dict) -> Wallpaper:
        """Convert a Bing JSON image entry into normalized Wallpaper."""
        prefer_uhd = self.config.get("prefer_uhd", True)
        urlbase = item.get("urlbase", "")
        raw_url = item.get("url", "")
        hsh = item.get("hsh") or item.get("startdate", "")

        if prefer_uhd and urlbase:
            image_url = f"{self.BASE_URL}{urlbase}_UHD.jpg"
            width, height = 3840, 2160
        else:
            image_url = f"{self.BASE_URL}{raw_url}"
            width, height = 1920, 1080

        thumb_url = f"{self.BASE_URL}{raw_url}"
        copyright_text = item.get("copyright", "")
        title = item.get("title") or "Bing Daily Wallpaper"

        # Extract photographer / source from copyright e.g. "Title (© Author/Getty)"
        author = "Unknown"
        match = re.search(r"©\s*([^)]+)", copyright_text)
        if match:
            author = match.group(1).strip()

        return Wallpaper(
            id=f"bing-{hsh}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=title,
            description=copyright_text,
            thumbnail_url=thumb_url,
            image_url=image_url,
            source_url=item.get("copyrightlink") or self.homepage_url,
            width=width,
            height=height,
            aspect_ratio="16:9",
            tags=["bing", "daily", "landscape", "nature", "photography"],
            categories=["Nature", "Landscape", "Daily"],
            author=author,
            license="Copyrighted (Personal Desktop Use Only)",
            license_url="https://www.microsoft.com/servicesagreement",
            attribution_required=True,
            created_at=item.get("startdate", ""),
            published_at=item.get("fullstartdate", ""),
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        """Return available daily wallpapers."""
        images = self._fetch_feed()
        return [self._to_wallpaper(item) for item in images]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        """Client-side search across daily wallpapers."""
        images = self._fetch_feed()
        query = filters.query.lower().strip()
        matched = []

        for item in images:
            wp = self._to_wallpaper(item)
            if not query:
                matched.append(wp)
            elif (
                query in wp.title.lower()
                or query in wp.description.lower()
                or query in wp.author.lower()
                or any(query in t for t in wp.tags)
            ):
                matched.append(wp)

        return matched

    def get_categories(self) -> List[str]:
        return ["Nature", "Landscape", "Daily"]

    def get_wallpaper(self, wallpaper_id: str) -> Optional[Wallpaper]:
        images = self._fetch_feed()
        clean_id = wallpaper_id.replace("bing-", "").strip()
        for item in images:
            hsh = item.get("hsh") or item.get("startdate", "")
            if clean_id in hsh:
                return self._to_wallpaper(item)
        return None
