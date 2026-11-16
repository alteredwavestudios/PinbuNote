# Pinbu Note v0.9.0b4 — Readable SafeSave Backups & Legacy Migration

**Experimental, full-source build.** Maintain independent copies of important coursework and test against disposable notebooks first. No stable release or cloud-conflict guarantee is implied.

## Readable per-project backup folders

SafeSave's automatic backup folders now use familiar titles such as `Sociology`, `Sociology (2)` and `Film Studies`. Full notebook/source identities remain in the `history.pinbubackup` index. `assets/` contains shared document assets; `data/objects/` and `data/snapshots/` contain deduplicated metadata and version records. The project folder includes **PLEASE READ - About Your Backups.txt**, a friendly warning not to alter internal archive files.

Existing long-ID directories can be safely converted to readable project names with the migration tool. Contents are checked; original indexed directories are retained under `_Legacy Originals (kept)` when conversion is performed within the configured backup directory.

## Settings → Preferences → Migrate Legacy Backups…

The new preview-and-confirm utility can import:

- Earlier complete SQLite backup snapshots (`.pinbunote`, `.yomunote`, `.yominote`), including the rotating whole-file backups from previous releases.
- Earlier folder-based Yomu Note project backups containing `project.json`.
- Long-named deduplicated SafeSave histories produced by v0.9.0b–b3.

Click **Scan Folder** and review the list before **Migrate Found Backups…**. You can browse to an older backup folder. Conversion happens off the GUI thread and verifies newly created snapshots. Full-file originals are never deleted, and repeat imports of an unchanged source are skipped. Newly imported backups are organised per project and reused assets are not duplicated across snapshots.

Use **File → Restore From Backup…** to restore a chosen version into a *new* `.pinbunote` notebook. Do not manually rename or remove individual files inside a SafeSave history.

## Existing SaveSafe guarantees retained

- Private local working copies; original notebook only published via checked Save.
- Automatic five-minute local backups and close backups.
- Pre-overwrite verified backup when replacing an existing notebook.
- Version compatibility warnings and protected publish behaviour.
- Crash-recovery records and explicit close actions.

The `.pinbunote` format remains **v6** and `.pinbubackup` remains **v1**. This release changes the physical folder organisation and adds migration tools, not the archive version.

## Build artefacts expected from CI

- `PinbuNote_Setup_v0.9.0b4.exe`
- `PinbuNote-0.9.0b4-macOS-arm64-unsigned.dmg`
- `PinbuNote-0.9.0b4-macOS-x86_64-unsigned.dmg`

These are *build output filenames*, not prebuilt installers included in this source ZIP.

## Known cautions

- Cloud sync can still race across devices without a provider-atomic compare-and-swap. Keep an independent local recovery copy.
- The migration tool intentionally doesn't discard old backup files; you may need extra temporary disk space during conversion.
- The automated test environment lacks PySide6 for native GUI checks. Verify the Preferences dialog and recovery workflow on your actual operating system before relying on this version.
- Unreadable or unsupported future backup formats are reported and left untouched. Older app builds will not necessarily understand future snapshots.
