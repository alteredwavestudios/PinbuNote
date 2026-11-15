# Yomu Note v0.8.5 — Reliability and Performance 🌸

**Public-preview / pre-release candidate.** This version promotes the successful
v0.8.4a → v0.8.4b → v0.8.4c development work into one candidate for GitHub
source tests and native installer verification. The portable `.yomunote`
SQLite notebook schema remains **v5**. No migration or manual import is required.

## Reliability and data integrity

- Original PDFs, images and converted page sources are checked when loading
  and saving. Missing assets report an error rather than silently producing
  a notebook with broken pages.
- Page moves/copies between tabs are staged and committed transactionally;
  failures roll back the file operations and tab manifests. The entire move
  is one Undo/Redo operation, preserving annotations and reading status.
- Undoing a transfer into an originally empty tab immediately clears its
  stale preview and title.

## Performance and memory

- Native PDF text selection uses a bounded, precomputed per-page glyph index
  instead of repeatedly scanning every glyph while dragging the pointer.
- Multi-tab persistence coalesces unchanged manifest writes and performs one
  SQLite commit for groups of editor changes.
- Idle autosave uses a frozen revision-aware metadata snapshot written by a
  background worker on a private SQLite connection; an older worker cannot
  overwrite a newer manual save. Failed jobs remain retryable.
- Tab Exchange staging and final SQLite commit run in background tasks with
  rollback on failure. The final atomic commit cannot be cancelled mid-write.
- Inactive Groups and Individual navigation icons are released; old disposable
  JPEG caches receive bounded low-priority trimming. Source PDFs, images,
  notes and annotations are not removed by that cleanup.

## Preserved features

Native PDF text selection and text-aware highlighting, scanned-page offline
OCR, Smart Import, page groups, reading completion, annotations, rich-text
notes, tables, project tabs, Tab Exchange, Undo/Redo and kawaii themes.

## Limitations and release checks

- **Explicit Save, notebook closing and backups remain synchronous** so the
  app can confirm writes are durable before leaving the notebook.
- The Windows setup still preserves the existing Inno Setup **AppId** and the
  PyInstaller **matching SQLite DLL repair**, installed-executable smoke test
  and **bundled Tesseract OCR** verification. No setup-time app auto-launch.
- Mac builds remain unsigned/unnotarised; Linux distribution remains source-only.
- A green source test suite is not sufficient to publish the release. Validate
  the installed Windows EXE with existing notebook copies, text selection,
  autosave, import/export and OCR. Test macOS where machines are available.

## Expected draft-release downloads

- `YomuNote_Setup_v0.8.5.exe` — Windows x64 installer
- `YomuNote-0.8.5-macOS-arm64-unsigned.dmg` — Apple Silicon
- `YomuNote-0.8.5-macOS-x86_64-unsigned.dmg` — Intel macOS
- `SHA256SUMS.txt` — download hashes

**These are expected GitHub Actions outputs, not binaries included in this
source archive.** The workflow creates an unpublished **draft pre-release**
only after all three native packaging jobs succeed.
