# Yomu Note v0.8.4c — Stability and Performance, Part 2

**Development candidate** — do not install over the published v0.8.3b release.
This build is based on v0.8.4b and preserves the v5 `.yomunote` SQLite format.

## Implemented

- Idle autosave now captures immutable per-tab JSON metadata on the GUI thread
  and writes the SQLite notebook in a background task using a separate SQLite
  connection. PDF/image data streams in bounded chunks; no full-document raster
  cache is included. A versioned save guard prevents a late worker overwriting
  a more recent manual save. Changing an asset mid-copy aborts the transaction.
- Multiple idle autosaves coalesce. Failed saves mark their source panes dirty
  for retry. Explicit Save, Save on Exit, structural transfers, and backup safety
  still use the proven synchronous path and serialize behind active writers.
- Frozen snapshot metadata uses a 96 MiB memory ceiling. Larger metadata falls
  back to the original writer instead of risking memory exhaustion.
- Tab Exchange now performs BOTH staging and final SQLite commit on workers.
  The import dialog remains modal; cancellation is disabled for its final
  atomic commit phase. UI widgets and Undo history are updated on the GUI
  thread only AFTER the transaction finishes.
- Switching away from a tab releases both Individual AND Groups thumbnail
  icons. Old disposable JPEG caches are pruned once per activation on a low
  priority worker, with separate folder byte/count budgets. Original PDFs,
  page assets, notes and annotations are never removed by this cleanup.
- Regression tests for frozen snapshots, stale jobs, asset changes, closure,
  cross-thread import, rollback and cache trimming.

## Deliberate limitations

- Explicit manual saves, notebook close and periodic backup still may wait on
  SQLite; it would be unsafe to make them fire-and-forget before introducing
  durable acknowledgement and shutdown handling for all entry points.
- Tab Exchange performs source inspection and its initial editor flush on the
  GUI thread; these are not yet fully asynchronous.
- Background writers do not perform UI work or hold SQLite connections across
  threads. The final visual/installer checks require Windows/macOS testing.

## Draft release asset names (future CI build only)

- `YomuNote_Setup_v0.8.4c.exe` — Windows x64 installer.
- `YomuNote-0.8.4c-macOS-arm64-unsigned.dmg` — Apple Silicon.
- `YomuNote-0.8.4c-macOS-x86_64-unsigned.dmg` — Intel macOS.

These are target filenames in the build scripts, **not** files included in
this source candidate. Do not create a release tag until GUI testing passes.

## Suggested manual checks

1. Edit several notes, leave the program idle for 60 seconds, save/close/reopen
   and verify no content is missing.
2. Edit immediately after autosave starts, manually save, reopen, and verify
   that the newer text wins.
3. Import tabs containing large PDFs; confirm the finalization dialog remains
   responsive to the OS and the imported tab supports one-step Undo/Redo.
4. Navigate to Groups thumbnails, switch to another tab and back, and verify
   icons reload normally. Test PDF text selection and old notebook reopening.

All production installer identifiers and the Windows SQLite/OCR safeguards
remain unchanged. This source build has not been locally tested in the native
Qt GUI and is **not** a replacement for the known-working v0.8.3b installer.
