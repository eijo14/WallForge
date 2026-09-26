"""Openverse provider implementation using official REST API."""

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


class OpenverseProvider(WallpaperProvider):
    """Provider for openly licensed images and artwork from Openverse.
    
    Access Type: TYPE A (Official REST API)
    Indexes over 700 million Creative Commons and Public Domain works.
    Anonymous rate limit: 20 req/min.
    """

    BASE_URL = "https://api.openverse.org/v1/images"

    @property
    def provider_id(self) -> str:
        return "openverse"

    @property
    def provider_name(self) -> str:
        return "Openverse"

    @property
    def homepage_url(self) -> str:
        return "https://openverse.org/"

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
                key="license_filter",
                label="License Filter",
                field_type="choice",
                default="cc0,pdm,by",
                description="Allowed Creative Commons licenses",
                options=["all", "cc0,pdm,by", "cc0,pdm"],
            )
        ]

    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        license_filter = self.config.get("license_filter", "cc0,pdm,by")
        if license_filter != "all":
            params["license"] = license_filter

        url = f"{self.BASE_URL}/?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PersonalWallpaperEngine/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.record_success()
            return data
        except Exception as exc:
            self.record_failure(f"Openverse request failed: {exc}")
            raise

    def _to_wallpaper(self, item: Dict[str, Any]) -> Wallpaper:
        lic = item.get("license", "").upper()
        lic_ver = item.get("license_version", "")
        license_name = f"CC {lic} {lic_ver}".strip() if lic else "Unknown"

        width = item.get("width") or 0
        height = item.get("height") or 0

        aspect_ratio = "Unknown"
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

        tags = [t.get("name", "").lower() for t in item.get("tags", []) if t.get("name")]
        image_url = item.get("url", "")
        thumb_url = item.get("thumbnail") or image_url

        return Wallpaper(
            id=f"openverse-{item.get('id', '')}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=item.get("title") or "Openverse Artwork",
            description=item.get("attribution", ""),
            thumbnail_url=thumb_url,
            image_url=image_url,
            source_url=item.get("foreign_landing_url") or self.homepage_url,
            width=int(width),
            height=int(height),
            aspect_ratio=aspect_ratio,
            tags=tags[:8],
            categories=["Creative Commons", "Art"],
            author=item.get("creator") or "Unknown",
            license=license_name,
            license_url=item.get("license_url", ""),
            attribution_required=(lic.lower() != "cc0"),
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        params = {
            "q": "wallpaper desktop landscape",
            "page": page,
            "page_size": 24,
        }
        res = self._request(params)
        results = res.get("results", [])
        return [self._to_wallpaper(item) for item in results]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        query = filters.query.strip() or "wallpaper"
        params = {
            "q": query,
            "page": filters.page,
            "page_size": filters.page_size or 24,
        }
        res = self._request(params)
        results = res.get("results", [])
        return [self._to_wallpaper(item) for item in results]

    def get_categories(self) -> List[str]:
        return ["Creative Commons", "Art", "Photography"]
