"""Security audit regression test suite verifying all audit fixes."""

import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter, Wallpaper
from wallpaper_engine.core.security import (
    MAX_PREVIEW_BYTES,
    MAX_THUMBNAIL_BYTES,
    MAX_WALLPAPER_BYTES,
    is_safe_path,
    is_safe_url,
    sanitize_extension,
)
from wallpaper_engine.providers.custom import CustomWallpaperProvider, validate_custom_source
from wallpaper_engine.providers.unsplash import UnsplashProvider, report_unsplash_download
from wallpaper_engine.providers.wikimedia import WikimediaProvider
from wallpaper_engine.setters.generic import GenericLinuxWallpaperSetter
from wallpaper_engine.setters.gnome import GNOMEWallpaperSetter
from wallpaper_engine.setters.hyprland import HyprlandWallpaperSetter
from wallpaper_engine.setters.macos import MacOSWallpaperSetter


class TestSecurityAuditRegressions(unittest.TestCase):
    """Verify security controls and fixes identified in the pre-release audit."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="wp_sec_audit_"))
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.cache_mgr = CacheManager(
            base_cache_dir=self.cache_dir,
            base_data_dir=self.data_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # CRIT-01: Bounded remote downloads
    # =========================================================================
    def test_thumbnail_download_limit_via_content_length(self):
        """Reject thumbnails early when Content-Length exceeds 10 MB."""
        mock_resp = MagicMock()
        mock_resp.getheader.side_effect = lambda h: "15000000" if h.lower() == "content-length" else None
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_resp
            result = self.cache_mgr.fetch_and_cache_thumbnail("https://example.com/huge_thumb.jpg")
            self.assertIsNone(result)

    def test_thumbnail_download_limit_mid_stream(self):
        """Abort and delete partial files when thumbnail response body exceeds 10 MB mid-stream."""
        # Simulated stream yielding chunks until > 10 MB
        chunk = b"X" * 1024 * 1024  # 1 MB chunk
        stream = io.BytesIO(chunk * 12)  # 12 MB total stream without Content-Length
        mock_resp = MagicMock()
        mock_resp.getheader.return_value = None
        mock_resp.read.side_effect = lambda size=65536: stream.read(size)

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_resp
            result = self.cache_mgr.fetch_and_cache_thumbnail("https://example.com/oversized_stream.jpg")
            self.assertIsNone(result)
            # Ensure no partial raw file is left behind on disk
            raw_parts = list(self.cache_mgr.thumbs_dir.glob("*.raw.part"))
            self.assertEqual(len(raw_parts), 0)

    def test_wallpaper_download_limit_via_content_length(self):
        """Reject wallpapers early when Content-Length exceeds 60 MB."""
        mock_resp = MagicMock()
        mock_resp.getheader.side_effect = lambda h: "70000000" if h.lower() == "content-length" else None
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_resp
            ok, path, msg = self.cache_mgr.download_wallpaper("https://example.com/oversized_wp.jpg")
            self.assertFalse(ok)
            self.assertIsNone(path)
            self.assertIn("60 MB", msg)

    def test_wallpaper_download_limit_mid_stream(self):
        """Abort and delete partial file when wallpaper download exceeds 60 MB mid-stream."""
        chunk = b"A" * (2 * 1024 * 1024)  # 2 MB chunks
        call_count = 0

        def read_mock(size=65536):
            nonlocal call_count
            call_count += 1
            if call_count > 35:  # 35 * 2 MB = 70 MB
                return b""
            return chunk

        mock_resp = MagicMock()
        mock_resp.getheader.return_value = None  # No Content-Length
        mock_resp.read.side_effect = read_mock

        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_resp
            ok, path, msg = self.cache_mgr.download_wallpaper("https://example.com/unbounded_wp.jpg")
            self.assertFalse(ok)
            self.assertIsNone(path)
            # Ensure partial file is removed
            parts = list(self.cache_mgr.wallpapers_dir.glob("*.part"))
            self.assertEqual(len(parts), 0)

    # =========================================================================
    # CRIT-02: macOS AppleScript injection prevention
    # =========================================================================
    def test_macos_setter_uses_positional_argv(self):
        """Ensure macOS setter passes wallpaper path via positional argv, never via string interpolation."""
        setter = MacOSWallpaperSetter()
        malicious_path = self.temp_dir / 'test" ; do shell script "evil" ; tell application "System Events" to --.jpg'
        malicious_path.write_bytes(b"dummy")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""

        with patch("platform.system", return_value="Darwin"), \
             patch("shutil.which", return_value="/usr/bin/osascript"), \
             patch("subprocess.run", return_value=mock_proc) as mock_sub:

            ok, msg = setter.apply_wallpaper(malicious_path)
            self.assertTrue(ok)
            mock_sub.assert_called_once()
            args = mock_sub.call_args[0][0]
            self.assertEqual(args[0], "osascript")
            self.assertEqual(args[1], "-e")
            script_body = args[2]
            # Ensure malicious path is NOT interpolated into script text
            self.assertNotIn("evil", script_body)
            self.assertNotIn(str(malicious_path.resolve()), script_body)
            # Ensure path is passed as positional argument
            self.assertEqual(args[3], str(malicious_path.resolve()))
            self.assertIn("on run argv", script_body)

    # =========================================================================
    # HIGH-01: Path traversal protection
    # =========================================================================
    def test_extension_sanitization(self):
        """Ensure extension sanitization strips path traversal and invalid extensions."""
        self.assertEqual(sanitize_extension("../../../etc/cron.d"), "jpg")
        self.assertEqual(sanitize_extension("png"), "png")
        self.assertEqual(sanitize_extension("..jpg.."), "jpg")
        self.assertEqual(sanitize_extension("exe"), "jpg")
        self.assertEqual(sanitize_extension("sh"), "jpg")
        self.assertEqual(sanitize_extension("WEBP"), "webp")

    def test_safe_path_containment(self):
        """Ensure paths outside the wallpapers directory are rejected."""
        safe_child = self.cache_mgr.wallpapers_dir / "safe.jpg"
        self.assertTrue(is_safe_path(safe_child, self.cache_mgr.wallpapers_dir))

        traversal_path = self.cache_mgr.wallpapers_dir / ".." / "system.file"
        self.assertFalse(is_safe_path(traversal_path, self.cache_mgr.wallpapers_dir))

    # =========================================================================
    # HIGH-02: URL validation & SSRF protection
    # =========================================================================
    def test_url_validation_safe_schemes(self):
        """Disallow file://, ftp://, gopher:// schemes for remote fetch."""
        self.assertFalse(is_safe_url("file:///etc/passwd")[0])
        self.assertFalse(is_safe_url("ftp://example.com/img.jpg")[0])
        self.assertFalse(is_safe_url("gopher://example.com/")[0])
        self.assertTrue(is_safe_url("https://example.com/wallpaper.jpg")[0])
        self.assertTrue(is_safe_url("http://example.com/wallpaper.jpg")[0])

    def test_url_validation_blocks_ssrf(self):
        """Disallow loopback, private ranges, and cloud metadata services."""
        # Loopback
        self.assertFalse(is_safe_url("http://127.0.0.1:8080/image.jpg")[0])
        self.assertFalse(is_safe_url("http://localhost/image.jpg")[0])
        self.assertFalse(is_safe_url("http://[::1]:8080/image.jpg")[0])

        # Cloud metadata service (169.254.169.254)
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/")[0])

        # RFC 1918 Private ranges
        self.assertFalse(is_safe_url("http://10.0.0.1/wallpaper.png")[0])
        self.assertFalse(is_safe_url("http://172.16.5.10/wallpaper.png")[0])
        self.assertFalse(is_safe_url("http://192.168.1.100/wallpaper.png")[0])

    def test_custom_provider_blocks_ssrf(self):
        """Ensure CustomWallpaperProvider rejects SSRF URLs in validate_custom_source."""
        cfg_ssrf = {
            "type": "json_feed",
            "url": "http://169.254.169.254/metadata",
        }
        ok, msg, details = validate_custom_source(cfg_ssrf)
        self.assertFalse(ok)
        self.assertIn("Unsafe URL", msg)

    # =========================================================================
    # HIGH-03: Subprocess timeouts
    # =========================================================================
    def test_hyprland_setter_handles_timeout(self):
        """Hyprland setter must handle subprocess TimeoutExpired without crashing."""
        setter = HyprlandWallpaperSetter()
        test_img = self.temp_dir / "test.jpg"
        test_img.write_bytes(b"dummy")

        with patch.object(setter, "_ensure_hyprpaper_daemon", return_value=True), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["hyprctl"], timeout=5)):
            ok, msg = setter.apply_wallpaper(test_img)
            self.assertFalse(ok)
            self.assertIn("timed out", msg)

    def test_gnome_setter_handles_timeout(self):
        """GNOME setter must handle subprocess TimeoutExpired without crashing."""
        setter = GNOMEWallpaperSetter()
        test_img = self.temp_dir / "test.jpg"
        test_img.write_bytes(b"dummy")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["gsettings"], timeout=5)):
            ok, msg = setter.apply_wallpaper(test_img)
            self.assertFalse(ok)
            self.assertIn("timed out", msg)

    # =========================================================================
    # HIGH-04: Unsplash API download tracking compliance
    # =========================================================================
    def test_unsplash_download_tracking(self):
        """UnsplashProvider preserves download_location and triggers tracking GET request."""
        provider = UnsplashProvider()
        provider.configure({"access_key": "test_access_key_123"})

        wp_item = {
            "id": "abc12345",
            "alt_description": "Desert Dunes",
            "urls": {"small": "https://images.unsplash.com/small.jpg", "full": "https://images.unsplash.com/full.jpg"},
            "links": {
                "html": "https://unsplash.com/photos/abc12345",
                "download_location": "https://api.unsplash.com/photos/abc12345/download",
            },
            "user": {"name": "Photographer"},
        }

        wp = provider._to_wallpaper(wp_item)
        self.assertEqual(wp.download_location, "https://api.unsplash.com/photos/abc12345/download")

        # Test asynchronous download reporting
        with patch("urllib.request.urlopen") as mock_open, \
             patch("urllib.request.Request") as mock_req:
            provider.track_download(wp)
            # Give background thread a moment to fire
            time.sleep(0.1)
            mock_req.assert_called()
            # Verify URL and Client-ID header were sent
            called_args = mock_req.call_args[0]
            self.assertEqual(called_args[0], "https://api.unsplash.com/photos/abc12345/download")
            headers = mock_req.call_args[1].get("headers", {})
            self.assertEqual(headers.get("Authorization"), "Client-ID test_access_key_123")

    # =========================================================================
    # MED-01: Pillow exception handling and decompression bombs
    # =========================================================================
    def test_corrupted_image_handling(self):
        """CacheManager handles corrupted image files gracefully."""
        corrupt_file = self.temp_dir / "corrupted.jpg"
        corrupt_file.write_bytes(b"not a real image")

        thumb = self.cache_mgr.create_thumbnail(corrupt_file, "https://example.com/corrupt.jpg")
        self.assertIsNone(thumb)

    # =========================================================================
    # MED-02: Wikimedia User-Agent compliance
    # =========================================================================
    def test_wikimedia_user_agent(self):
        """Wikimedia provider requests use compliant WallForge User-Agent header."""
        provider = WikimediaProvider()
        with patch("urllib.request.urlopen") as mock_open, \
             patch("urllib.request.Request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"query": {}}'
            mock_open.return_value.__enter__.return_value = mock_resp

            provider._request({"action": "query"})
            mock_req.assert_called_once()
            headers = mock_req.call_args[1].get("headers", {})
            self.assertEqual(headers.get("User-Agent"), "WallForge/1.0 (https://github.com/eijofrancis/wallforge)")

    # =========================================================================
    # MED-03: Hyprpaper newline injection prevention
    # =========================================================================
    def test_hyprpaper_newline_injection_rejected(self):
        """Hyprland setter rejects paths containing newlines to prevent config/command injection."""
        setter = HyprlandWallpaperSetter(hypr_config_dir=self.temp_dir / "hypr")
        malicious_path = Path(f"{self.temp_dir}/wall\nipc = off.jpg")

        ok, msg = setter.apply_wallpaper(malicious_path)
        self.assertFalse(ok)
        self.assertIn("newline", msg.lower())

    # =========================================================================
    # MED-04: pyproject.toml dependencies
    # =========================================================================
    def test_pyproject_dependency_versions(self):
        """pyproject.toml must declare secure minimum versions for requests and Pillow."""
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        self.assertIn("requests>=2.32.3", content)
        self.assertIn("Pillow>=10.3.0", content)

    # =========================================================================
    # MED-05: Repository governance files
    # =========================================================================
    def test_governance_files_exist(self):
        """SECURITY.md and CONTRIBUTING.md must be present in repository root."""
        root_dir = Path(__file__).resolve().parent.parent
        sec_file = root_dir / "SECURITY.md"
        contrib_file = root_dir / "CONTRIBUTING.md"

        self.assertTrue(sec_file.is_file(), "SECURITY.md missing")
        self.assertTrue(contrib_file.is_file(), "CONTRIBUTING.md missing")
        self.assertGreater(sec_file.stat().st_size, 100)
        self.assertGreater(contrib_file.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
