# Pinbu Note v0.9.2b — Research Navigator Display (experimental)

**Please test on disposable notebook copies.** This is a source preview; native
Windows/macOS GUI and installer checks have not been completed. The v0.9.2a
research engine and SafeSave v0.9.1 remain intact.

## New features

- Page-number badge at the bottom right of each page row in Groups and
  Individual views. Click to cycle **Printed**, **Source PDF/Slide**, and
  **Tree order**. Missing printed numbers are skipped. No page number ever
  changes merely because its display mode changes.
- Filled ◆ denotes a directly assigned page reference; outlined ◇ denotes
  a group-inherited reference. Untagged/unreferenced pages show numbers only.
- Hover the number for its meaning; hover the row for the title and research
  summary (or complete rich-text bibliography when selected in Preferences).
- Right-click a page → Page number display for explicit mode selection or reset.
  In Groups view, Alt+N also cycles the selected page's badge.
- Preferences → Page navigator controls the default numbering mode, optional
  author/year vs tags vs short title and row hover format. User-selectable
  presentation is separate from the underlying bibliography.
- The number resolver makes one pass over the group tree and reuses stable
  page IDs. No extra thumbnails are decoded.

## SQLite format and safety

**No database schema or project research fields were added** in v0.9.2b.
The notebook remains container v7 / per-tab project v5 / backup v1.
Existing `research.references`, `reference_assignments`, `numbering`, and
`tags` are the sole bibliographic source of truth. Computed number badges and
formatted bibliography strings are transient UI data, not written to SQLite.
Per-page display mode overrides use one small JSON mapping per notebook-tab
within the application’s QSettings preferences and are pruned on reload.

Library-wide bibliography deduplication and cross-notebook reference
reconciliation remain future work; this release deliberately does not alter
the existing SafeSave and tab-transfer contracts.

## Validation

Run `python -m pytest -q` in the extracted source folder. Qt GUI tests need
a real PySide6 installation on Windows/macOS; optional GUI tests are skipped
on minimal/headless hosts lacking Qt.

Windows installer staging: `PinbuNote_Setup_v0.9.2b.exe`.
macOS staged DMGs: `PinbuNote-0.9.2b-macOS-arm64-unsigned.dmg`,
`PinbuNote-0.9.2b-macOS-x86_64-unsigned.dmg`.
