"""Unsplash wallpaper provider with secure API key configuration."""

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


class UnsplashProvider(WallpaperProvider):
    """Provider for Unsplash high-resolution photography.
    
    Access Type: TYPE A (Official REST API)
    Requires a free Unsplash Developer Client-ID.
    """

    BASE_URL = "https://api.unsplash.com"

    @property
    def provider_id(self) -> str:
        return "unsplash"

    @property
    def provider_name(self) -> str:
        return "Unsplash"

    @property
    def homepage_url(self) -> str:
        return "https://unsplash.com/"

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
                key="access_key",
                label="Unsplash Access Key (Client-ID)",
                field_type="password",
                default="",
                description="Register a free app at unsplash.com/developers to get an Access Key",
            )
        ]

    def configure(self, config: Dict[str, Any]) -> None:
        super().configure(config)
        key = self.config.get("access_key", "").strip()
        if not key:
            self.status = SourceStatus.NOT_CONFIGURED
        else:
            self.status = SourceStatus.ONLINE

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Any:
        key = self.config.get("access_key", "").strip()
        if not key:
            self.status = SourceStatus.NOT_CONFIGURED
            return []

        url = f"{self.BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Client-ID {key}",
                "User-Agent": "PersonalWallpaperEngine/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.record_success()
            return data
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                self.record_failure(f"Unsplash API authentication error ({err.code}): invalid key.")
            else:
                self.record_failure(f"Unsplash HTTP {err.code}: {err.reason}")
            raise
        except Exception as exc:
            self.record_failure(f"Unsplash request failed: {exc}")
            raise

    def _to_wallpaper(self, item: Dict[str, Any]) -> Wallpaper:
        user = item.get("user", {})
        urls = item.get("urls", {})
        links = item.get("links", {})

        author = user.get("name") or user.get("username") or "Unsplash Photographer"
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
            id=f"unsplash-{item.get('id', '')}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=item.get("alt_description") or item.get("description") or f"Photo by {author}",
            description=item.get("description", ""),
            thumbnail_url=urls.get("small") or urls.get("thumb") or "",
            image_url=urls.get("full") or urls.get("regular") or "",
            source_url=links.get("html") or self.homepage_url,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            tags=["photography", "unsplash", "nature", "architecture"],
            categories=["Photography", "Unsplash"],
            author=author,
            license="Unsplash License",
            license_url="https://unsplash.com/license",
            attribution_required=True,
            created_at=item.get("created_at", ""),
            download_location=links.get("download_location", ""),
        )

    def track_download(self, wallpaper_or_location: Any) -> Any:
        """Asynchronously notify Unsplash download endpoint as required by API guidelines."""
        dl_url = (
            wallpaper_or_location.download_location
            if isinstance(wallpaper_or_location, Wallpaper)
            else str(wallpaper_or_location or "")
        )
        if dl_url:
            return report_unsplash_download(dl_url, self.config.get("access_key", "").strip())
        return None


    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        key = self.config.get("access_key", "").strip()
        if not key:
            return []
        params = {"page": page, "per_page": 24, "order_by": "popular"}
        data = self._request("photos", params)
        if isinstance(data, list):
            return [self._to_wallpaper(p) for p in data]
        return []

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        key = self.config.get("access_key", "").strip()
        if not key:
            return []
        query = filters.query.strip() or "wallpaper"
        params = {
            "query": query,
            "page": filters.page,
            "per_page": filters.page_size or 24,
        }
        res = self._request("search/photos", params)
        results = res.get("results", []) if isinstance(res, dict) else []
        return [self._to_wallpaper(p) for p in results]

    def get_categories(self) -> List[str]:
        return ["Photography", "Architecture", "Nature", "Textures"]


def report_unsplash_download(download_location: str, access_key: str = "") -> Any:
    """Asynchronously notify Unsplash download endpoint according to official API terms."""
    if not download_location:
        return None

    def _fire():
        try:
            headers = {"User-Agent": "WallForge/1.0"}
            if access_key:
                headers["Authorization"] = f"Client-ID {access_key}"
            req = urllib.request.Request(download_location, headers=headers)
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pass

    import threading
    t = threading.Thread(target=_fire, daemon=True)
    t.start()
    return t
