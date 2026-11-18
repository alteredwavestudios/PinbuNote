# Start here — Pinbu Note v1.0

This is the source-only v1.0 release candidate. It is **not** an already-tested Windows or macOS installer.

1. **Keep copies of your notebooks** for your first test and don't open one notebook simultaneously in multiple old/new app versions.
2. On Windows, install Python 3.12, follow the README's dependency/install instructions and launch via `run-windows.bat`. On Mac, follow `run-mac.command`; for Linux, use Python 3.12 and `python main.py` after installing dependencies.
3. In the preview toolbar, click **☾ Dark** to attempt light text on dark paper, **Invert** for simple inversion, or click the active button again to restore the original. These only change the visible preview—not PDFs, OCR, thumbnails or saved annotations.
4. Test F11 (Windows/Linux), Minimal Light/Minimal Dark themes, the F1 Keyboard Shortcuts window, and optional reference-based page/group labels.
5. Save, close and reopen a test notebook. Confirm notes, annotations, bookmarks, citations, and PDF page ordering survive. Try backup health verification and restore to a *new copy*.
6. **There are no annotation-to-notes links in v1.0.** Existing v0.97 link buttons have been removed. Ordinary annotations and notes are unaffected. Unused v0.97 link metadata is discarded when the notebook is next saved; older inserted invisible anchors might remain in notes HTML.
7. The release audit results, skipped tests and outstanding native-platform checks are in `V100_FINAL_AUDIT.md`.

## Build and publication

Use `build-windows.ps1` and `build-installer-windows.ps1` on Windows, or `build-mac.command` and `scripts/package-macos-dmg.sh` on each Mac architecture. The GitHub Actions draft-release workflow checks the release tag matches the embedded version and will not publish automatically. Test every installer on its native system before publishing.
