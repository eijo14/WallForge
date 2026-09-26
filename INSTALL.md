# Installing WallForge

WallForge can be installed on **Linux**, **Windows**, and **macOS**.

---

## 1. Linux

### Option A: Flatpak (Recommended for all distributions)
```bash
flatpak install flathub org.wallforge.app
flatpak run org.wallforge.app
```

### Option B: AppImage (Universal Portable)
1. Download `WallForge-x86_64.AppImage` from [Releases](https://github.com/eijofrancis/wallforge/releases).
2. Make it executable and run:
```bash
chmod +x WallForge-x86_64.AppImage
./WallForge-x86_64.AppImage
```

### Option C: Native System Package (Arch Linux / AUR)
```bash
yay -S wallforge
```

### Option D: Python pip / Virtual Environment
**Requirements:** Python 3.10+, GTK4, Libadwaita (`libadwaita-1`).

```bash
# Fedora
sudo dnf install python3-pip python3-gobject gtk4 libadwaita

# Ubuntu / Debian 23.04+
sudo apt install python3-pip python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1

# Arch Linux
sudo pacman -S python-pip python-gobject gtk4 libadwaita

# Install WallForge
pip install .
wallforge
```

---

## 2. Windows 10 & 11

### Option A: Setup Installer (.exe)
1. Download `WallForge-Setup-1.0.0-x64.exe` from [Releases](https://github.com/eijofrancis/wallforge/releases).
2. Run the installer wizard.
3. Launch **WallForge** from the Start Menu or Desktop shortcut.

### Option B: Portable Package (.zip)
1. Download `WallForge-1.0.0-win64.zip`.
2. Extract the folder anywhere on your computer.
3. Run `WallForge.exe`.

---

## 3. macOS (Big Sur 11.0+)

### Option A: DMG Installer
1. Download `WallForge-1.0.0-macOS.dmg`.
2. Open the disk image and drag **WallForge** into your `Applications` folder.
3. Open WallForge from Launchpad or Finder.

### Option B: Homebrew Cask (Upcoming)
```bash
brew install --cask wallforge
```
