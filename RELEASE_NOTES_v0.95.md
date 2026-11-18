# Pinbu Note v0.95 — Stability release

This release is built **only from v0.9.2b Navigator Click Hotfix**. It does not
include PinbuBoard or NodeGraphQt. The portable notebook format stays at v7;
existing `.pinbunote` and supported legacy notebooks remain compatible.

## Fixes

- Unified bounded SQLite manifest reads for opening, working-copy creation,
  backup scanning and creation, destination inspection, sharing and restore.
  The limit is evaluated on UTF-8 **bytes** in SQLite before returning JSON
  to Python. This reduces memory-exhaustion risk from malicious notebooks.
- Version comparison supports the requested two-part **0.95** label while
  recognising old `0.9.2b` and future releases for downgrade protection.
- If closing fails to save, Pinbu Note remains open, logs the exception and
  explains the safest next step: retry or Save Copy As. The app does not
  claim the work was successfully published.
- Windows installer, About/version field, macOS DMG naming and draft-release
  workflow updated. A release tag must match the source version; both macOS
  architectures and Windows must succeed before a draft is created.

## Known verification gaps

This source archive is **not** a prebuilt native installer. GitHub's macOS
runner allocation issue remains unproven for v0.95 and needs an actual CI run.
GUI scrolling, OCR packaging, opening a frozen .app and Windows installer
startup require native-platform testing. Do not publicly ship v0.95 before
those checks complete. The macOS DMGs are unsigned and not notarised.

## Expected draft-release artifact filenames

- `PinbuNote_Setup_v0.95.exe` — Windows installer
- `PinbuNote-0.95-macOS-arm64-unsigned.dmg` — Apple Silicon
- `PinbuNote-0.95-macOS-x86_64-unsigned.dmg` — Intel Mac

The release workflow checks all three nonempty artifacts and saves SHA-256
checksums, but cannot sign or notarize them automatically.
