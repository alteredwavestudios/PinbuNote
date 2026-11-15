# v0.8.5 — Release acceptance checklist

**Status:** Source candidate prepared. NOT yet published or installed as a
0.8.5 Windows/macOS package. The user has confirmed v0.8.4c works locally.

- [x] Release version, Inno Setup filename and numeric version, macOS DMG
      names and GitHub Actions expected assets aligned to v0.8.5.
- [x] Windows installer AppId, SQLite DLL safety check, frozen EXE startup
      smoke test and offline OCR verification preserved.
- [x] Notebook schema remains v5; underlying 0.8.4c application behaviour
      retained unchanged.
- [ ] GitHub pull-request source tests pass on Windows, macOS and Linux.
- [ ] Fresh Windows installer build passes frozen EXE/SQLite and OCR checks.
- [ ] Both macOS architectures produce valid DMGs; test where possible.
- [ ] Installed Windows app test: notebooks, text selection/highlighting,
      OCR, imported tabs, undo, autosaving and existing settings survive.
- [ ] Confirm checksums and any unsigned build warnings.
- [ ] Publish **draft pre-release** manually after acceptance.

This package is *source*, not the final unsigned native installer.
