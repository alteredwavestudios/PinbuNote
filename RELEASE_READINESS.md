# Pinbu Note v1.0 — Publication gates

This source candidate is **not yet cleared for public release**. The accompanying audit report details which checks passed in this environment.

- [x] App/library, installer, workflow, test and release-note version strings agree on **1.0 / v1.0**.
- [x] All annotation-to-notes runtime code has been removed; old standalone PDF annotations and notes remain supported.
- [x] Notebook schema v7 and tab format v5 unchanged.
- [x] Full-source static compilation and integrated headless regression suite pass.
- [x] Existing SafeSave / malicious metadata tests, old project compatibility tests and synthetic performance tests run.
- [ ] PySide6 native GUI smoke test: launch, new notebook, F11, minimal themes, navigation, F1 help, import PDF and page preview, dark/invert/original modes, annotations, editor undo/redo, quit/save/reopen.
- [ ] Windows installer build/upgrade test including PyInstaller startup, bundled OCR and SQLite DLL configuration.
- [ ] macOS arm64 and Intel: signed/offline OCR dependencies verification, app launch, DMG install, first-run privacy prompts and long session memory.
- [ ] Large real-world document test: PDF scrolling, OCR, photo annotation, zoom, memory growth, and thumbnail eviction.
- [ ] Voice Studio microphone and recorder test (existing experimental feature; transcription needs a separately supplied offline model).
- [ ] SafeSave with Dropbox/OneDrive/iCloud sync conflicts verified on native systems using *copies* of notebooks.
- [ ] Confirm exact native asset names and checksums; review GitHub **draft** release before publishing.

**Never mark the app signed/notarised; current macOS DMGs are unsigned.**
