# Pinbu Note ♥ — v0.9.1 release candidate source

**A cosy offline reading and study notebook, inspired by patchwork.**

This is a follow-up **Pinbu Note** candidate of the Yomu Note v0.8.6b development
candidate. It is **not a tested Windows/macOS release**. Do not replace a
working installation without testing with a COPY of your notebooks.

## SafeSave v0.9.1 — Health, quiet autosave footer & optional second backup

The permanent status-bar footer shows a small `Autosave · HH:MM` time after
local saving. Preferences now includes an *optional* independent second backup
folder, a **SafeSave Health & Verify Backups…** window and detailed last-backup
status per location. The new health check can hash-check snapshots and perform
a real temporary restore without touching the original notebook. Primary
backups remain mandatory. See `RELEASE_NOTES_v0.9.1.md` and
`START-HERE-v0.9.1.md` for testing guidance.

## SafeSave fundamentals (experimental)

By default, GUI-opened notebooks run from a private OS-local SQLite working copy.
Autosaves and five-minute backups never write directly to Dropbox/OneDrive/iCloud.
**File → Save** deliberately publishes a checked copy back to the selected
original; a changed original blocks publishing and keeps the working copy.
On close, a fresh, immutable snapshot is created in a local
per-project history, preserving unpublished working copies for recovery.

`Backups/<Readable Project Name>/` contains `assets/` (content-addressed
PDFs/images) and `data/` (compressed metadata objects and versioned snapshots),
with a `history.pinbubackup` index for **File → Restore From Backup…**.
**File → Export Portable Backup…** generates a standalone `.pinbubackup` file
containing both folders; restore creates a separate `.pinbunote` file.

Notebook format v6 is written by this build; it can still read v5 notebooks.
Previously released v5-only Pinbu/Yomu Note builds reject v6 rather than
silently overwriting new data. Do not downgrade an edited v6 notebook.

**Important limitation:** cloud-folder publishing relies on file revision
checks; it is not an atomic Dropbox/OneDrive conditional write. Simultaneous
publishes from devices that have not yet synced can still produce conflicts.
Keep recovery backups, use a disposable test notebook first, and allow cloud
sync to finish before editing from another machine.

**v0.9.0b4:** Save Copy As can explicitly overwrite an existing notebook, but first makes a deduplicated, independently verified **pre-overwrite** snapshot of the **destination's own project history**. Newer app versions trigger a prominent Save as New Copy recommendation; incompatible future notebook formats are protected from overwrite. The cloud original is not targeted by autosave; if it changes to a newer app version while open, Pinbu warns without publishing. See `RELEASE_NOTES_v0.9.0b4.md`.

## Experimental Voice Studio (v0.9.0a)

Edit → Voice Studio opens **Dictation** or **Lecture** mode. Mic access starts
only after clicking Record or Resume, confirming Pinbu's consent prompt and
granting OS permission. Pause and Stop release the microphone immediately.

- Lecture recordings and transcripts live **outside** notebooks, by default
  in your OS Documents folder at `PinbuNotes/Recordings` (Windows, macOS and
  Linux XDG Documents locations). Change this in Preferences → Voice Studio.
- Dictation audio is temporary and deleted when Voice Studio closes; recognised
  text can be inserted into the current notes at the cursor.
- Transcription is entirely **offline** using a user-supplied `whisper-cli`
  (whisper.cpp executable) and local `ggml-*.bin` model. Neither is bundled
  in this experimental source/installer: configure both paths in Voice Studio.
  Without them recording still works, but transcription does not.
- Lecture transcription begins **after Stop**, not during recording, in
  one-minute chunks, with coarse timestamps saved beside the WAV file. Partial
  transcripts are checkpointed on disk; the original WAV is retained.
- An explicit GUI smoke test is still required on Windows and macOS for OS
  microphone permissions, device format fallback, transcript insertion and
  long recording recovery. Do not publish as a stable feature yet.

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
