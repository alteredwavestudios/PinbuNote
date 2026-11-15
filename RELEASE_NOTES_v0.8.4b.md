# Yomu Note v0.8.4b 🌸 — Reliability + performance candidate

**Not yet a published pre-release.** Source-only build for user acceptance,
code review and cross-platform CI. Based on published v0.8.3b Text Lab.

## What's new since the working v0.8.4a candidate

- Fix stale preview after Undo moves the only page out of a tab. An empty tab
  immediately clears its previous PDF, annotations and page caption, and
  invalidates in-flight preview render callbacks. No tab-switch refresh needed.
- Coalesce multi-tab saves into a single portable SQLite notebook commit when
  closing a window/notebook, switching notebooks, exporting a clean copy,
  preparing Tab Exchange, and before cross-tab transfer/Undo. This avoids the
  repeated full-manifest scan and commit after every tab editor is serialised.
- On any failed batched save, already-serialised editors are marked dirty so
  their autosave timer can retry; a failed close continues to be blocked.
- Speed up Text Lab drag hit-testing with a bounded vertical glyph index
  prepared on the PDF worker thread. Maintain the previous nearest-glyph
  semantics, selection text and highlight geometry.
- Preserve v5 notebook format, existing highlight defaults, OCR, installed
  application ID, SQLite DLL repair and offline OCR release checks.

## Data integrity changes inherited from v0.8.4a

- Refuse notebook saves when a live source, converted render PDF or page image
  is missing or an unsafe symlink. Absent assets can no longer be silently
  omitted from an otherwise valid-looking notebook file.
- Detect previously saved notebooks that reference missing assets on load,
  with an actionable error. The original file is not altered on failure.
- Cross-tab copy/move now stages media first, writes both tab manifests, and
  makes ONE durable SQLite commit. On a failed copy/manifest/SQLite save,
  both working manifests are restored and the staged media is discarded.
- Cross-tab copy/move is now one shared Undo/Redo operation, preserving notes,
  completion state, annotations and page reading positions where applicable.
- Avoid unnecessary SQLite rewrites when a JSON project manifest has merely
  acquired a new modification timestamp without changing its contents.

## Not included in this stage

- No new clipboard-image paste or voice transcription yet.
- Still deferred: truly asynchronous SQLite writing using immutable snapshots,
  Tab Exchange commit off the GUI thread, converter sandboxing, full disk-cache
  quotas, and broader fuzzing/stress tests.
- No notebook schema changes, no background/cloud transcription, no new network service.

## Candidate installer asset names (only after separate CI/build verification)

- `YomuNote_Setup_v0.8.4b.exe`
- `YomuNote-0.8.4b-macOS-arm64-unsigned.dmg`
- `YomuNote-0.8.4b-macOS-x86_64-unsigned.dmg`

**Release gate:** Test native UI behaviour, Undo/Redo, old notebook opening,
local/offline OCR and the installed Windows runtime before publishing.
