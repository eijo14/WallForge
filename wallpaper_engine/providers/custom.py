"""Generic dynamic custom wallpaper provider supporting user-defined feeds, APIs, manifests, and folders."""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    SourceStatus,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider
from wallpaper_engine.core.security import is_safe_url


class CustomWallpaperProvider(WallpaperProvider):
    """User-configured dynamic wallpaper source."""

    def __init__(self, custom_config: Dict[str, Any], cache_manager: Optional[CacheManager] = None) -> None:
        super().__init__(cache_manager=cache_manager)
        self._cfg = custom_config
        self._pid = custom_config.get("id", f"custom_{abs(hash(custom_config.get('url', '')))}")
        self._name = custom_config.get("name", "Custom Source")
        self._source_type = custom_config.get("type") or custom_config.get("feed_type", "json_feed")
        self._url = custom_config.get("url") or custom_config.get("url_or_path", "")
        self.configure(custom_config)

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def homepage_url(self) -> str:
        return self._url or "https://localhost"

    @property
    def capabilities(self) -> Capability:
        caps = Capability.FEATURED | Capability.DIRECT_IMAGE_URL
        if self._source_type in ("rest_api", "local_folder", "image_manifest"):
            caps |= Capability.SEARCH
        if self._cfg.get("has_pagination", True):
            caps |= Capability.PAGINATION
        return caps

    def get_settings_schema(self) -> List[SettingField]:
        return [
            SettingField(
                key="api_key",
                label="API Key / Token (Optional)",
                field_type="password",
                default=self._cfg.get("api_key", ""),
                description="Optional secret API key or Bearer token.",
            )
        ]

    def _get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "PersonalWallpaperEngine/2.0"}
        api_header = self._cfg.get("api_header", "Authorization")
        api_key = self.config.get("api_key") or self._cfg.get("api_key", "")
        if api_key:
            if api_header.lower() == "authorization" and not api_key.startswith("Bearer "):
                headers[api_header] = f"Bearer {api_key}"
            else:
                headers[api_header] = api_key
        return headers

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        if self._source_type == "local_folder":
            return self._search_local(filters.query)
        elif self._source_type in ("json_feed", "rest_api"):
            results = self._fetch_json(filters.query, filters.page)
            if self._source_type == "json_feed" and filters.query:
                q = filters.query.lower()
                results = [w for w in results if q in w.title.lower()]
            return results
        elif self._source_type == "image_manifest":
            return self._fetch_manifest(filters.query)
        return []

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        if self._source_type == "local_folder":
            return self._search_local("")
        elif self._source_type in ("json_feed", "rest_api"):
            return self._fetch_json("", page)
        elif self._source_type == "image_manifest":
            return self._fetch_manifest("")
        return []

    def _search_local(self, query: str) -> List[Wallpaper]:
        folder = Path(self._url)
        if not folder.is_dir():
            return []
        valid_exts = (".jpg", ".jpeg", ".png", ".webp")
        query_lower = query.lower()
        results = []
        for p in folder.rglob("*"):
            if p.suffix.lower() in valid_exts:
                if not query_lower or query_lower in p.name.lower():
                    results.append(
                        Wallpaper(
                            id=f"{self._pid}-{abs(hash(str(p)))}",
                            provider_id=self._pid,
                            provider_name=self._name,
                            title=p.stem.replace("_", " ").replace("-", " ").title(),
                            image_url=str(p.resolve()),
                            thumbnail_url=str(p.resolve()),
                            source_url=str(p.parent),
                        )
                    )
        return results

    def _fetch_manifest(self, query: str) -> List[Wallpaper]:
        safe, msg = is_safe_url(self._url)
        if not safe:
            self.record_failure(f"Unsafe source URL: {msg}")
            return []

        req = urllib.request.Request(self._url, headers=self._get_headers())
        with urllib.request.urlopen(req, timeout=6) as resp:
            text = resp.read().decode("utf-8", errors="replace")

        base_asset = self._cfg.get("asset_base_url") or self._url.rsplit("/", 1)[0] + "/"
        wallpapers = []
        query_lower = query.lower()
        for idx, line in enumerate(text.splitlines()):
            line = line.strip()
            if line and line.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                if not query_lower or query_lower in line.lower():
                    img_url = line if line.startswith("http") else f"{base_asset}{line}"
                    wallpapers.append(
                        Wallpaper(
                            id=f"{self._pid}-{idx}",
                            provider_id=self._pid,
                            provider_name=self._name,
                            title=Path(line).stem.replace("-", " ").replace("_", " ").title(),
                            image_url=img_url,
                            thumbnail_url=img_url,
                            source_url=img_url,
                        )
                    )
        return wallpapers

    def _extract_field(self, item: Dict[str, Any], path: str, default: Any = "") -> Any:
        if not path:
            return default
        cur: Any = item
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur

    def _fetch_json(self, query: str, page: int) -> List[Wallpaper]:
        url = self._url
        # Query parameter replacement
        if "{query}" in url:
            url = url.replace("{query}", urllib.parse.quote(query))
        elif query:
            sep = "&" if "?" in url else "?"
            query_param = self._cfg.get("query_param", "q")
            url = f"{url}{sep}{query_param}={urllib.parse.quote(query)}"

        if "{page}" in url:
            url = url.replace("{page}", str(page))
        elif page > 1:
            sep = "&" if "?" in url else "?"
            page_param = self._cfg.get("page_param", "page")
            url = f"{url}{sep}{page_param}={page}"

        safe, msg = is_safe_url(url)
        if not safe:
            self.record_failure(f"Unsafe source URL: {msg}")
            return []

        req = urllib.request.Request(url, headers=self._get_headers())
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        items = data
        items_path = self._cfg.get("items_field", "")
        if items_path and isinstance(data, dict):
            items = self._extract_field(data, items_path, [])
        elif isinstance(data, dict):
            # Auto-detect array field
            for v in data.values():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    items = v
                    break

        if not isinstance(items, list):
            return []

        img_field = self._cfg.get("image_field")
        thumb_field = self._cfg.get("thumbnail_field")
        title_field = self._cfg.get("title_field", "title")

        wallpapers = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            img_url = None
            if img_field:
                img_url = self._extract_field(item, img_field)
            else:
                for candidate in ("image_url", "url", "image", "src", "file", "download_url"):
                    val = self._extract_field(item, candidate)
                    if val and isinstance(val, str):
                        img_url = val
                        break

            if not img_url or not isinstance(img_url, str):
                continue

            thumb_url = None
            if thumb_field:
                thumb_url = self._extract_field(item, thumb_field)
            else:
                for candidate in ("thumbnail_url", "thumb_url", "thumb", "thumbnail"):
                    val = self._extract_field(item, candidate)
                    if val and isinstance(val, str):
                        thumb_url = val
                        break
            if not thumb_url:
                thumb_url = img_url

            title = self._extract_field(item, title_field, f"Wallpaper #{idx + 1}")
            w_id = str(self._extract_field(item, "id", f"{self._pid}-{idx}"))
            w = 0
            h = 0
            try:
                w = int(self._extract_field(item, "width", 0) or 0)
                h = int(self._extract_field(item, "height", 0) or 0)
            except Exception:
                pass

            wallpapers.append(
                Wallpaper(
                    id=f"{self._pid}-{w_id}",
                    provider_id=self._pid,
                    provider_name=self._name,
                    title=str(title),
                    image_url=str(img_url),
                    thumbnail_url=str(thumb_url),
                    source_url=str(img_url),
                    width=w,
                    height=h,
                )
            )
        return wallpapers


def validate_custom_source(cfg: Dict[str, Any]) -> Tuple[bool, str, Dict[str, bool]]:
    """Test and validate a custom source configuration.
    
    Returns (success: bool, status_message: str, details: dict).
    """
    stype = cfg.get("type", "json_feed")
    url = cfg.get("url", "").strip()
    if not url:
        return False, "URL or path is required.", {}

    details = {
        "reachable": False,
        "format_recognized": False,
        "image_field_detected": False,
        "pagination_detected": False,
    }

    if stype == "local_folder":
        folder = Path(url)
        if folder.is_dir():
            details["reachable"] = True
            details["format_recognized"] = True
            valid_exts = (".jpg", ".jpeg", ".png", ".webp")
            imgs = [p for p in folder.rglob("*") if p.suffix.lower() in valid_exts]
            if imgs:
                details["image_field_detected"] = True
                return True, f"Found {len(imgs)} local images in folder.", details
            return True, "Folder is accessible (no images found yet).", details
        return False, f"Folder does not exist or is not a directory: {url}", details

    # Remote HTTP tests
    safe, msg = is_safe_url(url)
    if not safe:
        return False, f"Unsafe URL: {msg}", details

    try:
        provider = CustomWallpaperProvider(cfg)
        wallpapers = provider.get_featured(page=1)
        details["reachable"] = True
        details["format_recognized"] = True
        if wallpapers:
            details["image_field_detected"] = True
            details["pagination_detected"] = "{page}" in url or "page" in cfg.get("page_param", "page")
            return True, f"Connection successful! Detected {len(wallpapers)} wallpapers in feed.", details
        return True, "Source reached successfully, but no wallpapers matched configured fields.", details
    except Exception as exc:
        return False, f"Could not connect: {exc}", details
