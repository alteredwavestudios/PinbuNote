# Pinbu Note v0.8.7a — Patchwork rebrand and sticky-note placement

**Development source, not a signed or tested production installer.** Based on the
uploaded Yomu Note v0.8.6b source. Notebook database schema remains v5.

## Changes

- New product/window/About/installer display name: **Pinbu Note**.
- Wordmark: **Pinbu ♥** in the existing rounded-font family with small,
  widely tracked **NOTE** below. Tracking is a percentage of glyph size.
- New icon based on a bespoke patchwork plush study companion; platform
  PNG/ICO/ICNS assets provided (original art in assets/).
- Three ADHD-conscious patchwork themes use gently different shelf/canvas/
  notes-backdrop colours while keeping PDF and editor paper calm.
- Sticky composer now supports alignment, optional paper background,
  percentage-based letter spacing, and visible plain-text bullet lines.
- Sticky placement: compose first, then click anywhere on the page to place it;
  moves and resizes now commit to the saved annotation, with Undo/Redo.
- New GUI notebooks use `.pinbunote`; older `.yomunote` and `.yominote`
  remain openable and importable. Internal file format and page links are not
  changed. QSettings are separate from the legacy product.
- Windows installer/CI and macOS DMG build scripts use the new product name.

## Intentional compatibility choices

- Core `yomunote` Python package/module filenames remain in place in this
  first migration build to preserve imports, plugin paths and hundreds of
  existing regression tests. Internal renames can follow after native tests.
- The old Windows Inno Setup AppId is retained so installation can upgrade
  the same product; upgrade/uninstall behaviour must be smoke-tested.
- The old notebook lock, external-write detection and offline OCR routines are
  preserved. Do not edit the same notebook in an older version simultaneously.
- Existing `yomu://` document links remain understood by the application.

## Native acceptance checklist

1. Test with *copies* of existing `.yomunote` notebooks, including rich text,
   OCR, page groups, bookmarks, annotations and Tab Exchange.
2. Create a fresh `.pinbunote` notebook, close/reopen, drag-drop and export
   tabs; check file association double-click on Windows.
3. Place a sticky at corners and in the middle; drag it and resize it, save,
   reopen and use Undo/Redo. Check old saved sticky annotations still render.
4. Try left/centre/right alignment, bullets, 80/100/125% tracking, 8/24/48pt
   type, and a transparent background with both light and dark documents.
5. Check all three new palettes and every existing theme, including UI at
   narrow column widths, colour contrast and reduced-motion preference.
6. Run CI source regression and native Windows installer/SQLite/OCR smoke test;
   run both macOS architectures; check macOS app icon and English OCR bundle.
7. Ensure launching a `.pinbunote` argument opens that file. Test that the
   older Yomu application remains intact if installed side-by-side.

Native GUI/installer testing has NOT been performed in the current environment.

Expected Windows installer after native build: `PinbuNote_Setup_v0.8.7a.exe`.
