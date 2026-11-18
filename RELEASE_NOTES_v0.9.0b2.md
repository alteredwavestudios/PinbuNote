# Pinbu Note v0.9.0b2 — SafeSave exit and crash-recovery fix (experimental)

**Source only; use disposable notebook copies during testing.**

## Fixes

- **No false unpublished-changes warning after Save:** `Project.save()` no longer regenerates `updated_at` or updates app-version stamps on a no-op. Opening an earlier-release notebook also normalises the app-version stamp in the **private local working copy** without publishing it. Previously every close rewrote metadata, making the notebook appear changed regardless of user edits.
- **Three-button close dialog, only when unpublished edits exist:** Save & Close (checked publish to the selected original), Close Without Saving (no publish; local copy and backups retained), Go back (cancel exit). A failed publish keeps the window open.
- **Crash-detection markers:** each local SafeSave working session records `active` while being edited and `closed` after an intentional, backed-up close. At next startup, abandoned *unlocked* `active` sessions trigger a recovery prompt. A second, still-running Pinbu process isn't misidentified as crashed.
- **Recover Latest Save:** constructs a separate `.pinbunote` from the last locally committed working database in the OS-local `Pinbu Note/Recovered` folder (outside cloud-synchronised Documents), without replacing the external original. The prompt can be dismissed with Not Now; recovery files remain available via File → Recover Local Working Copy.
- Existing `.pinbunote` v5/v6 notebook format and `.pinbubackup` histories are unchanged. The Windows `fsync` hotfix from v0.9.0b1 remains included.

## Important safety limits

- An operating-system power failure can lose edits made *after* the latest local SQLite autosave; those keystrokes were still in RAM. The prompt recovers the last **committed** local copy, not unsaved memory.
- A hard crash during a SQLite write is expected to leave either the prior or completed transaction; if the working database is corrupt, use the per-project backup history. Recovery never overwrites the original.
- Sessions from v0.9.0b1 have no reliable close marker: they remain manually recoverable but cannot be automatically distinguished from normal closes.
- Mac/Windows native GUI and Dropbox cross-device conflict testing remain outstanding. Filesystem checks cannot provide a distributed atomic write across two disconnected machines.

## Expected release packages (build from source)

- Windows: `PinbuNote_Setup_v0.9.0b2.exe`
- macOS arm64: `PinbuNote-0.9.0b2-macOS-arm64-unsigned.dmg`
- macOS Intel: `PinbuNote-0.9.0b2-macOS-x86_64-unsigned.dmg`

## Manual regression test

1. Open a disposable copy of a notebook and press Save; close without further edits. **No warning should appear.**
2. Open again; edit one note; close. Choose Go back, then Save & Close; confirm the chosen original contains the edit.
3. Edit again; choose Close Without Saving; confirm the original is unchanged and recovery is available in the File menu. **This is not a delete/discard function.**
4. With a disposable notebook open, make a note edit, wait until local autosave commits, then force-kill Pinbu (not a normal close). Reopen: choose Recover Latest Save. Confirm it makes a separate notebook, preserving the original.
5. Open two independent notebooks in separate processes; starting the second must not report the first as crashed.
