#!/usr/bin/env bash
# Script to build WallForge AppImage using appimagetool
set -e

SCRIPT_DIR="$(dirname "$(readlink -f "${0}")")"
PROJECT_DIR="$(readlink -f "${SCRIPT_DIR}/../..")"
BUILD_DIR="${PROJECT_DIR}/build/appimage"
APP_DIR="${BUILD_DIR}/WallForge.AppDir"

echo "==> Preparing AppDir at ${APP_DIR}..."
rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/usr/bin"
mkdir -p "${APP_DIR}/usr/share/applications"
mkdir -p "${APP_DIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${APP_DIR}/usr/share/metainfo"

echo "==> Copying metadata and icons..."
cp "${PROJECT_DIR}/packaging/appimage/AppRun" "${APP_DIR}/AppRun"
chmod +x "${APP_DIR}/AppRun"

cp "${PROJECT_DIR}/packaging/metadata/org.wallforge.app.desktop" "${APP_DIR}/org.wallforge.app.desktop"
cp "${PROJECT_DIR}/packaging/metadata/org.wallforge.app.desktop" "${APP_DIR}/usr/share/applications/"
cp "${PROJECT_DIR}/packaging/metadata/org.wallforge.app.metainfo.xml" "${APP_DIR}/usr/share/metainfo/"

cp "${PROJECT_DIR}/packaging/icons/org.wallforge.app.svg" "${APP_DIR}/org.wallforge.app.svg"
cp "${PROJECT_DIR}/packaging/icons/org.wallforge.app.svg" "${APP_DIR}/usr/share/icons/hicolor/scalable/apps/"
cp "${PROJECT_DIR}/packaging/icons/org.wallforge.app.png" "${APP_DIR}/.DirIcon"

echo "==> Installing Python application code..."
pip install --prefix="${APP_DIR}/usr" --no-deps "${PROJECT_DIR}"

if command -v appimagetool &>/dev/null; then
    echo "==> Packaging AppImage..."
    ARCH="$(uname -m)" appimagetool "${APP_DIR}" "${BUILD_DIR}/WallForge-${ARCH}.AppImage"
    echo "✓ Built: ${BUILD_DIR}/WallForge-${ARCH}.AppImage"
else
    echo "Notice: 'appimagetool' not found in PATH."
    echo "Download from https://github.com/AppImage/AppImageKit/releases and run:"
    echo "  appimagetool \"${APP_DIR}\" \"${BUILD_DIR}/WallForge-x86_64.AppImage\""
fi
