## v0.9.0b3 — Protected Save Copy As overwrite and newer files

**Save Copy As** permits an existing filename after explicit confirmation, but first creates and verifies a `pre-overwrite` snapshot in that destination notebook's **own** `assets/` and `data/` backup folders. Newer app version: strong warning and Save as New Copy recommended; incompatible future *file format*: overwrite prohibited. Opening newer notebooks warns and requires upgrading. Ordinary autosaves remain local only; if the original cloud notebook is upgraded externally, Pinbu warns and blocks publishing. A normal Save to an externally changed notebook remains blocked.

# SafeSave implementation guide (experimental v0.9.0b1)

## Locations

Automatic histories are per-project folders below the configured **local** backup
root (default `Pinbu Note/Backups` under LOCALAPPDATA, macOS Application Support,
or XDG_DATA_HOME). Each folder's own `history.pinbubackup` is a small JSON index:

- `assets/<sha-prefix>/<hash>.bin`: immutable source PDFs, images, and converted
  page assets, identified by SHA-256. Reused by all snapshots with that content.
- `data/objects/<sha-prefix>/<hash>.z`: zlib-compressed project metadata / notes,
  also content-addressed.
- `data/snapshots/<UTC>-<id>.json`: immutable complete notebook state/pointers,
  including saved app version, format version and time/reason.

The source-path key prevents independent copies of a notebook from sharing
history, even if their internal notebook UUID happens to be identical.

`history.pinbubackup` is **not self-contained**. To transfer a backup, use
**File → Export Portable Backup…**. That outputs a self-contained ZIP-format
`.pinbubackup` file with the same folders inside. Restore From Backup handles
both forms and always creates a new `.pinbunote`.

## Opening and saving

- The GUI opens a verified SQLite working copy in OS-local WorkingCopies.
- Normal autosaves, reading positions and five-minute snapshots only touch
  that copy. The external notebook is *never* used as a live writable DB.
- Explicit Save publishes a consistent SQLite snapshot if the external file
  still matches its open-time identity. Cross-device compare-and-swap is not
  possible on ordinary sync-folder files. A Dropbox race is still possible
  before remote changes arrive; unpublished local copies provide recovery.
- Closing or switching forces a local history snapshot first. If the snapshot
  fails, the close/switch cannot proceed silently.
- If there are unpublished changes, normal Quit warns; the retained working
  copy can be recovered via File → Recover Local Working Copy….
- No project backup history or detached working-copy folder should be kept
  inside Dropbox/OneDrive/iCloud by default.

## Versioning

New writes are notebook format v6; this build reads v5 or v6. The preserved
v5 magic/structure is still understood. Older v5-only builds cannot open v6,
which prevents them silently rewriting newer files. The saved app version is
informational; newer builds refuse future app versions with an explanatory
error. Older executable releases cannot be retrofitted to show that message.

## Safety boundaries

Atomic local snapshot metadata writes; SHA-256 verified on restore; manifest
path traversal rejected; untrusted compressed snapshot sizes capped; no source
PDF is modified. For cloud consistency stronger than filesystem checks, future
work requires provider-specific APIs and a carefully tested conflict protocol.

For now, test with copied coursework only, and verify backups are restorable.

## v0.9.0b4 readable histories and migration

Backup root folders now use the notebook's name and append `(2)` etc. for collisions, with canonical identity in `history.pinbubackup` rather than visible folder name. Project histories include `PLEASE READ - About Your Backups.txt` and retain separate `assets/` and `data/` directories.

Settings → Preferences → **Migrate Legacy Backups…** scans a user-chosen old backup directory and previews intact complete `.pinbunote`/`.yomunote`/`.yominote` snapshots, early folder-backed `project.json` directories and long-ID SafeSave histories. After explicit confirmation it imports legacy snapshots (including original timestamps where available), verifies archive contents, and reports skipped/failed entries. Old full-file backups are never deleted. Long-ID projects in the current backup root are copied and verified, then their originals are retained under `_Legacy Originals (kept)`.
