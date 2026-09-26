"""Curated minimalist wallpapers from DenverCoder1's GitHub collection."""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import urllib.request

from wallpaper_engine.core.models import (
    Capability,
    SearchFilter,
    SettingField,
    Wallpaper,
)
from wallpaper_engine.core.provider_base import WallpaperProvider


class GitHubWallsProvider(WallpaperProvider):
    """Provider for curated minimalist wallpapers hosted on GitHub.
    
    Access Type: TYPE B (Public Git Tree / Raw CDN)
    Uses GitHub Git Tree API to discover hundreds of high-resolution
    flat art and minimalist wallpapers.
    """

    TREE_URL = "https://api.github.com/repos/DenverCoder1/minimalistic-wallpaper-collection/git/trees/main?recursive=1"
    RAW_BASE = "https://raw.githubusercontent.com/DenverCoder1/minimalistic-wallpaper-collection/main/"
    REPO_URL = "https://github.com/DenverCoder1/minimalistic-wallpaper-collection"

    @property
    def provider_id(self) -> str:
        return "github_minimal"

    @property
    def provider_name(self) -> str:
        return "Minimalist GitHub"

    @property
    def homepage_url(self) -> str:
        return self.REPO_URL

    @property
    def capabilities(self) -> Capability:
        return (
            Capability.FEATURED
            | Capability.SEARCH
            | Capability.CATEGORIES
            | Capability.TAGS
            | Capability.DIRECT_IMAGE_URL
            | Capability.RANDOM
        )

    def _fetch_tree(self) -> List[str]:
        cache_key = "github_minimal_tree"
        if self.cache_manager:
            cached = self.cache_manager.get_meta(cache_key, max_age_seconds=86400 * 7)
            if cached and isinstance(cached, list):
                return cached

        req = urllib.request.Request(
            self.TREE_URL,
            headers={"User-Agent": "PersonalWallpaperEngine/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tree = data.get("tree", [])
            images = [
                item["path"] for item in tree
                if item.get("path", "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                and not item.get("path", "").startswith(".")
            ]

            if self.cache_manager and images:
                self.cache_manager.set_meta(cache_key, images)
            self.record_success()
            return images
        except Exception as exc:
            self.record_failure(f"Failed to fetch GitHub tree: {exc}")
            if self.cache_manager:
                fallback = self.cache_manager.get_meta(cache_key, max_age_seconds=86400 * 30)
                if fallback:
                    return fallback
            raise

    def _to_wallpaper(self, path: str) -> Wallpaper:
        stem = Path(path).stem
        clean_title = re.sub(r"^[A-Za-z0-9_-]+_", "", stem)  # Remove ID prefixes if any
        title = clean_title.replace("-", " ").replace("_", " ").title()

        tokens = [t.lower() for t in re.split(r"[-_ ]+", stem) if len(t) > 2]
        tags = list(set(["minimalist", "minimal", "flatart"] + tokens[:6]))

        image_url = f"{self.RAW_BASE}{path}"
        slug = re.sub(r"[^a-zA-Z0-9_-]", "", stem)

        return Wallpaper(
            id=f"ghmin-{slug[:24]}",
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            title=title[:40],
            description=f"Curated Minimalist Wallpaper ({Path(path).name})",
            thumbnail_url=image_url,
            image_url=image_url,
            source_url=f"{self.REPO_URL}/blob/main/{path}",
            width=0,
            height=0,
            aspect_ratio="16:9",
            tags=tags,
            categories=["Minimalist", "Flat Art", "Vector"],
            author="Community Artist",
            license="Open Source / Community",
            license_url=f"{self.REPO_URL}/blob/main/LICENSE",
            attribution_required=False,
        )

    def get_featured(self, page: int = 1) -> List[Wallpaper]:
        tree = self._fetch_tree()
        page_size = 24
        start = (page - 1) * page_size
        end = start + page_size
        return [self._to_wallpaper(p) for p in tree[start:end]]

    def search(self, filters: SearchFilter) -> List[Wallpaper]:
        tree = self._fetch_tree()
        query = filters.query.lower().strip()
        matched = []

        for p in tree:
            wp = self._to_wallpaper(p)
            if not query:
                matched.append(wp)
            elif (
                query in wp.title.lower()
                or query in p.lower()
                or any(query in t for t in wp.tags)
            ):
                matched.append(wp)

        page_size = filters.page_size or 24
        start = (filters.page - 1) * page_size
        end = start + page_size
        return matched[start:end]

    def get_categories(self) -> List[str]:
        return ["Minimalist", "Flat Art", "Vector"]
