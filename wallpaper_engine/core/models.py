"""Normalized models, capability flags, and filter definitions."""

from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import Any, List, Optional


class Capability(Flag):
    """Capabilities that a wallpaper provider may support."""
    SEARCH = auto()               # Server-side search support
    FEATURED = auto()             # Curated / popular / trending feed
    CATEGORIES = auto()           # Categorized collections
    TAGS = auto()                 # Tag-based filtering
    RESOLUTION_FILTER = auto()    # Server-side resolution filtering
    ASPECT_RATIO_FILTER = auto()  # Aspect ratio filtering
    PAGINATION = auto()           # Paginated results
    RANDOM = auto()               # Native random wallpaper selection
    DIRECT_IMAGE_URL = auto()     # Direct high-res image download URL
    LICENSE_METADATA = auto()     # Explicit license information
    AUTHOR_METADATA = auto()      # Author / photographer attribution


class SourceStatus(Enum):
    """Health and operational status of a provider."""
    ONLINE = "Online"
    DEGRADED = "Degraded"
    OFFLINE = "Offline"
    DISABLED = "Disabled"
    NOT_CONFIGURED = "Not Configured"


@dataclass
class Wallpaper:
    """Normalized wallpaper model returned by all providers."""
    id: str                         # Provider-prefixed unique ID (e.g., 'archimg-019')
    provider_id: str                # Identifier of the provider (e.g., 'archimg')
    provider_name: str              # User-readable name (e.g., 'ArchImg')
    title: str                      # User-readable title
    description: str = ""           # Caption, explanation, or prompt
    thumbnail_url: str = ""         # Direct URL or local path for thumbnail display
    image_url: str = ""             # Direct full-resolution image URL
    source_url: str = ""            # Upstream landing page URL
    
    width: int = 0                  # Pixel width (0 if unknown/pending)
    height: int = 0                 # Pixel height (0 if unknown/pending)
    aspect_ratio: str = "Unknown"   # Normalized aspect ratio (e.g., '16:9', '21:9', '1:1')
    file_size: int = 0              # In bytes (0 if unknown)
    
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    author: str = "Unknown"         # Artist / photographer / uploader
    license: str = "Unknown"        # License name (e.g., 'CC BY-SA 4.0', 'Unknown')
    license_url: str = ""           # URL to license terms if available
    attribution_required: bool = False
    
    created_at: str = ""
    published_at: str = ""
    download_location: str = ""     # Optional upstream API download tracking endpoint (e.g. Unsplash)

    @property
    def resolution_str(self) -> str:
        """Formatted resolution string (e.g. '3840x2160' or 'Unknown')."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "Unknown"

    @property
    def is_4k_or_more(self) -> bool:
        """Check if resolution is at least 4K (3840x2160 or equivalent pixel count)."""
        return (self.width * self.height) >= (3840 * 2160)

    @property
    def is_1440p_or_more(self) -> bool:
        """Check if resolution is at least 1440p (2560x1440)."""
        return (self.width * self.height) >= (2560 * 1440)

    @property
    def is_1080p_or_more(self) -> bool:
        """Check if resolution is at least 1080p (1920x1080)."""
        return (self.width * self.height) >= (1920 * 1080)

    def to_dict(self) -> dict:
        """Serialize wallpaper model to JSON-compatible dictionary."""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "title": self.title,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "image_url": self.image_url,
            "source_url": self.source_url,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "file_size": self.file_size,
            "tags": list(self.tags),
            "categories": list(self.categories),
            "author": self.author,
            "license": self.license,
            "license_url": self.license_url,
            "attribution_required": self.attribution_required,
            "created_at": self.created_at,
            "published_at": self.published_at,
            "download_location": self.download_location,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Wallpaper":
        """Deserialize wallpaper model from dictionary."""
        return cls(
            id=data.get("id", ""),
            provider_id=data.get("provider_id", ""),
            provider_name=data.get("provider_name", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            image_url=data.get("image_url", ""),
            source_url=data.get("source_url", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            aspect_ratio=data.get("aspect_ratio", "Unknown"),
            file_size=data.get("file_size", 0),
            tags=list(data.get("tags", [])),
            categories=list(data.get("categories", [])),
            author=data.get("author", "Unknown"),
            license=data.get("license", "Unknown"),
            license_url=data.get("license_url", ""),
            attribution_required=data.get("attribution_required", False),
            created_at=data.get("created_at", ""),
            published_at=data.get("published_at", ""),
            download_location=data.get("download_location", ""),
        )


@dataclass
class SearchFilter:
    """Unified search criteria passed to providers."""
    query: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    min_width: int = 0
    min_height: int = 0
    aspect_ratio: str = ""          # e.g., '16:9', '21:9', '16:10', '1:1', 'portrait'
    sorting: str = "relevance"       # 'relevance', 'newest', 'resolution', 'random'
    page: int = 1
    page_size: int = 24


@dataclass
class SettingField:
    """A provider-owned configuration parameter."""
    key: str
    label: str
    field_type: str                 # 'string', 'password', 'bool', 'int', 'choice'
    default: Any
    description: str = ""
    options: List[str] = field(default_factory=list)  # For 'choice' field_type
