# Yomu Note v0.8.3b — complete integrated development source

This is a complete source checkout assembled directly from the user-provided
**Yomu-Note-main.zip** baseline. It already includes the v0.8.3a Text Lab,
Select Text UI update and v0.8.3b integration. **No patching, cloning, resuming
or Python build-preparation scripts are required.**

## Windows: how to try it safely

1. Fully **extract this ZIP** in File Explorer to an ordinary folder,
   such as `H:\dev\Yomu-Note-v0.8.3b`. Do **not** run it from inside the ZIP.
2. Open that folder and double-click **`RUN_DEV_SAFELY.cmd`**.
3. The first launch uses `run-windows.bat` to create a local `.venv` and install
   `requirements.txt` if Python and dependencies are needed. Internet may be
   required for the initial dependency installation.
4. Test with a **copy** of an existing `.yomunote` notebook.

The safe launcher sets `YOMU_INTEGRATION_DEV=1`, which uses separate development
QSettings. On first use it **reads/copies UI preferences from normal Yomu Note**;
it never modifies production preferences or transfers automatically reopened
notebooks. Subsequent changes to experimental preferences stay separate.

**Do not run `run-windows.bat` by itself** if you want to keep experimental
preferences separate. **Do not run the installer** yet: the integration restores
Yomu Note's normal Windows installer identity and would be treated as an
upgrade to the existing installation. This is a development source package,
**not a precompiled Windows `.exe`**.

## Integrated features

- Native PDF text layer detection and drag selection, selection Copy, bold
  I-beam Select Text button (disabled + tooltip on image-only pages).
- Word / PowerPoint / EPUB conversions containing a usable PDF text layer can
  also use native selection. Existing OCR/area highlight remains for scans.
- `Select Text` next to `OCR` at upper right beneath **Text selection modes**;
  responsive, equal-sized buttons and an icon-only compact state.
- Right-click selected passage: **Copy Text** or **Highlight Text**.
- Grouped native text highlight as one Undoable annotation, with Multiply
  blending and cumulative darkening when multiple highlights overlap.
- Default **#FFE536**, **80% opacity** for newly applied highlighters. Already
  stored annotations retain their own appearance.
- Auto text-aware highlight when text exists, otherwise area highlight;
  unavailable text-aware menu item is disabled.
- Removing multiple pages via toolbar/context menu and Delete/Backspace in
  either the Group or Individual navigator, in **one Undo step**.
- Theme-accent focus outline on the keyboard-active column.

## Tests and limitations

The generated source was syntax-checked (`compileall`), and 63 focused tests
covering native PDF extraction, vector model, source integration, group
behaviour, tab exchange and data safety passed on Linux. Full PySide6 GUI and
Windows installer builds **could not be executed here**: Qt/PySide6 is not
available in the build environment. Please test interactions before merging.

Native text geometry currently declines rotated/cropped and some unusual PDFs.
Scanned PDFs and images still use rectangular highlighting and OCR. Optional
LibreOffice or Calibre installs remain necessary for some non-PDF imports.

## Merging later

Once tested on Windows, compare this source against your main branch and commit
it in a new feature branch / PR. The complete source was provided instead of
changing your GitHub repository or local working checkout.
