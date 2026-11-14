# Yomu Note v0.8.3b 🌸 — Text Lab integration (pre-release)

This is a **pre-release** for Windows and macOS testing. Do **not** publish the draft release before checking the installers on actual target machines. Both macOS DMGs are **unsigned and not notarized**. Linux remains source-only.

## What's new

- Text-aware PDF selection, Copy Text and Highlight Text context-menu actions for documents with text layers.
- **Select Text** and **OCR** grouped in the preview toolbar with responsive controls; Select Text and text-aware highlight actions are disabled on image-only pages.
- Text-aware highlight groups can be undone as one action; area highlighting remains available when text layers are missing.
- New highlight default: **#FFE536**, **80% opacity**, **Multiply**, without rewriting older saved annotations.
- Delete/Backspace in the focused page navigator removes all selected pages, and one Undo restores the whole batch and group hierarchy.
- Theme-accent outlines clarify which workspace panel has keyboard focus.
- Optional development launcher with separate preferences seeded once from regular Yomu Note settings.

## Release and installer safety checks

- **Windows:** Retain Python's matching `sqlite3.dll` for `_sqlite3.pyd` instead of the potentially incompatible OCR DLL; keep OCR native libraries under the private `ocr` directory.
- Run a frozen EXE smoke test *after* repairing SQLite, then verify bundled OCR.
- **Inno Setup:** Wait for installer completion before testing the installed copy; check exit code and installed SQLite runtime.
- **First launch:** Installer does not automatically launch the app; start Yomu Note from the Windows Start menu after closing Setup.
- Keep the stable Inno Setup `AppId` so this remains an upgrade to the existing Windows application.
- **macOS:** Produce unsigned arm64 and x86_64 DMGs with offline OCR verification.
- **Linux:** Source-only; source tests run in the CI matrix.

## Release assets

- `YomuNote_Setup_v0.8.3b.exe`
- `YomuNote-0.8.3b-macOS-arm64-unsigned.dmg`
- `YomuNote-0.8.3b-macOS-x86_64-unsigned.dmg`
- `SHA256SUMS.txt`

The release workflow creates an **unpublished draft**. Before publishing, test the installed Windows application from the Start menu, opening a PDF, native text selection, OCR, multi-page deletion and Undo. Verify macOS behaviour on supported hardware. These checks are not replaced by passing source tests.
