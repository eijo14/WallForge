#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="${DATA_DIR}/applications"
ICONS_DIR="${DATA_DIR}/icons/hicolor"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> Installing WallForge..."

# Ensure directories exist
mkdir -p "$APPS_DIR"
mkdir -p "$SYSTEMD_USER_DIR"
mkdir -p "${ICONS_DIR}/scalable/apps"
mkdir -p "${ICONS_DIR}/128x128/apps"
mkdir -p "${ICONS_DIR}/256x256/apps"
mkdir -p "${ICONS_DIR}/512x512/apps"

# Install Icons
if [ -f "$SCRIPT_DIR/packaging/icons/org.wallforge.app.svg" ]; then
    cp "$SCRIPT_DIR/packaging/icons/org.wallforge.app.svg" "${ICONS_DIR}/scalable/apps/org.wallforge.app.svg"
    cp "$SCRIPT_DIR/packaging/icons/wallforge_128x128.png" "${ICONS_DIR}/128x128/apps/org.wallforge.app.png" 2>/dev/null || true
    cp "$SCRIPT_DIR/packaging/icons/wallforge_256x256.png" "${ICONS_DIR}/256x256/apps/org.wallforge.app.png" 2>/dev/null || true
    cp "$SCRIPT_DIR/packaging/icons/wallforge_512x512.png" "${ICONS_DIR}/512x512/apps/org.wallforge.app.png" 2>/dev/null || true
    echo "  ✓ Installed app icons to: ${ICONS_DIR}"
fi

# Install Desktop Entry
DESKTOP_SRC="$SCRIPT_DIR/packaging/metadata/org.wallforge.app.desktop"
DESKTOP_DEST="$APPS_DIR/org.wallforge.app.desktop"

sed "s|Exec=wallforge|Exec=python3 $SCRIPT_DIR/run.py|" "$DESKTOP_SRC" > "$DESKTOP_DEST"
chmod +x "$DESKTOP_DEST"
echo "  ✓ Installed desktop launcher at: $DESKTOP_DEST"

# Install Systemd Rotation Service
if [ -f "$SCRIPT_DIR/data/personal-wallpaper-rotation.service" ]; then
    cp "$SCRIPT_DIR/data/personal-wallpaper-rotation.service" "$SYSTEMD_USER_DIR/wallforge-rotation.service"
    echo "  ✓ Installed systemd user service at: $SYSTEMD_USER_DIR/wallforge-rotation.service"
fi

chmod +x "$SCRIPT_DIR/run.py"

echo ""
echo "WallForge installation complete!"
echo "Launch from your application menu or run:"
echo "  python3 '$SCRIPT_DIR/run.py'"
