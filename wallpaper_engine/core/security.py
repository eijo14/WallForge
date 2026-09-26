"""Security validation utilities for URL and path handling."""

import ipaddress
from pathlib import Path
import re
import socket
from typing import Optional, Set, Tuple
import urllib.parse

SAFE_SCHEMES: Set[str] = {"http", "https"}
BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}
ALLOWED_IMAGE_EXTENSIONS: Set[str] = {"jpg", "jpeg", "png", "webp", "bmp"}

MAX_THUMBNAIL_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_PREVIEW_BYTES = 15 * 1024 * 1024     # 15 MB
MAX_WALLPAPER_BYTES = 60 * 1024 * 1024   # 60 MB


def is_safe_url(url: str, allow_private: bool = False) -> Tuple[bool, str]:
    """Validate remote URL for safe scheme and SSRF protection.
    
    Rejects:
      - Non-HTTP/HTTPS schemes (e.g. file://, ftp://, gopher://)
      - Loopback addresses (127.0.0.0/8, ::1)
      - Link-local and cloud metadata addresses (169.254.0.0/16, fe80::/10)
      - Private RFC 1918 / RFC 4193 addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
      - Broadcast, unspecified, and reserved IPs
      - localhost and local hostnames
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or invalid."

    url = url.strip()
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    scheme = parsed.scheme.lower()
    if scheme not in SAFE_SCHEMES:
        return False, f"Disallowed URL scheme '{scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid hostname."

    hostname_lower = hostname.lower()

    if not allow_private:
        # Check blocked hostnames
        if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.endswith(
            (".local", ".internal", ".localhost", ".localdomain")
        ):
            return False, f"Access to local/private host '{hostname}' is blocked."

        # Check IP literal
        try:
            ip = ipaddress.ip_address(hostname_lower)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
                or ip.is_multicast
            ):
                return False, f"Access to private or reserved IP '{ip}' is blocked."
        except ValueError:
            # Domain name; check resolved addresses if DNS is reachable
            try:
                resolved = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
                for res in resolved:
                    sockaddr = res[4]
                    ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if (
                        resolved_ip.is_loopback
                        or resolved_ip.is_private
                        or resolved_ip.is_link_local
                        or resolved_ip.is_reserved
                        or resolved_ip.is_unspecified
                        or resolved_ip.is_multicast
                    ):
                        return False, f"Hostname '{hostname}' resolves to private/reserved IP '{resolved_ip}'."
            except (socket.gaierror, socket.timeout, OSError):
                # DNS failure or offline environment; allow valid syntax domain to proceed to HTTP request
                pass

    return True, "URL is valid."


def sanitize_extension(extension: str, default: str = "jpg") -> str:
    """Sanitize file extension to prevent path traversal and restrict to image types."""
    if not extension:
        return default
    # Strip dots and non-alphanumeric characters
    clean = re.sub(r"[^a-zA-Z0-9]", "", str(extension)).lower()
    if clean in ALLOWED_IMAGE_EXTENSIONS:
        return clean
    return default


def is_safe_path(target_path: Path, allowed_parent: Path) -> bool:
    """Ensure target path is strictly contained within allowed parent directory."""
    try:
        resolved_target = target_path.resolve()
        resolved_parent = allowed_parent.resolve()
        return resolved_target.is_relative_to(resolved_parent)
    except Exception:
        return False
