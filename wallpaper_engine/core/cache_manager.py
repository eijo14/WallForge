"""Three-tier cache manager: metadata, downscaled thumbnails, and full wallpapers."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Optional, Tuple
import urllib.request

from PIL import Image

from wallpaper_engine.core.security import (
    MAX_PREVIEW_BYTES,
    MAX_THUMBNAIL_BYTES,
    MAX_WALLPAPER_BYTES,
    is_safe_path,
    is_safe_url,
    sanitize_extension,
)

# Protect against decompression bomb denial-of-service
Image.MAX_IMAGE_PIXELS = 100_000_000


class CacheManager:
    """Manages local caching following XDG conventions and low-RAM requirements.
    
    Tiers:
      1. Meta Cache: Provider manifests and API responses with TTL.
      2. Thumbnails Cache: 320px downscaled WebP/JPEG thumbnails for fast, low-RAM GTK grid rendering.
      3. Previews Cache: 1280px downscaled WebP images for modal dialog preview without full download.
      4. Wallpapers Storage: Full-resolution downloaded original wallpapers.
    """

    def __init__(
        self,
        base_cache_dir: Optional[Path] = None,
        base_data_dir: Optional[Path] = None,
        max_cache_mb: int = 500,
    ) -> None:
        import threading
        from wallpaper_engine.core.paths import PathManager

        self.path_mgr = PathManager(
            override_cache_dir=base_cache_dir,
            override_data_dir=base_data_dir,
        )
        self.cache_dir = self.path_mgr.cache_dir
        self.data_dir = self.path_mgr.data_dir
        self.max_cache_bytes = max_cache_mb * 1024 * 1024

        self.meta_dir = self.path_mgr.meta_dir
        self.thumbs_dir = self.path_mgr.thumbs_dir
        self.previews_dir = self.path_mgr.previews_dir
        self.wallpapers_dir = self.path_mgr.wallpapers_dir
        self.logs_dir = self.path_mgr.logs_dir

        self._preview_meta_lock = threading.Lock()
        self._in_flight_previews: dict = {}

        self.path_mgr.ensure_directories()

    def get_hash(self, key: str) -> str:
        """Generate deterministic hex hash for a key or URL."""
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

    # -------------------------------------------------------------------------
    # Tier 1: Metadata Cache
    # -------------------------------------------------------------------------
    def get_meta(self, key: str, max_age_seconds: int = 3600) -> Optional[Any]:
        """Retrieve cached metadata if not expired."""
        h = self.get_hash(key)
        path = self.meta_dir / f"{h}.json"
        if not path.is_file():
            return None

        try:
            stat = path.stat()
            if time.time() - stat.st_mtime > max_age_seconds:
                return None  # Expired
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def set_meta(self, key: str, data: Any) -> None:
        """Cache metadata atomically."""
        h = self.get_hash(key)
        target = self.meta_dir / f"{h}.json"
        part = self.meta_dir / f"{h}.tmp"
        try:
            with open(part, "w", encoding="utf-8") as f:
                json.dump(data, f)
            part.replace(target)
        except Exception:
            if part.exists():
                part.unlink(missing_ok=True)

    # -------------------------------------------------------------------------
    # Tier 2: Thumbnail Cache (Low-RAM Optimization)
    # -------------------------------------------------------------------------
    def get_thumbnail_path(self, image_url: str) -> Optional[Path]:
        """Return local path to cached thumbnail if it exists."""
        h = self.get_hash(image_url)
        thumb_path = self.thumbs_dir / f"{h}.webp"
        if thumb_path.is_file():
            # Update access time for LRU
            thumb_path.touch(exist_ok=True)
            return thumb_path
        return None

    def create_thumbnail(self, source_path: Path, image_url: str, max_size: int = 320) -> Optional[Path]:
        """Generate and save a downscaled thumbnail from a local image file."""
        h = self.get_hash(image_url)
        target = self.thumbs_dir / f"{h}.webp"
        part = self.thumbs_dir / f"{h}.tmp.webp"

        try:
            with Image.open(source_path) as img:
                # Downscale preserving aspect ratio
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                img.save(part, format="WEBP", quality=85)

            part.replace(target)
            self.enforce_cache_limit()
            return target
        except Exception:
            if part.exists():
                part.unlink(missing_ok=True)
            return None

    def create_preview_from_file(self, source_path: Path, preview_url: str, max_size: int = 1280) -> Optional[Path]:
        """Generate and save a downscaled 1280px preview WebP from a local image file off-thread."""
        h = self.get_hash(preview_url)
        target = self.previews_dir / f"{h}.webp"
        if target.is_file():
            return target
        part = self.previews_dir / f"{h}.tmp.webp"
        try:
            with Image.open(source_path) as img:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                img.save(part, format="WEBP", quality=85)
            part.replace(target)
            self.enforce_cache_limit()
            return target
        except Exception:
            if part.is_file():
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass
            return None

    def fetch_and_cache_thumbnail(
        self,
        thumbnail_url: str,
        timeout: int = 15,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) WallForge/1.0",
    ) -> Optional[Path]:
        """Download or generate local thumbnail without loading large images into UI."""
        if not thumbnail_url:
            return None

        # Handle local files
        if thumbnail_url.startswith("file://"):
            local_p = Path(thumbnail_url[7:])
            if local_p.is_file():
                return self.create_thumbnail(local_p, thumbnail_url)
            return None

        safe, _ = is_safe_url(thumbnail_url)
        if not safe:
            return None

        existing = self.get_thumbnail_path(thumbnail_url)
        if existing:
            return existing

        h = self.get_hash(thumbnail_url)
        temp_file = self.thumbs_dir / f"{h}.raw.part"
        target_webp = self.thumbs_dir / f"{h}.webp"

        try:
            req = urllib.request.Request(
                thumbnail_url,
                headers={"User-Agent": user_agent},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_length = resp.getheader("Content-Length")
                if content_length and int(content_length) > MAX_THUMBNAIL_BYTES:
                    return None

                bytes_received = 0
                chunk_size = 65536
                with open(temp_file, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                        if bytes_received > MAX_THUMBNAIL_BYTES:
                            raise ValueError(f"Thumbnail exceeded {MAX_THUMBNAIL_BYTES} bytes limit")

            # Create downscaled WebP thumbnail
            with Image.open(temp_file) as img:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")
                img.thumbnail((320, 320), Image.Resampling.LANCZOS)
                img.save(target_webp, format="WEBP", quality=85)

            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

            self.enforce_cache_limit()
            return target_webp
        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            if target_webp.exists() and not target_webp.is_file():
                target_webp.unlink(missing_ok=True)
            return None

    # -------------------------------------------------------------------------
    # Tier 3: Preview Cache (Modal Dialog Low-RAM Optimization)
    # -------------------------------------------------------------------------
    def get_preview_path(self, image_url: str) -> Optional[Path]:
        """Return local path to cached preview image (downscaled, max 1280px) if it exists."""
        h = self.get_hash(image_url)
        preview_path = self.previews_dir / f"{h}.webp"
        if preview_path.is_file():
            preview_path.touch(exist_ok=True)
            return preview_path
        return None

    def fetch_and_cache_preview(
        self,
        image_url: str,
        timeout: Optional[float] = None,
        connect_timeout: float = 3.0,
        read_timeout: float = 8.0,
        max_size: int = 1280,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) WallForge/1.0",
    ) -> Tuple[bool, Optional[Path], str]:
        """Fetch remote image and downscale to a lightweight preview without saving to permanent wallpapers."""
        if not image_url:
            return False, None, "Empty image URL."

        if timeout is not None:
            read_timeout = float(timeout)

        # Handle file:// schemes directly
        if image_url.startswith("file://"):
            local_p = Path(image_url[7:])
            if local_p.is_file():
                return True, local_p, "Local file ready."
            return False, None, f"Local file not found: {local_p}"

        safe, msg = is_safe_url(image_url)
        if not safe:
            return False, None, f"Unsafe URL: {msg}"

        # 1. If already cached in preview cache
        existing_preview = self.get_preview_path(image_url)
        if existing_preview:
            return True, existing_preview, "Cached preview available."

        # 2. If already downloaded in permanent wallpapers
        existing_wp = self.get_wallpaper_path(image_url)
        if existing_wp:
            return True, existing_wp, "Full wallpaper already downloaded."

        # 3. Deduplicate concurrent requests for the same wallpaper
        import threading
        with self._preview_meta_lock:
            existing_preview = self.get_preview_path(image_url)
            if existing_preview:
                return True, existing_preview, "Cached preview available."
            existing_wp = self.get_wallpaper_path(image_url)
            if existing_wp:
                return True, existing_wp, "Full wallpaper already downloaded."

            if image_url in self._in_flight_previews:
                event = self._in_flight_previews[image_url]
                in_flight = True
            else:
                event = threading.Event()
                self._in_flight_previews[image_url] = event
                in_flight = False

        if in_flight:
            # Wait for concurrent fetch to complete
            event.wait(timeout=connect_timeout + read_timeout + 2.0)
            existing = self.get_preview_path(image_url)
            if existing and existing.is_file():
                return True, existing, "Cached preview available."
            return False, None, "Concurrent preview download did not produce a file."

        h = self.get_hash(image_url)
        temp_file = self.previews_dir / f"{h}.raw.part"
        target_webp = self.previews_dir / f"{h}.webp"

        print(f"[PREVIEW] preview URL: {image_url}", flush=True)
        print("[PREVIEW] request started", flush=True)

        try:
            t_req_start = time.perf_counter()
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": user_agent},
            )
            # Enforce connect timeout
            with urllib.request.urlopen(req, timeout=connect_timeout) as resp:
                content_length = resp.getheader("Content-Length")
                if content_length and int(content_length) > MAX_PREVIEW_BYTES:
                    return False, None, f"Preview exceeds maximum size limit ({MAX_PREVIEW_BYTES} bytes)."

                sock = getattr(resp, "fp", None)
                if sock and hasattr(sock, "raw") and hasattr(sock.raw, "_sock") and sock.raw._sock:
                    sock.raw._sock.settimeout(read_timeout)

                raw_chunks = []
                bytes_received = 0
                deadline = time.perf_counter() + read_timeout
                while True:
                    if time.perf_counter() > deadline:
                        raise TimeoutError(f"Preview download exceeded {read_timeout}s read timeout")
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    raw_chunks.append(chunk)
                    bytes_received += len(chunk)
                    if bytes_received > MAX_PREVIEW_BYTES:
                        raise ValueError(f"Preview download exceeded {MAX_PREVIEW_BYTES} bytes limit")

                raw_data = b"".join(raw_chunks)
                req_ms = (time.perf_counter() - t_req_start) * 1000
                print(f"[PREVIEW] response received: {bytes_received} bytes, {req_ms:.1f} ms", flush=True)

            t_dec_start = time.perf_counter()
            print("[PREVIEW] decode started", flush=True)
            import io
            with Image.open(io.BytesIO(raw_data)) as img:
                w, h_dim = img.size
                dec_ms = (time.perf_counter() - t_dec_start) * 1000
                print(f"[PREVIEW] decode finished: {w}x{h_dim}, {dec_ms:.1f} ms", flush=True)

                t_res_start = time.perf_counter()
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                temp_webp = self.previews_dir / f"{h}.tmp.webp"
                img.save(temp_webp, format="WEBP", quality=85)
                temp_webp.replace(target_webp)
                res_ms = (time.perf_counter() - t_res_start) * 1000
                print(f"[PREVIEW] resize finished, {res_ms:.1f} ms", flush=True)

            self.enforce_cache_limit()
            return True, target_webp, "Preview loaded successfully."
        except Exception as exc:
            print(f"[PREVIEW] HTTP or decode error: {exc}", flush=True)
            return False, None, f"Failed to fetch preview: {exc}"
        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            with self._preview_meta_lock:
                event.set()
                self._in_flight_previews.pop(image_url, None)

    # -------------------------------------------------------------------------
    # Tier 4: Full Wallpapers Storage
    # -------------------------------------------------------------------------
    def get_wallpaper_path(self, image_url: str, extension: str = "jpg") -> Optional[Path]:
        """Check if full wallpaper is already saved locally."""
        h = self.get_hash(image_url)
        clean_ext = sanitize_extension(extension)
        # Check common extensions
        for ext in (clean_ext, "jpg", "png", "webp", "jpeg", "bmp"):
            path = (self.wallpapers_dir / f"{h}.{ext}").resolve()
            if is_safe_path(path, self.wallpapers_dir) and path.is_file():
                return path
        return None

    def download_wallpaper(
        self,
        image_url: str,
        extension: str = "jpg",
        timeout: int = 45,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) WallForge/1.0",
        progress_callback=None,
    ) -> Tuple[bool, Optional[Path], str]:
        """Download full-resolution wallpaper with atomic writing and image verification."""
        if not image_url:
            return False, None, "Empty image URL."

        safe, msg = is_safe_url(image_url)
        if not safe:
            return False, None, f"Unsafe URL: {msg}"

        clean_ext = sanitize_extension(extension)
        existing = self.get_wallpaper_path(image_url, clean_ext)
        if existing:
            return True, existing, "Already downloaded."

        h = self.get_hash(image_url)
        target = (self.wallpapers_dir / f"{h}.{clean_ext}").resolve()
        part = (self.wallpapers_dir / f"{h}.part").resolve()

        if not is_safe_path(target, self.wallpapers_dir) or not is_safe_path(part, self.wallpapers_dir):
            return False, None, "Invalid path traversal attempt."

        try:
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": user_agent},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                total_size = resp.getheader("Content-Length")
                total_bytes = int(total_size) if total_size else 0
                if total_bytes > MAX_WALLPAPER_BYTES:
                    return False, None, f"Wallpaper exceeds maximum size limit (60 MB)."

                downloaded = 0
                chunk_size = 65536

                with open(part, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > MAX_WALLPAPER_BYTES:
                            raise ValueError(f"Download exceeded {MAX_WALLPAPER_BYTES} bytes limit")
                        if progress_callback and total_bytes > 0:
                            progress_callback(downloaded, total_bytes)

            # Validate image with Pillow
            with Image.open(part) as img:
                img.verify()

            # Atomic move
            part.replace(target)

            # Also generate a thumbnail from this downloaded image if missing
            if not self.get_thumbnail_path(image_url):
                self.create_thumbnail(target, image_url)

            return True, target, "Download successful."
        except Exception as exc:
            if part.exists():
                part.unlink(missing_ok=True)
            return False, None, f"Download failed: {exc}"

    # -------------------------------------------------------------------------
    # Cache Size & Cleanup (LRU)
    # -------------------------------------------------------------------------
    def get_cache_size(self) -> int:
        """Calculate total bytes occupied by temporary cache (thumbs + previews + meta)."""
        total = 0
        for directory in (self.thumbs_dir, self.previews_dir, self.meta_dir):
            for entry in directory.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
        return total

    def enforce_cache_limit(self) -> None:
        """Evict oldest accessed cache files when cache limit is exceeded."""
        current_size = self.get_cache_size()
        if current_size <= self.max_cache_bytes:
            return

        # Collect files in thumbs, previews, and meta with their access times
        files = []
        for directory in (self.thumbs_dir, self.previews_dir, self.meta_dir):
            for entry in directory.iterdir():
                if entry.is_file():
                    try:
                        stat = entry.stat()
                        files.append((stat.st_atime, stat.st_size, entry))
                    except Exception:
                        pass

        # Sort oldest accessed first
        files.sort(key=lambda x: x[0])

        bytes_to_remove = current_size - (self.max_cache_bytes * 0.8)  # Free to 80% of limit
        removed_bytes = 0
        for _, size, path in files:
            if removed_bytes >= bytes_to_remove:
                break
            try:
                path.unlink(missing_ok=True)
                removed_bytes += size
            except Exception:
                pass

    def clear_cache(self) -> int:
        """Remove all temporary thumbnails, previews, and meta files without touching saved wallpapers."""
        removed_count = 0
        for directory in (self.thumbs_dir, self.previews_dir, self.meta_dir):
            for entry in directory.iterdir():
                if entry.is_file():
                    try:
                        entry.unlink()
                        removed_count += 1
                    except Exception:
                        pass
        return removed_count
