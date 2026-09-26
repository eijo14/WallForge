"""NASA Astronomy Picture of the Day (APOD) provider implementation."""

import json
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider


class NasaApodProvider(WallpaperProvider):
    """Provider for NASA Astronomy Picture of the Day (APOD) wallpapers.
    
    Access Type: TYPE A (Official REST API)
    Uses NASA's open API to fetch ultra-high-resolution space and astronomy imagery.
    Works out of the box with DEMO_KEY; users can provide their own api.data.gov key.
    """

    BASE_URL = "https://api.nasa.gov/planetary/apod"

    @property
    def provider_id(self) -> str:
        return "nasa_apod"

    @property
    def provider_name(self) -> str:
        return "NASA Space"

    @property
    def homepage_url(self) -> str:
        return "https://apod.nasa.gov/"

    @property
    def capabilities(self) -> Capability:
        return (
            Capability.FEATURED
            | Capability.SEARCH
            | Capability.CATEGORIES
            | Capability.TAGS
            | Capability.DIRECT_IMAGE_URL
            | Capability.AUTHOR_METADATA
            | Capability.LICENSE_METADATA
            | Capability.RANDOM
        )

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="api_key",
                label="NASA API Key (Optional)",
                field_type="password",
                default="DEMO_KEY",
                description="Custom api.data.gov key (defaults to DEMO_KEY)",
            )
        ]

    def _request(self, params: Dict[str, Any]) -> Any:
        """Issue request to NASA APOD endpoint."""
        api_key = self.config.get("api_key", "DEMO_KEY").strip() or "DEMO_KEY"
        params["api_key"] = api_key

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PersonalWallpaperEngine/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.record_success()
            return data
        except Exception as exc:
            self.record_failure(f"NASA APOD request failed: {exc}")
            raise

    def _to_wallpaper(self, item: Dict[str, Any]) -> Optional[Wallpaper]:
        """Convert an APOD JSON item into a normalized Wallpaper."""
        if item.get("media_type") != "image":
            return None  # Skip video APOD entries

        date = item.get("date", "")
        clean_date = date.replace("-", "")
        # APOD archive URL format: apYYMMDD.html
        archive_slug = f"ap{clean_date[2:]}.html" if len(clean_date) >= 8 else ""
        source_url = f"https://apod.nasa.gov/apod/{archive_slug}" if archive_slug else self.homepage_url

        image_url = item.get("hdurl") or item.get("url", "")
        thumb_url = item.get("url") or image_url
        copyright_artist = item.get("copyright", "NASA / Public Domain").strip()
        is_copyrighted = bool(item.get("copyright"))

        license_name = "Copyright Artist" if is_copyrighted else "Public Domain (NASA)"

        return Wallpaper(
            id=f"nasa-{date}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=item.get("title", f"Space Picture ({date})"),
            description=item.get("explanation", ""),
            thumbnail_url=thumb_url,
            image_url=image_url,
            source_url=source_url,
            width=0,       # Populated on inspection
            height=0,
            aspect_ratio="16:9",
            tags=["nasa", "space", "astronomy", "cosmos", "universe", "stars"],
            categories=["Space", "Astronomy", "Science"],
            author=copyright_artist,
            license=license_name,
            license_url="https://www.nasa.gov/multimedia/guidelines/index.html",
            attribution_required=is_copyrighted,
            created_at=date,
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        """Fetch a batch of random or recent astronomy wallpapers."""
        cache_key = f"nasa_featured_p{page}"
        if self.cache_manager:
            cached = self.cache_manager.get_meta(cache_key, max_age_seconds=14400)
            if cached and isinstance(cached, list):
                return [self._to_wallpaper(i) for i in cached if self._to_wallpaper(i)]

        # Fetch 20 random pictures
        data = self._request({"count": 20, "thumbs": "true"})
        if isinstance(data, list):
            if self.cache_manager:
                self.cache_manager.set_meta(cache_key, data)
            wallpapers = [self._to_wallpaper(item) for item in data]
            return [wp for wp in wallpapers if wp is not None]
        return []

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        """Search NASA APOD wallpapers."""
        wallpapers = self.get_featured(page=1)
        query = filters.query.lower().strip()
        if not query:
            return wallpapers

        return [
            wp for wp in wallpapers
            if (
                query in wp.title.lower()
                or query in wp.description.lower()
                or query in wp.author.lower()
                or any(query in t for t in wp.tags)
            )
        ]

    def get_categories(self) -> List[str]:
        return ["Space", "Astronomy", "Science"]

    def get_wallpaper(self, wallpaper_id: str) -> Optional[Wallpaper]:
        clean_date = wallpaper_id.replace("nasa-", "").strip()
        try:
            data = self._request({"date": clean_date, "thumbs": "true"})
            if isinstance(data, dict):
                return self._to_wallpaper(data)
        except Exception:
            pass
        return None
