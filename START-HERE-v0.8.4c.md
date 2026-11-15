# v0.8.4c development candidate — run on copies only

See `RELEASE_NOTES_v0.8.4c.md` for background save and Tab Exchange test checklist.

# Yomu Note v0.8.4c — Reliability development candidate

This is a **complete source build**, not a precompiled Windows EXE or the public
v0.8.3b installer. It builds on the working v0.8.4a data-integrity candidate
with a small UI Undo fix and measured performance improvements.

1. Extract the complete ZIP to a fresh directory, such as
   `H:\dev\Yomu-Note-v0.8.4c`. Avoid merging it into the installed app.
2. Double-click `RUN_DEV_SAFELY.cmd` on Windows. It uses isolated developer
   preferences (`YOMU_INTEGRATION_DEV=1`). Install Python requirements in a
   separate virtual environment if needed; see `run-windows.bat` and README.
3. Open **copies** of valuable `.yomunote` notebooks.
4. Test moving and copying multiple pages between tabs; Ctrl+Z and Ctrl+Shift+Z
   (or your configured Redo shortcut), including annotations and reading flags.
5. In a destination tab that originally had no pages, move a page in; switch
   to that tab and Undo. Its PDF preview should clear **immediately**, without
   switching away and back. Then Redo and verify the page reappears.
6. Try a notebook with many tabs: use Save, close/reopen, and Tab Exchange.
   Verify no editor changes are lost. The new save batch makes one SQLite
   commit for each of those multi-pane operations.
7. Test opening old notebooks and performing save/reopen. If an original PDF
   was removed, the app should give an error instead of silently saving a
   broken notebook; restore missing material from backups before retrying.

## Guarantees and limitations

- v5 notebook format and installer AppId unchanged.
- Working v0.8.3b and production settings remain untouched in safe dev mode.
- Tested Python storage operations; Windows/macOS native GUI and installer
  still need independent testing before release.
- This candidate reduces repeated saves in multi-pane operations, but the
  remaining SQLite commit is still synchronous on the GUI thread. True worker
  persistence and third-party parser sandboxing remain separate stages.
