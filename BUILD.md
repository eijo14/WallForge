# Building WallForge from Source

This document describes how to build, test, and package WallForge across all supported platforms.

---

## Prerequisites

- **Python**: 3.10 or newer
- **GTK4**: 4.10+
- **Libadwaita**: 1.3+
- **PygObject**: 3.42+
- **Pillow**: 9.0+
- **Requests**: 2.28+

---

## 1. Running in Development Mode

Clone the repository and install development dependencies:

```bash
git clone https://github.com/eijofrancis/wallforge.git
cd wallforge

# Create virtual environment (optional)
python3 -m venv venv
source venv/bin/activate

# Install in editable mode
pip install -e .

# Run the app directly
python3 run.py
```

---

## 2. Running the Test Suite

WallForge contains comprehensive unit and cross-platform regression test suites:

```bash
# Run all tests headlessly
python3 -m unittest discover -s tests -p "test_*.py"

# Or run with display access enabled (for live GTK widget verification)
WAYLAND_DISPLAY=wayland-1 DISPLAY=:0 python3 -m unittest discover -s tests -p "test_*.py"

# Run only platform and capability tests
python3 -m unittest tests/test_platform_backends.py
```

---

## 3. Packaging

### Generating Icons
To re-render all PNG and ICO icon assets from the source SVG:
```bash
python3 packaging/icons/render_icons.py
```

### Linux Flatpak
```bash
flatpak-builder --user --install --force-clean build-dir packaging/flatpak/org.wallforge.app.json
```

### Linux AppImage
```bash
bash packaging/appimage/build_appimage.sh
```

### Windows Binary & Installer
On a Windows build machine:
```cmd
pip install pyinstaller pillow requests pygobject
pyinstaller packaging/windows/wallforge.spec

; Optional: Build Inno Setup installer
iscc packaging/windows/wallforge_installer.iss
```

### macOS Application Bundle & DMG
On a macOS build machine:
```bash
pip install pyinstaller pillow requests pyobjc-core
pyinstaller packaging/macos/wallforge_mac.spec

bash packaging/macos/create_dmg.sh
```
