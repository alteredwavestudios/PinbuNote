# Yomu Note Text Lab — v0.8.3a experimental 🌸

This is a **separate development experiment**, built from public `v0.8.2-rc2`.
It is **not an official release** and is not intended for ordinary users.

## What works in the prototype

- New **Select Text** control next to **OCR** at the top of the preview: click, drag, release and Ctrl+C / Cmd+C to copy native PDF text.
- The normal **Highlight** tool now attempts *text-aware* highlighting on PDF-backed pages. Dragging over multiple lines produces **one annotation** with line-fitted fragments, one Undo entry, and existing colour, opacity, Multiply blending and selection handles.
- The highlight dropdown preserves explicit **Area highlight**, Marker and Straight-line highlighter.
- Native extraction works on PDFs and *converted PDF-backed imports* such as DOCX and EPUB when conversion preserved embedded text.
- Select Text is disabled with tooltip **No text layer available on this page** on scanned/image-only pages, and the top button becomes icon-only in narrow layouts.
- The original JPEG preview pipeline, OCR, image highlighting, existing notes and `.yomunote` format are retained.
- Native geometry extraction runs in the existing PDFium-locked background task system and is dropped at page changes.

## Important experimental limits

- Rotated/cropped PDFs and pages over 25,000 native characters deliberately use the previous non-text-aware tools; native selection is disabled rather than misaligned.
- Selection follows PDFium's underlying character order. Unusual columns, fonts, ligatures and scientific documents may still have incorrect selection/copy ordering.
- This first experiment does **not yet** implement double-click word selection, keyboard selection extension, or edge auto-scrolling.
- Scanned PDFs and images still use OCR and area highlighting.
- Multi-line highlights use the existing `highlight` record with an optional `segments` field; old versions may ignore the segmentation and show an over-broad bounding rectangle. **Use copies of notebooks for the experiment.** Do not edit important notebooks with Text Lab and later open them in v0.8.2 without backup.
- Fully manual GUI and multi-platform installer testing is still necessary. This source kit cannot assert Windows/macOS package verification until it is run on those systems.

## Launch and build on Windows

This clone was produced independently of `H:\dev\Yomu-Note`.

Run `run-windows.bat` from this source folder. It creates its own `.venv` and runs the app directly. For a fully packaged Windows EXE and separate installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-installer-windows.ps1
```

**Installer isolation:** The experiment has a distinct Windows `AppId` and installs to **Yomu Note Text Lab**. It will not upgrade or overwrite the published **Yomu Note** installation. The source has its own separate Git clone and `.venv`.

The Windows build expects Python, Inno Setup and the normal Yomu Note OCR packaging prerequisites on the build computer. No files are ever written to the existing `Yomu-Note` checkout.

## Recommended checks

1. Launch Text Lab with a throwaway notebook.
2. Import a two-line digital PDF, drag over text and copy it.
3. Activate Highlight, drag across two lines and verify one grouped selection/Undo.
4. Use the Highlight dropdown's Area option on a scanned PDF.
5. Reopen the experimental notebook and check the shape positions; test zoom, page switch, OCR and Undo/Redo.
6. Repeat on converted DOCX and EPUB PDFs after conversion has preserved text.
