# Yomu Note v0.8.4a 🌸 — Reliability candidate

**Not yet a published pre-release.** Source-only build for user acceptance,
code review and cross-platform CI. Based on published v0.8.3b Text Lab.

## Data integrity changes

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
- Deferred: GUI-thread save batching/workers, converter sandboxing, PDF text
  hit-testing optimisation, and broader fuzzing/stress tests.
- No notebook schema changes, no background/cloud transcription, no new network service.

## Candidate installer asset names (only after separate CI/build verification)

- `YomuNote_Setup_v0.8.4a.exe`
- `YomuNote-0.8.4a-macOS-arm64-unsigned.dmg`
- `YomuNote-0.8.4a-macOS-x86_64-unsigned.dmg`

**Release gate:** Test native UI behaviour, Undo/Redo, old notebook opening,
local/offline OCR and the installed Windows runtime before publishing.
