#!/usr/bin/env bash
# Make an AppImage from build-linux.sh's standalone bundle.
# Provide the appimagetool path (and optional runtime) on the command line.
# Linux distribution compatibility STILL needs a clean-machine smoke test.
set -euo pipefail
cd "$(dirname "$0")/.."
tool="${1:-appimagetool}"
version="$(python -c 'from yomunote import __version__; print(__version__)')"
runtime="${2:-}"
source="$PWD/dist/Pinbu Note"
[[ -x "$source/Pinbu Note" ]] || { echo "Missing executable: $source/Pinbu Note" >&2; exit 1; }
appdir="$PWD/.build/PinbuNote.AppDir"
rm -rf "$appdir"
mkdir -p "$appdir/usr/bin"
cp -a "$source" "$appdir/usr/bin/Pinbu Note"
cp assets/icon.png "$appdir/pinbu-note.png"
ln -s pinbu-note.png "$appdir/.DirIcon"
cat > "$appdir/pinbu-note.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Pinbu Note
Comment=Offline reading, annotation and shared study notebooks
Exec=pinbu-note
Icon=pinbu-note
Terminal=false
Categories=Education;Office;
DESKTOP
cat > "$appdir/AppRun" <<'APPRUN'
#!/bin/sh
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$HERE/usr/bin/Pinbu Note/Pinbu Note" "$@"
APPRUN
chmod +x "$appdir/AppRun"
mkdir -p release-assets
arch="$(uname -m)"
output="$PWD/release-assets/PinbuNote-${version}-Linux-${arch}.AppImage"
args=()
if [[ -n "$runtime" ]]; then args+=(--runtime-file "$runtime"); fi
ARCH="$arch" APPIMAGE_EXTRACT_AND_RUN=1 "$tool" "${args[@]}" "$appdir" "$output"
test -s "$output"
echo "AppImage generated at $output"
