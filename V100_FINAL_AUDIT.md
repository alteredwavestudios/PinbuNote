# Pinbu Note v1.0 — Final stability, security and performance audit

**Scope:** Full-source, headless release candidate built from v0.96 plus the independent preview-only dark-reading behaviour introduced in v0.97. The failed experimental annotation-to-notes system was removed; **no PinbuBoard code** is shipped.

**Verdict:** Source-level checks pass. **Not yet cleared for a public native binary release** because this Linux testing container has no PySide6 Qt runtime, Windows, Mac, or installer execution environment.

## 1. Implementation and rollback

- Restored `yomunote/window.py` and `yomunote/project.py` from the pre-link v0.96 release, then carried forward only v0.97's preview Dark/Invert controls, raster-colour adapter, per-user mode preference, and dark-compatible annotation blend mode.
- Removed `annotation_notes.py`, `note_anchor_qt.py`, their menu/badge/UI operations, linked undo coupling, and the special `annotation_note_links` write field. The v0.97-only link test file was removed and replaced with release-level regression tests.
- Preserved existing PDF vector annotations, sticky notes, photo annotations, research references, multiple notes pages, existing rich-text links, bookmarks, SafeSave backups, and page/group navigation.
- Corrected Smart Dark's slightly tinted near-black text treatment: the colour-preservation mask now depends on luminance as well as saturation, keeping near-black printed ink legible. The source PIL image remains unmodified.
- v0.97 link metadata is treated as an **unknown legacy field** when opening a saved Project. It is omitted when the Project next saves, with normal notes and annotations retained. Deliberately, no automatic rich-text character stripping is performed; previously inserted invisible word-joiner anchors may remain because indiscriminate deletion could damage user text. Keep an original copy of notebooks last edited in v0.97 if those obsolete links matter.
- Notebook storage format **v7**, per-tab Project format **v5**, and the Windows installer **AppId** are unchanged.

## 2. Source and test results

| Check | Result | Limitations |
|---|---|---|
| Integrated regression suite | **652 passed; 56 skipped; 3 additional subtests passed** | Qt-dependent tests skipped due to unavailable PySide6 |
| Independent per-file watchdog | **154/154 modules completed**: 104 passed, 50 skipped, **zero failed or hung** | Modules run in separate isolated settings with a 90-second limit; roughly 374 s total |
| Python source compilation | **PASS** for main, app, OCR scripts, tests | Syntax only, not native GUI startup |
| Removed-feature guard | **PASS** | No remaining annotation-notes module, badge, UI callback, or special Project field |
| Legacy v0.97 compatibility | **PASS** for Project JSON and complete SQLite notebook | Tested using disposable synthetic notebooks; original notes retained; defunct metadata removed on save |
| Old/new release version protection | **PASS** | `1.0` is newer than `0.97` and `0.95`; saved app version `1.01` is rejected as future |
| Archive integrity | See source ZIP SHA256 and ZIP verification in package | Not a signed or notarised installer |

**Environment:** Linux, Python 3.13.5 for this run. The project targets Python 3.12 for native release builders; it must also pass there. The source-only audit does **not** establish that Qt toolbars, dark rendering, cursors, F11, OCR, microphone permissions or complex text editing behave correctly on a native desktop.

## 3. Focused security observations

- Reviewed 62 application/script Python modules with a source/AST scan: **no direct Python `eval`/`exec`, pickle or marshal deserialisation, `os.system`, `shell=True` subprocess, or dangling relative-module imports** found.
- Five calls through the `subprocess` API remain for external converters, OCR, voice transcription and Windows frozen-application verification. They are pre-existing trust boundaries, not new v1.0 features; they must be smoke-tested on the target OS and are not equivalent to arbitrary shell execution.
- Existing v0.95 regressions exercise 32 MiB bounded SQLite manifest loading across the application, reject oversize and Unicode-byte-count bypasses, prevent external file overwrite conflicts, reject hostile notebook asset paths and unsafe sizes, and test recovery behaviour.
- The default notebook opening process works on a private local session copy instead of overwriting a cloud original during autosave. Cloud sync itself cannot provide an atomic conflict-free publish across unsynchronised devices.
- Native libraries (Qt, PDFium, Pillow, Tesseract) remain potential security boundaries for untrusted PDFs/images; this audit is not a dependency CVE scan, binary fuzz test, or penetration test. Keep package pins updated and verify downloaded installer provenance.

## 4. Synthetic performance observations

Measurements below are from disposable test data on the auditing Linux machine, not a real app-frame-rate benchmark. Disk caches and CPU state affect absolute timings.

| Operation | Result |
|---|---:|
| 100-page **metadata-only** SQLite notebook: open / unchanged save | 0.0039 / 0.0014 s |
| 1,000-page **metadata-only** notebook: open / unchanged save | 0.0073 / 0.0058 s |
| 5,000-page **metadata-only** notebook: open / unchanged save | 0.0259 / 0.0223 s |
| Smart Dark Pillow transform, 1.4 million pixels | ~0.059 s |
| Smart Dark Pillow transform, 2.8 million pixels | ~0.076 s |
| Very large 3.2-million-pixel preview (uses inversion fallback) | ~0.073 s |
| Peak process RSS during this synthetic benchmark | ~207 MiB (212,256 KiB) |

The performance logic only modifies decoded preview rasters and discards them when the page leaves view. No original PDFs, OCR assets or long-lived page caches are recoloured. **Performance is not yet measured for 500-page PDF scrolling, GUI animation, note editor typing, annotation resizing or memory use over a multi-hour native session.**

## 5. Version, packaging and GitHub Actions review

- Versioned application metadata: `yomunote.__version__ = '1.0'`, Inno Setup `MyAppVersion = '1.0'`, Windows executable file version `1.0.0.0`, builder scripts and expected asset filenames are aligned.
- CI release workflow checks the tag matches the source version and requires Windows plus both Mac architectures before producing a **draft**; it does **not automatically publish** a release.
- Intended assets: `PinbuNote_Setup_v1.0.exe`, `PinbuNote-1.0-macOS-arm64-unsigned.dmg`, and `PinbuNote-1.0-macOS-x86_64-unsigned.dmg`.
- **These native binaries were NOT built or executed in this environment.** macOS images remain unsigned and unnotarised. Earlier GitHub Actions history proves older macOS release jobs worked, but does not prove this v1.0 build passes. A previously cancelled 15-minute macOS source job had no assigned runner and cannot be interpreted as a source-code failure.

## 6. Remaining publication blockers / native acceptance checklist

1. On Windows: launch from a fresh Python 3.12 venv, create and reopen notes, import PDF/image, use OCR, change all reading modes and verify the originals are unchanged, F11, themes, F1 Help and Save/Restore; build Inno installer and verify a clean install **and upgrade**.
2. On Apple Silicon **and** Intel: run the regression suite with PySide6, build both unsigned DMGs, launch the actual `.app`, verify the bundled Tesseract assets and test opening/saving notes and Smart Dark; assess signing/notarisation needs before wider distribution.
3. Test UI performance: several hundred PDF pages, multiple annotation types, repeated zoom and theme switching, thumbnail memory release, long sessions, editor undo/redo, and closing during an in-flight save.
4. On a notebook copy, verify real-world legacy `.yominote`/`.pinbunote` opening, v0.97 downgrade compatibility, SafeSave recovery after a simulated failed publish, and normal cloud conflict handling.
5. Verify final checksums, inspect CI results and the unpublished draft artifacts, then publish manually only after acceptance.

## Reproduce this audit

From the extracted source directory, after installing its dependencies:

```bash
python -m compileall -q main.py yomunote ocr_packaging scripts tests
python -m pytest -q
python YomuNote-Full-Test-Audit.py --per-file-timeout 90
```

The audit evidence ZIP includes the local integrated test log, full isolated-module watchdog ZIP, synthetic performance data, security scan results, and scripts used to generate the additional performance/security results.

**Final classification:** v1.0 **source candidate passes the available automated checks**; native platforms and installer verification are outstanding, so it would be inaccurate to claim v1.0 is completely validated or publicly release-ready yet.
