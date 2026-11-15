Pinbu Note ♥
ピンブノート

Little pieces, big ideas.

A cosy, offline study companion for Windows and macOS. Organise your readings, annotate documents, collect notes and stitch your ideas together.

Current version: v0.8.7c

Highlights: Three-column workspace, PDF and document importing, OCR, rich-text notes, movable sticky notes, bookmarks, reading progress, Pomodoro, notebook exchange, custom themes and flexible page scrolling.

Theme collections: Japanese & Kawaii, Pinbu Textiles, French Art Nouveau, Modern & System.

## What's new

- Responsive **Pinbu ♥ / NOTE** wordmark and new patchwork mascot icon.
- Three low-noise patchwork themes: **Pinbu Patchwork**, **Silk Sampler** and
  **Indigo Stitch**, with visually distinct pane surfaces and calm editor paper.
- Sticky notes: edit font size from Quick Edit; improved bullets and lighter preview;
  choose location with a click after writing; saved positions now
  move and resize through Select; configurable paper background, alignment,
  plain-text bullet toggling and percentage-based font tracking.
- Bookmarks now show a small ribbon on the page thumbnail and preview.
- New notebooks created from the GUI use `.pinbunote`. Existing `.yomunote`
  and `.yominote` files remain supported for opening and tab importing.
- App-specific settings are stored separately; non-sensitive visual preferences
  can be copied from the older Yomu Note settings without modifying them.

## Build

Install Python 3.12 and dependencies from `requirements.txt`, then run
`python main.py`. On Windows run `run-windows.bat` followed by
`build-windows.ps1` and `build-installer-windows.ps1`. On macOS run
`run-mac.command` followed by `build-mac.command` and
`scripts/package-macos-dmg.sh`. Native OCR assets are assembled only
on the target platform. GitHub Actions can build all installable assets
from a version tag; its draft-release workflow never publishes automatically.

**Compatibility caution:** do not open the same notebook simultaneously in
an older Yomu Note process and Pinbu Note. v0.8.6b introduced a per-file
lock, but older released versions do not cooperate with that lock.

## Historical Yomu Note source documentation

The original user and developer documentation remains in this archive, with
historical screenshots and release notes retained for context. See
`RELEASE_NOTES_v0.8.7b.md`, `START-HERE-v0.8.6b.md`, and
`docs/BUILD_RELEASES.md`.

---

**v0.8.6b baseline:** Historical user manuals and screenshots are included in
`docs/`, but they may still show the earlier Yomu Note interface. The present
source package is a separate, unpublished Pinbu Note development candidate.

## Historical release and visual reference

The last previously published Yomu Note release was **v0.8.3b**; its
[downloads](https://github.com/alteredwavestudios/Yomu-Note/releases/tag/v0.8.3b)
remain historical and have not been replaced by this source candidate.
The v0.8.6b baseline added **Reading View Memory** and sticky notes.
Screenshots of the earlier interface (not the new patchwork branding):

- ![Historical three-column interface](docs/screenshots/01-interface.png)
- ![Historical OCR dialog](docs/screenshots/02-ocr.png)
- ![Historical reading-progress UI](docs/screenshots/03-reading-progress.png)
- ![Historical tab exchange](docs/screenshots/04-tab-exchange.png)
