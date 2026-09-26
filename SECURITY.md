# Security Policy

## Supported Versions

Only the latest release of WallForge receives security updates and vulnerability patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of WallForge seriously. If you discover a vulnerability or potential security concern, please follow responsible disclosure guidelines:

1. **Do not create a public GitHub issue.**
2. Report the vulnerability privately via [GitHub Security Advisories](https://github.com/eijofrancis/wallforge/security/advisories/new) or by emailing the project maintainer at `security@wallforge.dev` (or the repository owner).
3. Include detailed steps to reproduce the issue, including:
   - Operating system and desktop environment.
   - WallForge version.
   - Proof-of-concept payload, URL, or script (if applicable).
   - Expected vs. actual behavior.

We strive to acknowledge receipt of vulnerability reports within 48 hours and provide updates on triage and mitigation progress.

## Security Architecture & Defenses

WallForge incorporates defenses designed to prevent common desktop application vulnerabilities:
- **Download Boundaries**: Strict file size limits on remote resources (10 MB for thumbnails, 15 MB for previews, 60 MB for full wallpapers) enforced during chunked streaming.
- **SSRF Protection**: Prohibits requests to loopback addresses, local networks (RFC 1918 / RFC 4193), link-local addresses, and cloud provider metadata services (e.g. `169.254.169.254`).
- **Path Traversal Prevention**: File extensions and local cache paths are strictly sanitized and restricted to designated application directories (`is_relative_to` checks).
- **Process & Command Safety**: Command-line invocations never interpolate untrusted strings into shell or script interpreters (e.g., AppleScript uses positional `argv` arrays; hyprpaper rejects paths with newline control characters).
- **Decompression Bomb Protection**: Pillow limits maximum pixel decompression to prevent memory exhaustion attacks.
