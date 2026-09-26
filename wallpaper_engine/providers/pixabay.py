"""Pixabay wallpaper provider with API key configuration."""

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


class PixabayProvider(WallpaperProvider):
    """Provider for Pixabay stock wallpapers and artwork.
    
    Access Type: TYPE A (Official REST API)
    Requires a free Pixabay API key.
    """

    BASE_URL = "https://pixabay.com/api"

    @property
    def provider_id(self) -> str:
        return "pixabay"

    @property
    def provider_name(self) -> str:
        return "Pixabay"

    @property
    def homepage_url(self) -> str:
        return "https://pixabay.com/"

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
                label="Pixabay API Key",
                field_type="password",
                default="",
                description="Free API key from pixabay.com/api/docs",
            )
        ]

    def configure(self, config: Dict[str, Any]) -> None:
        super().configure(config)
        key = self.config.get("api_key", "").strip()
        if not key:
            self.status = SourceStatus.NOT_CONFIGURED
        else:
            self.status = SourceStatus.ONLINE

    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        key = self.config.get("api_key", "").strip()
        if not key:
            self.status = SourceStatus.NOT_CONFIGURED
            return {}

        params["key"] = key
        url = f"{self.BASE_URL}/?{urllib.parse.urlencode(params)}"
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
            self.record_failure(f"Pixabay request failed: {exc}")
            raise

    def _to_wallpaper(self, item: Dict[str, Any]) -> Wallpaper:
        author = item.get("user", "Pixabay Contributor")
        width = item.get("imageWidth", 0)
        height = item.get("imageHeight", 0)

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

        raw_tags = item.get("tags", "")
        tags = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]

        return Wallpaper(
            id=f"pixabay-{item.get('id', '')}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=f"Pixabay #{item.get('id', '')} ({tags[0] if tags else 'Artwork'})",
            description=f"Tags: {raw_tags} | By: {author}",
            thumbnail_url=item.get("webformatURL") or item.get("previewURL") or "",
            image_url=item.get("largeImageURL") or item.get("webformatURL") or "",
            source_url=item.get("pageURL") or self.homepage_url,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            tags=tags[:8],
            categories=["Stock", "Photography", "Vector"],
            author=author,
            license="Pixabay License",
            license_url="https://pixabay.com/service/license-summary/",
            attribution_required=False,
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        key = self.config.get("api_key", "").strip()
        if not key:
            return []
        params = {
            "q": "wallpaper",
            "image_type": "photo",
            "orientation": "horizontal",
            "min_width": 1920,
            "page": page,
            "per_page": 24,
            "order": "popular",
        }
        res = self._request(params)
        hits = res.get("hits", [])
        return [self._to_wallpaper(p) for p in hits]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        key = self.config.get("api_key", "").strip()
        if not key:
            return []
        query = filters.query.strip() or "wallpaper"
        params = {
            "q": query,
            "image_type": "photo",
            "orientation": "horizontal",
            "page": filters.page,
            "per_page": filters.page_size or 24,
        }
        res = self._request(params)
        hits = res.get("hits", [])
        return [self._to_wallpaper(p) for p in hits]

    def get_categories(self) -> List[str]:
        return ["Photography", "Nature", "Vector", "Illustration"]
