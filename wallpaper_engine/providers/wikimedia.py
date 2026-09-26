"""Wikimedia Commons provider implementation using MediaWiki Action API."""

import json
import re
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


class WikimediaProvider(WallpaperProvider):
    """Provider for Wikimedia Commons Featured Pictures and high-resolution media.
    
    Access Type: TYPE A (Official MediaWiki Action API)
    Delivers public domain and Creative Commons curated imagery with full attribution.
    """

    API_URL = "https://commons.wikimedia.org/w/api.php"
    COMMONS_URL = "https://commons.wikimedia.org/wiki/"

    @property
    def provider_id(self) -> str:
        return "wikimedia"

    @property
    def provider_name(self) -> str:
        return "Wikimedia Commons"

    @property
    def homepage_url(self) -> str:
        return "https://commons.wikimedia.org/"

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
        )

    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["format"] = "json"
        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "WallForge/1.0 (https://github.com/eijofrancis/wallforge)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.record_success()
            return data
        except Exception as exc:
            self.record_failure(f"Wikimedia API request failed: {exc}")
            raise

    def _clean_html(self, raw_html: str) -> str:
        """Strip HTML tags from artist/license metadata strings."""
        if not raw_html:
            return ""
        clean = re.sub(r"<[^>]+>", "", raw_html)
        return clean.strip()

    def _to_wallpaper(self, page_data: Dict[str, Any]) -> Optional[Wallpaper]:
        imageinfo = page_data.get("imageinfo", [])
        if not imageinfo:
            return None

        info = imageinfo[0]
        mime = info.get("mime", "")
        if not mime.startswith("image/"):
            return None

        title = page_data.get("title", "").replace("File:", "").replace("_", " ")
        image_url = info.get("url", "")
        if not image_url:
            return None

        meta = info.get("extmetadata", {})
        artist_raw = meta.get("Artist", {}).get("value", "")
        author = self._clean_html(artist_raw) or "Wikimedia Contributor"

        license_short = meta.get("LicenseShortName", {}).get("value", "Unknown")
        license_url = meta.get("LicenseUrl", {}).get("value", "")

        width = int(info.get("width", 0))
        height = int(info.get("height", 0))

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

        page_id = page_data.get("pageid", "")
        wiki_url = f"{self.COMMONS_URL}{urllib.parse.quote(page_data.get('title', ''))}"

        thumb_url = info.get("thumburl") or image_url

        return Wallpaper(
            id=f"wikimedia-{page_id}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=title[:40],
            description=self._clean_html(meta.get("ImageDescription", {}).get("value", "")),
            thumbnail_url=thumb_url,
            image_url=image_url,
            source_url=wiki_url,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            file_size=int(info.get("size", 0)),
            tags=["wikimedia", "commons", "photography", "heritage"],
            categories=["Photography", "Featured", "Public Domain"],
            author=author,
            license=license_short,
            license_url=license_url,
            attribution_required=(license_short.lower() not in ("cc0", "public domain", "pd")),
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        cache_key = f"wikimedia_featured_p{page}"
        if self.cache_manager:
            cached = self.cache_manager.get_meta(cache_key, max_age_seconds=14400)
            if cached and isinstance(cached, list):
                parsed = [self._to_wallpaper(p) for p in cached]
                return [w for w in parsed if w is not None]

        params = {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": "Category:Featured_pictures_on_Wikimedia_Commons",
            "gcmlimit": 24,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1280,
        }
        res = self._request(params)
        pages = res.get("query", {}).get("pages", {})
        page_list = list(pages.values())

        if self.cache_manager and page_list:
            self.cache_manager.set_meta(cache_key, page_list)

        parsed = [self._to_wallpaper(p) for p in page_list]
        return [w for w in parsed if w is not None]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        query = filters.query.strip()
        if not query:
            return self.get_featured(page=filters.page)

        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:bitmap {query}",
            "gsrlimit": filters.page_size or 24,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1280,
        }
        res = self._request(params)
        pages = res.get("query", {}).get("pages", {})
        parsed = [self._to_wallpaper(p) for p in pages.values()]
        return [w for w in parsed if w is not None]

    def get_categories(self) -> List[str]:
        return ["Photography", "Featured", "Heritage"]
