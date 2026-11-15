# Yomu Note v0.8.6b — Sticky Notes, Bookmarks & Notebook Safety 🌸

**Development candidate; not a published release.** Built on the user-tested
v0.8.6a clipboard images and photo annotations, preserving the v5 SQLite
notebook format and v0.8.5 performance improvements.

## New features

- **Skeuomorphic sticky notes:** click *Sticky* beneath the page preview,
  write up to 8,000 characters, choose a paper background, font family, point
  size, bold and italic. The page-local note has a folded corner, subtle shadow,
  gradient paper texture and selectable corner handles. Select to move/resize;
  **double-click to edit**. Text and appearance edits are undoable together.
- **Page bookmarks:** add, rename or remove a bookmark from an Individual or
  Groups page context menu. Jump via the navigator's **Bookmarks** dropdown,
  or the app-wide **Bookmarks** menu (including across tabs). Bookmarks use
  stable page IDs: reorder and cross-tab move keep their targets; deleting a
  page removes the attached bookmark. No new notebook schema.
- **One editable session per notebook:** an OS-level lock prevents TWO newer
  Yomu Note versions from simultaneously editing the SAME notebook, while
  different notebooks remain independent. Lockfiles survive crashes harmlessly:
  the operating system releases the lock automatically.
- **External edit detection:** if an older version or file-sync tool writes
  the SQLite notebook during an open session, *this version* refuses a later
  save instead of blindly overwriting someone else's edit. A failed autosave
  is not treated as a successful one. Exit offers an explicit discard option
  for a detected external conflict; Cancel retains the live session.

## Limits of the lock

- **Existing published versions do NOT honour the new sidecar lock.** The
  on-disk check detects an older version's external change before OUR next
  save, but cannot block the old process from saving. Do not open the same
  notebook in pre-v0.8.6b and v0.8.6b simultaneously.
- OS file locks are LOCAL to a machine. They cannot coordinate edits between
  two different computers using Dropbox, iCloud, network copies or sync.
  Keep sync/version-history backups for those cases.
- Sidecar files named `<notebook>.yomunote.lock` are normal and may remain
  after closing; do NOT remove them while the notebook is in use.
- Sticky notes use a uniform font/style per note, not per-character rich text.
- This source candidate is not yet tested in a native Windows/macOS GUI.

## Testing

Python unit/integration and cross-process lock tests run without Qt.
The GUI interactions still require a native Windows/macOS test before a release.
Installer publishing is **not** authorised by this development ZIP.

Expected future installer filename after native CI: `YomuNote_Setup_v0.8.6b.exe` (not built in this package).
