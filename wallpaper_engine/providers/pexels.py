"""Pexels wallpaper provider with API key configuration."""

import json
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    SourceStatus,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider


class PexelsProvider(WallpaperProvider):
    """Provider for Pexels curated stock photos and desktop backgrounds.
    
    Access Type: TYPE A (Official REST API)
    Requires a free Pexels Developer API key.
    """

    BASE_URL = "https://api.pexels.com/v1"

    @property
    def provider_id(self) -> str:
        return "pexels"

    @property
    def provider_name(self) -> str:
        return "Pexels"

    @property
    def homepage_url(self) -> str:
        return "https://www.pexels.com/"

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
            | Capability.PAGINATION
        )

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="api_key",
                label="Pexels API Key",
                field_type="password",
                default="",
                description="Free API key from pexels.com/api",
            )
        ]

    def configure(self, config: Dict[str, Any]) -> None:
        super().configure(config)
        key = self.config.get("api_key", "").strip()
        if not key:
            self.status = SourceStatus.NOT_CONFIGURED
        else:
            self.status = SourceStatus.ONLINE

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        key = self.config.get("api_key", "").strip()
        if not key:
            self.status = SourceStatus.NOT_CONFIGURED
            return {}

        url = f"{self.BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": key,
                "User-Agent": "PersonalWallpaperEngine/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.record_success()
            return data
        except Exception as exc:
            self.record_failure(f"Pexels request failed: {exc}")
            raise

    def _to_wallpaper(self, item: Dict[str, Any]) -> Wallpaper:
        src = item.get("src", {})
        author = item.get("photographer", "Pexels Photographer")
        width = item.get("width", 0)
        height = item.get("height", 0)

        aspect_ratio = "16:9"
        if width > 0 and height > 0:
            val = round(width / height, 2)
            if val == 1.78:
                aspect_ratio = "16:9"
            elif val == 1.6:
                aspect_ratio = "16:10"
            elif val == 2.33:
                aspect_ratio = "21:9"
            elif val < 1.0:
                aspect_ratio = "Portrait"
            else:
                aspect_ratio = f"{val}:1"

        return Wallpaper(
            id=f"pexels-{item.get('id', '')}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=item.get("alt") or f"Photo by {author}",
            description=f"Photographer: {author}",
            thumbnail_url=src.get("medium") or src.get("small") or "",
            image_url=src.get("original") or src.get("large2x") or "",
            source_url=item.get("url") or self.homepage_url,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            tags=["pexels", "photography", "nature", "city"],
            categories=["Photography", "Pexels"],
            author=author,
            license="Pexels License",
            license_url="https://www.pexels.com/license/",
            attribution_required=True,
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        key = self.config.get("api_key", "").strip()
        if not key:
            return []
        params = {"page": page, "per_page": 24}
        res = self._request("curated", params)
        photos = res.get("photos", [])
        return [self._to_wallpaper(p) for p in photos]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        key = self.config.get("api_key", "").strip()
        if not key:
            return []
        query = filters.query.strip() or "wallpaper"
        params = {
            "query": query,
            "page": filters.page,
            "per_page": filters.page_size or 24,
            "orientation": "landscape",
        }
        res = self._request("search", params)
        photos = res.get("photos", [])
        return [self._to_wallpaper(p) for p in photos]

    def get_categories(self) -> List[str]:
        return ["Photography", "Nature", "City", "Abstract"]
