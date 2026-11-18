# Pinbu Note v1.0 — Core Study Notebook

This is the v1.0 source candidate based on **v0.96** with **v0.97's preview-only dark-reading mode** retained. It does not contain PinbuBoard or the unsuccessful annotation-to-notes linking experiment.

## Included

- Offline, three-panel study workspace: Groups/Individual navigator, page preview, rich-text notes with multiple notes pages
- Existing PDF/image import, vector annotations, OCR, research references, bookmarks, reading progress, Pomodoro, and SafeSave recovery functionality
- High-contrast in-text citation details in dark navigation themes
- F11 fullscreen and a View menu entry on Windows/Linux
- Optional display-only bibliographic page and group labels; switching the preference off preserves original titles
- Minimal Light and Minimal Dark theme choices
- Searchable Help → Keyboard Shortcuts reference (F1)
- Preview-only **☾ Dark** and **Invert** modes for PDFs and other imported page images, with **Original** available by toggling them off; annotations remain separately drawn
- v0.95 security hardening: bounded notebook manifests, safe sharing validation, more conservative failed-save behaviour

## Removed before v1.0

The experimental v0.97 annotation-to-notes feature did **not** function reliably in live use. All of its menu actions, badge objects, special undo callbacks, Qt anchor helper and link metadata write paths have been removed. Existing ordinary PDF annotations and notes remain in place. For a notebook last saved with v0.97, obsolete `annotation_note_links` metadata is **ignored** and dropped on the next save. Previously inserted invisible anchor characters may remain inside rich-text HTML; this release does not automatically strip text or alter user notes to remove them. Keep a backup of v0.97 data if you may want it later.

## Format and data safety

Notebook SQLite container format remains **v7**; the per-tab project manifest remains **v5**. Older `.pinbunote`, `.yomunote` and `.yominote` notebooks continue to be supported as before. Opening an existing notebook with v1.0 should be tested using a **copy** first. Never open the same file simultaneously in old, non-lock-aware versions.

## Build and unsigned deliverables

- Windows: `PinbuNote_Setup_v1.0.exe` (created using the Windows installer scripts)
- macOS Apple Silicon: `PinbuNote-1.0-macOS-arm64-unsigned.dmg`
- macOS Intel: `PinbuNote-1.0-macOS-x86_64-unsigned.dmg`

The source ZIP **does not include these native installers**. GitHub Actions creates an **unpublished draft** after successful platform jobs, and the user must inspect and publish it. Mac DMGs are unsigned and not notarized; distribution warnings are expected.

## Release readiness

Unit tests and static/security checks run headlessly. Native Qt GUI operation, real OCR, voice devices, Windows install/upgrade, and both macOS architectures require on-device/CI acceptance testing **before public distribution**. Smart Dark is a visual heuristic: some photos, complex figures or scans may look unnatural; switch to Original for colour accuracy. The local Voice Studio still requires user-supplied offline speech models and does not download them.
