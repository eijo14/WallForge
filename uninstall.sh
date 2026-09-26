#!/usr/bin/env bash
set -e

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> Uninstalling Personal Wallpaper Engine..."

if [ -f "$APPS_DIR/personal-wallpaper-engine.desktop" ]; then
    rm -f "$APPS_DIR/personal-wallpaper-engine.desktop"
    echo "  ✓ Removed desktop launcher"
fi

if [ -f "$SYSTEMD_USER_DIR/personal-wallpaper-rotation.service" ]; then
    systemctl --user stop personal-wallpaper-rotation.service 2>/dev/null || true
    systemctl --user disable personal-wallpaper-rotation.service 2>/dev/null || true
    rm -f "$SYSTEMD_USER_DIR/personal-wallpaper-rotation.service"
    systemctl --user daemon-reload 2>/dev/null || true
    echo "  ✓ Removed systemd rotation service"
fi

echo "Uninstallation complete."
