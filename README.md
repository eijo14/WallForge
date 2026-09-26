# WallForge ◈

<div align="center">
  <img src="packaging/icons/wallforge_128x128.png" alt="WallForge Logo" width="128" height="128" />
  <h3>Modern Pixel Wallpaper Engine & Multi-Source Desktop Background Manager</h3>
  <p>Fast, lightweight, privacy-respecting, and cross-platform desktop wallpaper aggregator with a distinctive Retro-Tech / Modern Pixel aesthetic.</p>
</div>

---

## Highlights

- ◈ **Multi-Source Aggregator**: Seamlessly search, filter, and discover wallpapers across multiple independent providers simultaneously without fear of single-point network failure.
- ◈ **Modern Pixel / Retro-Tech Aesthetic**: Clean desktop interface with custom pixel-art motifs, scanline accents, responsive cards, and dynamic themes (**Dark**, **Light**, **Midnight**, and **Pixel Green**).
- ◈ **Instant Two-Stage Previews**: Preview dialog opens in under 15ms by displaying cached 320px thumbnails immediately while fetching or decoding 1280px WebP previews in the background. Full-resolution originals are downloaded only when requested.
- ◈ **Unified Cross-Platform Engine**:
  - **Linux**: Native backends for Hyprland (`hyprpaper`), GNOME (`gsettings`), KDE Plasma (`plasma-apply-wallpaperimage`), Sway (`swaymsg`/`swaybg`), XFCE (`xfconf-query`), Cinnamon, MATE, and Generic X11/Wayland (`swww`, `feh`, `nitrogen`).
  - **Windows 10 / 11**: Native Win32 `SystemParametersInfoW` with automatic display style and multi-monitor handling.
  - **macOS (Big Sur, Monterey, Ventura, Sonoma, Sequoia)**: Native AppleScript via `osascript` targeting all connected desktop spaces.
- ◈ **Graceful Degradation**: Running on an unsupported OS or sandboxed environment? WallForge lets you browse, search, preview, favorite, and download wallpapers with 100% functionality even when desktop setting is restricted.
- ◈ **Low RAM Footprint**: Engineered with a 3-tier cache (Metadata TTL, downscaled WebP thumbnails, and on-demand full wallpapers). Active RAM stays between 35–65 MB.
- ◈ **Offline-First & Auto-Rotation**: Browse previously cached collections and favorited wallpapers completely offline. Automatic periodic rotation seamlessly falls back to offline pools if disconnected.

---

## Supported Providers

| Provider | Access Mode | Content Description |
| :--- | :--- | :--- |
| **ArchImg** | Public Manifest | Curated 4K minimalist Arch Linux and Hyprland ricing wallpapers. |
| **Wallhaven** | Public API | The premier anime, general, people, 4K/8K, and ultrawide wallpaper archive. |
| **Bing Daily** | Public JSON Feed | Daily landscape, architectural, and nature photography from Microsoft Bing. |
| **NASA APOD** | Open NASA API | Daily astronomy, deep-space telescope, and nebula high-resolution imagery. |
| **Openverse** | Public API | 700M+ Creative Commons and Public Domain cultural and artistic works. |
| **Wikimedia Commons** | MediaWiki API | Curated Featured Pictures and Pictures of the Day with full CC attribution. |
| **GitHub Walls** | Raw Content | DenverCoder1's minimalist flat-art curated wallpaper collection. |
| **Local Collections** | Filesystem | Scan and apply user wallpaper folders and personal archives. |
| **Keyed Sources** | API Key (Optional) | Optional integration with Unsplash, Pexels, and Pixabay. |

---

## Platform Support Matrix

| Platform / Desktop | Backend Identifier | Setter Mechanism | Multi-Monitor | Status |
| :--- | :--- | :--- | :---: | :---: |
| **Linux (Hyprland)** | `hyprland` | `hyprctl` / `hyprpaper` IPC + conf sync | Yes | **Tier 1** |
| **Linux (GNOME)** | `gnome` | `gsettings` (`picture-uri` + dark) | Partial | **Tier 1** |
| **Linux (KDE Plasma)** | `kde` | `plasma-apply-wallpaperimage` | Yes | **Tier 1** |
| **Linux (Sway)** | `sway` | `swaymsg` / `swaybg` | Yes | **Tier 1** |
| **Linux (XFCE)** | `xfce` | `xfconf-query` | Yes | **Tier 1** |
| **Linux (Cinnamon)** | `cinnamon` | `gsettings` (`org.cinnamon.desktop`) | Partial | **Tier 1** |
| **Linux (MATE)** | `mate` | `gsettings` (`org.mate.background`) | Partial | **Tier 1** |
| **Linux (Generic)** | `generic` | `swww` / `feh` / `nitrogen` / `swaybg` | Depends | **Tier 1** |
| **Windows 10 / 11** | `windows` | Win32 `SystemParametersInfoW` + Registry | Yes | **Tier 1** |
| **macOS** | `macos` | AppleScript via `osascript` / `System Events` | Yes | **Tier 1** |
| **Headless / Other** | `unavailable` | Graceful Degradation (Browse/Download) | N/A | **Graceful** |

For deep details, see [PLATFORM_SUPPORT.md](PLATFORM_SUPPORT.md).

---

## Quickstart & Installation

See [INSTALL.md](INSTALL.md) for full instructions across all operating systems.

### Linux (Flatpak)
```bash
flatpak install flathub org.wallforge.app
flatpak run org.wallforge.app
```

### Linux (Source / Virtualenv)
```bash
git clone https://github.com/eijofrancis/wallforge.git
cd wallforge
pip install -e .
python3 run.py
```

### Windows & macOS
Prebuilt installers and portable bundles are available under [Releases](https://github.com/eijofrancis/wallforge/releases).

---

## Keyboard Shortcuts

- `Ctrl + /` : Jump focus to Search Entry from any screen
- `Esc` (in Search view) : Unfocus search bar and return to Dashboard
- `Esc` (in Preview dialog) : Close preview modal
- `Ctrl + Q` : Quit application

---

## Architecture

WallForge follows clean software engineering principles:

```
wallforge/
├── wallpaper_engine/
│   ├── core/
│   │   ├── paths.py             # Cross-platform XDG/Windows/macOS PathManager
│   │   ├── cache_manager.py     # 3-tier low-RAM cache (meta, thumbs, previews)
│   │   ├── models.py            # Normalized Wallpaper and Capability models
│   │   ├── search_service.py    # Multi-provider concurrent progressive aggregator
│   │   ├── rotation_service.py  # Background wallpaper rotation with offline recovery
│   │   ├── source_manager.py    # Source configuration & credential storage
│   │   └── theme_manager.py     # Dynamic theme tokens & GTK4 CSS generation
│   ├── providers/               # Decoupled wallpaper providers (ArchImg, Wallhaven, etc.)
│   ├── setters/                 # Platform backends (Windows, macOS, Hyprland, GNOME, etc.)
│   └── ui/                      # GTK4 / Libadwaita responsive interface
├── packaging/                   # Flatpak, AppImage, PyInstaller, Inno Setup, icons
└── tests/                       # Complete regression and cross-platform test suites
```

---

## License

Released under the [MIT License](LICENSE). Copyright © 2026 Eijo Francis.
