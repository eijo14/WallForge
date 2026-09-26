# WallForge Platform Support Matrix

WallForge is engineered with a strict platform abstraction layer separating UI presentation, provider networking, and system desktop integration.

---

## Operating System & Desktop Environment Support

| Platform / Desktop | Backend Identifier | Setter Mechanism | Set Wallpaper | Clear Wallpaper | Multi-Monitor | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Linux (Hyprland)** | `hyprland` | `hyprctl` / `hyprpaper` IPC + conf sync | Yes | Yes | Yes | **Tier 1 (Full)** |
| **Linux (GNOME)** | `gnome` | `gsettings` (`picture-uri` + dark) | Yes | Yes | Partial | **Tier 1 (Full)** |
| **Linux (KDE Plasma)** | `kde` | `plasma-apply-wallpaperimage` | Yes | Yes | Yes | **Tier 1 (Full)** |
| **Linux (Sway)** | `sway` | `swaymsg` / `swaybg` | Yes | Yes | Yes | **Tier 1 (Full)** |
| **Linux (XFCE)** | `xfce` | `xfconf-query` | Yes | Yes | Yes | **Tier 1 (Full)** |
| **Linux (Cinnamon)** | `cinnamon` | `gsettings` (`org.cinnamon.desktop`) | Yes | Yes | Partial | **Tier 1 (Full)** |
| **Linux (MATE)** | `mate` | `gsettings` (`org.mate.background`) | Yes | Yes | Partial | **Tier 1 (Full)** |
| **Linux (Generic X11/Wayland)**| `generic` | `swww` / `feh` / `nitrogen` / `swaybg`| Yes | Yes | Depends | **Tier 1 (Full)** |
| **Windows 10 / 11** | `windows` | Win32 `SystemParametersInfoW` + Registry | Yes | Fallback | Yes | **Tier 1 (Full)** |
| **macOS (Big Sur, Monterey, Ventura, Sonoma, Sequoia)** | `macos` | AppleScript via `osascript` / `System Events` | Yes | Fallback | Yes | **Tier 1 (Full)** |
| **Headless / Unsupported OS** | `unavailable` | Graceful Degradation Fallback | No | No | No | **Graceful (Browse & Download 100%)** |

---

## Graceful Degradation Model

If WallForge runs in an environment where desktop wallpaper changing is restricted, sandboxed, or unsupported (e.g. running on an unsupported window manager, inside a minimal container, or on an operating system without permissions):

1. **No Crashes**: The application launches, initializes all modules, and presents the UI normally.
2. **Settings Detection**: Settings > Desktop Integration visibly reports `"Detected Platform: <OS>"` and sets the backend to `Unavailable`.
3. **Smart Button States**:
   - The **"Set as Wallpaper"** button in `WallpaperPreviewDialog` is disabled with a helpful tooltip: `"Wallpaper setting is unavailable on this system"`.
   - The **"Apply Random Wallpaper"** header action is disabled and triggers a non-blocking toast notification.
4. **100% Retained Capabilities**:
   - Discover feeds (featured, recent, top)
   - Cross-provider Search
   - Progressive instant previews (320px thumbnail → 1280px WebP)
   - Full-resolution Wallpaper Downloads
   - Favorites library
   - Themes and design tokens (Dark, Light, Midnight, Pixel Green)

---

## Path Standardization

WallForge automatically maps user directories to the native conventions of each operating system using `PathManager`:

| Directory | Linux / BSD (XDG) | Windows 10/11 | macOS |
| :--- | :--- | :--- | :--- |
| **Cache** | `~/.cache/wallforge/` | `%LOCALAPPDATA%\wallforge\Cache\` | `~/Library/Caches/wallforge/` |
| **Config** | `~/.config/wallforge/` | `%APPDATA%\wallforge\Config\` | `~/Library/Application Support/wallforge/` |
| **Data** | `~/.local/share/wallforge/` | `%LOCALAPPDATA%\wallforge\Data\` | `~/Library/Application Support/wallforge/Data/` |
| **Pictures** | `~/Pictures/` | `%USERPROFILE%\Pictures\` | `~/Pictures/` |

> Legacy paths from `wallpaper-engine` on Linux are automatically detected and loaded for seamless backwards compatibility.
