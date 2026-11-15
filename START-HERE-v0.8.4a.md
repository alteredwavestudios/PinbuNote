# Yomu Note v0.8.4a — Reliability development candidate

This is a **complete source build**, not a precompiled Windows EXE or the public
v0.8.3b installer. It includes the existing Text Lab features plus the first
stage of the deep audit's data-integrity fixes.

1. Extract the complete ZIP to a fresh directory, such as
   `H:\dev\Yomu-Note-v0.8.4a`. Avoid merging it into the installed app.
2. Double-click `RUN_DEV_SAFELY.cmd` on Windows. It uses isolated developer
   preferences (`YOMU_INTEGRATION_DEV=1`). Install Python requirements in a
   separate virtual environment if needed; see `run-windows.bat` and README.
3. Open **copies** of valuable `.yomunote` notebooks.
4. Test moving and copying multiple pages between tabs; Ctrl+Z and Ctrl+Shift+Z
   (or your configured Redo shortcut), including annotations and reading flags.
5. Test opening old notebooks and performing save/reopen. If an original PDF
   was removed, the app should give an error instead of silently saving a
   broken notebook; restore missing material from backups before retrying.

## Guarantees and limitations

- v5 notebook format and installer AppId unchanged.
- Working v0.8.3b and production settings remain untouched in safe dev mode.
- Tested Python storage operations; Windows/macOS native GUI and installer
  still need independent testing before release.
- This candidate does NOT yet solve the large-notebook main-thread save
  amplification or third-party parser sandboxing. These are separate stages.
