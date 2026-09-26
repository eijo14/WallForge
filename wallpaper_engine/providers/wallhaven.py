"""Wallhaven provider implementation using official REST API v1."""

import json
import time
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


class WallhavenProvider(WallpaperProvider):
    """Provider for Wallhaven desktop wallpapers.
    
    Access Type: TYPE A (Official REST API)
    Free public searches do not require an API key. An optional user API key
    unlocks user collections and purity toggles.
    """

    BASE_URL = "https://wallhaven.cc/api/v1"

    def __init__(self, cache_manager=None) -> None:
        super().__init__(cache_manager)
        self._last_request_time = 0.0
        self._min_request_interval = 1.35  # ~44 req/min to stay safely below 45 limit

    @property
    def provider_id(self) -> str:
        return "wallhaven"

    @property
    def provider_name(self) -> str:
        return "Wallhaven"

    @property
    def homepage_url(self) -> str:
        return "https://wallhaven.cc/"

    @property
    def capabilities(self) -> Capability:
        return (
            Capability.FEATURED
            | Capability.SEARCH
            | Capability.CATEGORIES
            | Capability.TAGS
            | Capability.RESOLUTION_FILTER
            | Capability.ASPECT_RATIO_FILTER
            | Capability.PAGINATION
            | Capability.RANDOM
            | Capability.DIRECT_IMAGE_URL
            | Capability.AUTHOR_METADATA
        )

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="api_key",
                label="Wallhaven API Key (Optional)",
                field_type="password",
                default="",
                description="Optional API key from wallhaven.cc account settings",
            ),
            SettingField(
                key="categories",
                label="Categories",
                field_type="choice",
                default="111",
                description="Categories to include: 111 (General, Anime, People)",
                options=["111", "100", "010", "110"],
            ),
        ]

    def _rate_limit(self) -> None:
        """Ensure polite spacing between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform HTTP request to Wallhaven API."""
        self._rate_limit()
        api_key = self.config.get("api_key", "").strip()

        filtered_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if api_key:
            filtered_params["apikey"] = api_key

        url = f"{self.BASE_URL}/{endpoint}?{urllib.parse.urlencode(filtered_params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PersonalWallpaperEngine/1.0"},
        )

        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.record_success()
            return data
        except urllib.error.HTTPError as err:
            if err.code == 429:
                self.record_failure("Wallhaven rate limit exceeded (HTTP 429).")
            else:
                self.record_failure(f"Wallhaven HTTP {err.code}: {err.reason}")
            raise
        except Exception as exc:
            self.record_failure(f"Wallhaven request failed: {exc}")
            raise

    def _to_wallpaper(self, item: Dict[str, Any]) -> Wallpaper:
        """Convert a Wallhaven API JSON record into a normalized Wallpaper."""
        item_id = item.get("id", "")
        thumbs = item.get("thumbs", {})
        thumb_url = thumbs.get("large") or thumbs.get("small") or item.get("path", "")

        ratio = str(item.get("ratio", "16:9"))
        if ratio == "1.78":
            aspect_ratio = "16:9"
        elif ratio == "1.6":
            aspect_ratio = "16:10"
        elif ratio == "2.33":
            aspect_ratio = "21:9"
        elif ratio == "1":
            aspect_ratio = "1:1"
        else:
            aspect_ratio = ratio

        category = item.get("category", "General").capitalize()
        source = item.get("source", "")

        return Wallpaper(
            id=f"wallhaven-{item_id}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=f"Wallhaven #{item_id}",
            description=f"Category: {category} | Source: {source}" if source else f"Category: {category}",
            thumbnail_url=thumb_url,
            image_url=item.get("path", ""),
            source_url=item.get("url", f"{self.homepage_url}w/{item_id}"),
            width=int(item.get("dimension_x", 0)),
            height=int(item.get("dimension_y", 0)),
            aspect_ratio=aspect_ratio,
            file_size=int(item.get("file_size", 0)),
            tags=[item.get("category", "general").lower(), item.get("purity", "sfw")],
            categories=[category],
            author="Unknown",
            license="Unknown",
            license_url=source if source else "",
            attribution_required=bool(source),
            created_at=item.get("created_at", ""),
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        """Fetch toplist wallpapers."""
        categories = self.config.get("categories", "111")
        params = {
            "categories": categories,
            "purity": "100",  # SFW
            "sorting": "toplist",
            "topRange": "1M",
            "page": page,
        }
        res = self._request("search", params)
        data = res.get("data", [])
        return [self._to_wallpaper(item) for item in data]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        """Search Wallhaven with server-side filters."""
        params: Dict[str, Any] = {
            "q": filters.query.strip(),
            "categories": self.config.get("categories", "111"),
            "purity": "100",
            "page": filters.page,
        }

        # Resolution filtering
        if filters.min_width > 0 and filters.min_height > 0:
            params["atleast"] = f"{filters.min_width}x{filters.min_height}"

        # Aspect ratio mapping
        if filters.aspect_ratio:
            ratio_map = {
                "16:9": "16x9",
                "16:10": "16x10",
                "21:9": "21x9",
                "32:9": "32x9",
                "1:1": "1x1",
                "portrait": "9x16",
            }
            if filters.aspect_ratio in ratio_map:
                params["ratios"] = ratio_map[filters.aspect_ratio]

        # Sorting mapping
        sort_map = {
            "relevance": "relevance",
            "newest": "date_added",
            "views": "views",
            "favorites": "favorites",
            "random": "random",
            "top": "toplist",
        }
        params["sorting"] = sort_map.get(filters.sorting, "relevance")

        res = self._request("search", params)
        data = res.get("data", [])
        return [self._to_wallpaper(item) for item in data]

    def get_categories(self) -> List[str]:
        return ["General", "Anime", "People"]

    def get_wallpaper(self, wallpaper_id: str) -> Optional[Wallpaper]:
        """Fetch single wallpaper by ID."""
        clean_id = wallpaper_id.replace("wallhaven-", "").strip()
        try:
            res = self._request(f"w/{clean_id}", {})
            data = res.get("data")
            if data:
                return self._to_wallpaper(data)
        except Exception:
            pass
        return None
