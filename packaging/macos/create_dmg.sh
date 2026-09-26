#!/usr/bin/env bash
# Creates a distributable macOS DMG using create-dmg or hdiutil
set -e

SCRIPT_DIR="$(dirname "$(readlink -f "${0}")")"
PROJECT_DIR="$(readlink -f "${SCRIPT_DIR}/../..")"
DIST_DIR="${PROJECT_DIR}/dist"
APP_PATH="${DIST_DIR}/WallForge.app"
DMG_PATH="${DIST_DIR}/WallForge-1.0.0-macOS.dmg"

if [ ! -d "${APP_PATH}" ]; then
    echo "Error: ${APP_PATH} does not exist. Run PyInstaller first:"
    echo "  pyinstaller packaging/macos/wallforge_mac.spec"
    exit 1
fi

echo "==> Creating macOS disk image at ${DMG_PATH}..."
rm -f "${DMG_PATH}"

if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "WallForge Installer" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "WallForge.app" 175 120 \
        --hide-extension "WallForge.app" \
        --app-drop-link 425 120 \
        "${DMG_PATH}" \
        "${APP_PATH}"
else
    # Fallback to standard macOS hdiutil
    echo "Using hdiutil fallback..."
    hdiutil create -volname "WallForge" -srcfolder "${APP_PATH}" -ov -format UDZO "${DMG_PATH}"
fi

echo "✓ Successfully created: ${DMG_PATH}"
