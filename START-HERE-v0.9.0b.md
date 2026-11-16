# Pinbu Note v0.9.0b — experimental SafeSave build

Keep **v0.8.7c** installed. Use copies of notebooks, not your only coursework.

Windows: `run-windows.bat`
macOS: `./run-mac.command` (or `chmod +x run-mac.command` first).

- Your notebook is edited in an OS-local working copy.
- Autosave is local; **File → Save** is what publishes back to the source file.
- Every five minutes when changed, SafeSave creates a deduplicated snapshot.
- Every normal close and project switch creates a fresh snapshot.
- Local backup directory is organised by project, then `assets/` and `data/`.
- Restore from a per-project `history.pinbubackup` or exported portable archive.
- Format v6 files are rejected by v5-only builds; don't downgrade files.
- Real cross-device cloud-sync races are **not fully solved** by filesystem
  checks, so never edit the same file concurrently on two devices.

See `docs/SAFE_SAVE.md` and `RELEASE_NOTES_v0.9.0b.md` for limitations and tests.
