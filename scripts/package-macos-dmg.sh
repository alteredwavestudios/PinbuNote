#!/usr/bin/env bash
# Package the already-built macOS application as a drag-to-Applications DMG.
# This does NOT sign or notarize it. That must be a separate release gate.
set -euo pipefail
cd "$(dirname "$0")/.."
arch="${1:-$(uname -m)}"
version="$(python -c 'from yomunote import __version__; print(__version__)')"
app="$PWD/dist/Pinbu Note.app"
[[ -d "$app" ]] || { echo "Missing built application: $app" >&2; exit 1; }
mkdir -p release-assets
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp -R "$app" "$stage/Pinbu Note.app"
ln -s /Applications "$stage/Applications"
hdiutil create -volname "Pinbu Note $version" -srcfolder "$stage" -format UDZO -ov \
  "$PWD/release-assets/PinbuNote-${version}-macOS-${arch}-unsigned.dmg"
echo 'Unsigned DMG created. Do not describe this as signed/notarized.'
