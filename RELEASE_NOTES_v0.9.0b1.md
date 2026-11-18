# v0.9.0b1 Windows save hotfix (experimental)

**Fix:** Publishing a staged local notebook on Windows no longer calls `os.fsync` on a read-only file descriptor (which raised `[Errno 9] Bad file descriptor`). It uses `r+b` on the completed temporary SQLite file before atomic replacement. The original file is never overwritten if the durability flush fails.

**Safety:** v0.9.0b working copies and `.pinbubackup` archives are retained and remain compatible. The notebook format remains v6. This remains an experimental release: do not test against your only copy of coursework, and remember Dropbox does not provide distributed atomic publish via the file system.

**Regression coverage:** One test emulates Windows refusing `fsync` on read-only descriptors, and one verifies a simulated disk-flush failure preserves the cloud-facing original and unpublished local copy.

# Pinbu Note ♥ v0.9.0b1 — SafeSave & Deduplicated Recovery (experimental)

**Keep v0.8.7c installed and use copies of notebooks for native testing.**
This source candidate has not been built or exercised with a real macOS/Windows
cloud-sync provider in this environment. v0.9.0a's Voice Studio remains present,
but SafeSave is the priority.

## Per-project backup history

Each project has its own independent backup directory:

```
Backups/
  Sociology--e4c...source--7d...project/
    history.pinbubackup       # small index / format descriptor
    assets/                   # unchanged original PDFs and images, once per hash
      ab/<sha256>.bin
    data/
      objects/                # compressed per-tab project and notes manifests
        cd/<sha256>.z
      snapshots/              # five-minute, open and close versions
        2026...json
```

The project name is human-readable, and the source key + notebook UUID prevent
copies or same-titled projects from sharing history accidentally. Snapshots
record the writing Pinbu version, original notebook format, reason, time,
all page metadata and pointers to assets. A deleted page survives in older
snapshots until the associated version expires. Saving another snapshot of
unchanged PDFs does **not** duplicate them. Repeated unmodified large assets
can be reused without re-reading the SQLite BLOB.

- Five-minute backup cycle while Pinbu is open; snapshots skip identical states.
- A **new** snapshot is created on each normal close and notebook switch.
- Default retention **100 snapshots** per project, adjustable 20–1000 in Preferences.
- Original v5/legacy backup files remain untouched by the new backup manager.
- **File → Restore From Backup…** opens a per-project `history.pinbubackup`
  index, a self-contained portable `.pinbubackup`, or older single-file backups.
- **File → Export Portable Backup…** packs `assets/` and `data/` into a
  transferable single `.pinbubackup` ZIP with internal integrity metadata.
- Recovery reconstructs a new `.pinbunote`, never overwriting a notebook.
- **File → Recover Local Working Copy…** helps retrieve sessions retained after
  a publishing conflict or crash.

## Local working copy and explicit publishing

Opening a notebook in the GUI creates a consistent SQLite copy in the OS-local
`Pinbu Note/WorkingCopies` folder. Autosaves update **only that local file**.
**File → Save / Cmd+S / Ctrl+S** first saves locally and then attempts to publish
back to the selected destination, checking for external changes. A detected
conflict leaves both the working copy and original intact. On close, if work
hasn't been published, Pinbu confirms and retains the local copy for recovery.

This relies on local filesystem identity checks, **not atomic distributed
transactions**. Dropbox/OneDrive may synchronise files late; simultaneous
publishes on two devices that haven't synced can still race. Before testing on
real coursework, close all old Pinbu/Yomu versions, test disposable notebooks,
and allow cloud sync to complete between devices.

## Notebook format and compatibility

New saves use notebook container **v6**; this build can read both v5 and v6.
Older released v5-only Pinbu/Yomu builds reject v6 rather than silently
rewriting unknown metadata. They can't display the new, friendlier warning
because those older executable releases can't be updated retrospectively.

## Known limitations / work in progress

- No automatic revision-safe cloud-provider API integrations yet.
- No native UI stress testing on Windows/macOS in this environment.
- The initial per-project history/restore runs synchronously; very large first
  snapshots may temporarily pause the interface.
- No point-in-time restore of one individual annotation: restore a whole
  snapshot to a new notebook for safety.
- A project history directory requires **all** its files; copying only its tiny
  `history.pinbubackup` index is **not** a portable backup. Use Export Portable
  Backup to create a self-contained archive.
- The first SafeSave build uses count-based retention; smarter daily/weekly
  retention, free-space warnings and independent mirrored archives are future
  hardening work.

## Expected packages

- Windows: `PinbuNote_Setup_v0.9.0b1.exe`
- macOS ARM64: `PinbuNote-0.9.0b1-macOS-arm64-unsigned.dmg`
- macOS Intel: `PinbuNote-0.9.0b1-macOS-x86_64-unsigned.dmg`

## Native test checklist

1. Open a copied, disposable notebook from Dropbox, edit it, and check the
   original stays unchanged until explicit Save.
2. Save explicitly and verify changes appear in the original. Let Dropbox sync.
3. Modify the original externally while local changes exist. Verify publishing
   is blocked, original unchanged, and local copy recoverable.
4. Leave a notebook open and trigger a five-minute backup; check its project
   folder contains `assets/`, `data/`, and `history.pinbubackup`.
5. Close without publishing; verify a close backup and recoverable local state.
6. Restore a snapshot from before deleting a page: the page/annotations return.
7. Export a portable `.pinbubackup`, move it elsewhere and restore without
   requiring the original project history folder.
8. Confirm a v0.8.7c app refuses (not rewrites) the new v6 notebook format.
9. Test huge PDFs, missing assets, full disk, interrupted save, crashed process,
   and both OS types before considering the feature stable.
