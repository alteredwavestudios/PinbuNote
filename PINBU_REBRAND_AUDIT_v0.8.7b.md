# Pinbu Note v0.8.7b — rebrand and performance audit

**Source baseline:** tested Pinbu Note v0.8.7a (derived from Yomu Note v0.8.6b).
**Status:** static Python checks and non-GUI regression tests passing; native Windows/macOS GUI and performance remain to be tested on target machines.

## Visible branding corrected

- About popup now says **Pinbu ♥** with a smaller, widely spaced **N O T E**, rather than the old Yomu/Japanese slogan.
- Focus settings and focus-timer tooltip now use Pinbu, as do the offline OCR reinstall prompt and notebook-lock conflict messages.
- Recovery dialog permits selecting Pinbu or legacy Yomu backups.
- New default backup and log folders use **Pinbu Note**. Files in old Yomu folders are not moved or deleted; users can browse to their old backups in Restore.

## Bookmark visibility

- Bookmark ribbons are drawn on the **Individual** thumbnail, group navigation page row and main page preview.
- Ribbons are vector-only GUI decorations. They are NOT burned into the scanned PDF, original image or a generated thumbnail cache.
- Bookmark/rename/remove and Undo/Redo update the visible badge without rebuilding the group tree or rerendering the PDF.
- Offscreen thumbnails still follow the 20-item cap.

## Sticky-note polish

- **Select** a sticky note and Quick Edit shows **Sticky font size** (6–72 pt). A finished change is a single Undo/Redo step; full composer remains available on double-click.
- Bullets toggle only the selected/current lines. Indentation is preserved; mixed selections do not duplicate existing bullets; a blank line can start a bullet.
- The editor no longer applies block formatting across its entire document for each font, alignment or colour preview. The previous approach caused unnecessary layout/undo work and may have contributed to perceived sluggishness.

## Performance work (plausible bottlenecks, not benchmark proof)

- Group-tree `find_item()` previously walked the full hierarchy for each visible image and navigation change. It now uses **QPersistentModelIndex** for steady-state lookup and falls back to tree traversal if a Qt drag/drop move invalidates an index.
- Bookmark drawing reuses existing navigation painting and a single tiny preview graphics item; it adds no page pixmaps or asynchronous render jobs.
- Existing PDF cache caps, thumbnail laziness, global PDFium lock, preview sharpening and autosave schedule are left untouched.

**Native test request:** compare v0.8.7a and v0.8.7b with the same copied notebook, checking initial load, scrolling thumbnails, page switches, sticky selection/Quick Edit, and long multi-line bullet notes. Consider turning on Reduce animations temporarily to distinguish animation GPU repaint from reading/annotation latency.

## Deliberately preserved legacy identifiers

- Python package `yomunote` and `YomuNote-Full-Test-Audit.py` are still internal implementation paths. Renaming them should be a separate tested migration, not mixed with UI fixes.
- `.yomunote` / `.yominote` extension support, `yomu-notebook` SQLite magic, `yomu://` historical page links, `application/x-yomu-notebook-pages` drag-drop MIME and `YOMU_SPACING_V1` notes metadata are deliberately retained to preserve older notebooks and workflows.
- `QSettings('Yomu Note', 'Yomu Note')` remains as a read-only settings migration source.
- Historical release notes, user guides, screenshots and published GitHub release URLs still correctly refer to Yomu Note.

## Safety

- Do not open/edit the same notebook in an old non-cooperating Yomu Note version and the current Pinbu Note version simultaneously. Native tests should use a **copy** of an existing notebook.
- Native Windows/macOS installer compatibility and responsive GUI behaviour were not executable in the source-build environment.
