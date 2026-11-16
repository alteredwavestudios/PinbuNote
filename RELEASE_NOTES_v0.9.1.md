# Pinbu Note v0.9.1 — SafeSave Health & Independent Second Backups

**Release candidate source**, not yet a published installer. Back up coursework
independently and test with duplicate notebooks before upgrading your daily setup.

## What changed

- **Quiet footer autosave indicator:** the permanent status bar now shows small
  `Autosave · HH:MM` text after a successful local commit, `Autosave · ready`
  when first opened, or `Autosave · failed` after an error. No new confetti or
  celebratory animation. The manual Save command still publishes to the
  notebook's chosen destination.
- **Optional second backup directory:** Preferences offers a checkbox and
  Browse control. Disabled by default. When enabled, Pinbu independently
  creates the *same complete snapshot state* in another deduplicated history,
  ideally on another physical drive. The existing mandatory primary backups
  and five-minute/close snapshots are unchanged.
- **No misleading success when the second backup fails:** the primary copy is
  retained; failures are reported. On close, the user chooses whether to
  continue with the primary backup or stay open to correct the issue. If the
  primary drive fails, Pinbu still tries the secondary destination. A vanished
  external-drive folder is never silently recreated on the internal disk.
- **SafeSave Health & Verify Backups:** Preferences opens an inspection window
  with the local notebook's timestamp, original file, last recorded successful
  manual publish, unpublished status, primary/secondary snapshot counts and
  storage use. Verification hash-checks backup content and performs a *real
  temporary restored-notebook test*. Verify Latest is quicker; Verify Entire
  History checks every retained snapshot and can be slow for large archives.
- **Better error attribution:** a missing PDF source blocks unsafe saving and
  provides a more meaningful message. If saving the currently open notebook
  fails while switching, recovery is not incorrectly offered for the new one.
- **Version alignment:** v0.9.1 application version, Windows installer
  `0.9.1.0`, DMG and draft release asset names are aligned for the next tag.

## Backup locations and formats

The primary backup root defaults to the OS-local application-data directory.
The second root can be selected separately, but must **not** be the same folder
or nested under the primary. Enable it manually in Preferences. Each root
contains its own readable per-project directory with `history.pinbubackup`,
`assets/`, `data/`, and a friendly `PLEASE READ` file. An unavailable removable
or network drive is an **error** for the secondary copy, never a silent success.

Notebook format remains **v6**; backup archive format remains **v1**. The new
source can use old `.pinbunote` notebooks and existing `.pinbubackup` histories
without a file-format conversion. Legacy backup migration remains available.

## Important safety limitations

- Local backups on the *same physical drive* do not protect against whole-drive
  failure. Choose a second physical drive for genuine storage redundancy.
- The secondary backup is not an automatic remote cloud synchronization system.
  It is an independent backup destination, not a concurrent editor.
- Dropbox/OneDrive/iCloud file-revision checks are not atomic across devices.
  True cross-device concurrent publishing remains a known limitation.
- The small footer time records a successful *local autosave*, not a successful
  upload or publish to the original `.pinbunote` file.
- Verify Entire History is intentionally thorough and may take a long time
  for notebooks with very large PDF collections. It runs on a worker thread.
- Native Windows/macOS microphone and Qt GUI testing is not covered by the
  source-only headless checks; v0.9.1 is not a stable multi-device guarantee.

## Expected build artefacts after successful draft-release CI

- `PinbuNote_Setup_v0.9.1.exe`
- `PinbuNote-0.9.1-macOS-arm64-unsigned.dmg`
- `PinbuNote-0.9.1-macOS-x86_64-unsigned.dmg`

These are expected **build outputs**, not executables included in the ZIP.
Release is draft/prerelease only; do not publish until real-machine acceptance
checks pass.

## What comes next

**v0.9.2:** citation management, PDF printed-page numbering, and searchable
research tags. Voice Studio work is postponed until after research tools.
