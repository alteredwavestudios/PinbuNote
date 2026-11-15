# Yomu Note v0.8.6a — Clipboard Images and Photo Annotations 🌸

**Development source build, not an installer or published GitHub release.**

Start from this folder with `RUN_DEV_SAFELY.cmd` on Windows. The development
preferences stay separate from installed v0.8.5. Test with **copies** of
valuable notebooks until the Windows/macOS GUI checks pass.

## Two ways to paste an image

1. **Create a new image page:** Copy a screenshot/image, focus the Individual
   or Groups navigator, and press **Ctrl+V / Cmd+V**, or choose **+Add → Paste
   Clipboard Image as Page**. The new page appears after the selected page
   (or in an explicitly selected group). It's in the shared Undo/Redo history.
2. **Overlay a photo:** Select an existing page in the middle preview, then
   click **Photo** on the annotation toolbar or press **Ctrl+V / Cmd+V** while
   the preview is focused. The image appears as a movable, resizable object.
   Choose **Select** to drag it or use the corner handles; use the Eraser or
   Undo/Redo as for any other annotation. Photo opacity can be changed using
   Quick Edit. Photos are stored with their page and survive Tab Exchange.

**Important:** Ctrl+V in the right-hand notes editor remains normal rich-text
paste and does NOT make a photo or new page. Only clipboard `hasImage()` is
accepted; unsupported clipboard contents show a friendly message.

## Data, memory, compatibility

- Clipboard page images become JPEG assets managed through existing `originals/`
  paths; the original non-JPEG transparency is flattened to white.
- Photo annotations are JPEG-compressed, up to 320 KiB each, 16 per page,
  and 12 MiB for photos across one tab. These limits keep notes portable and
  avoid unbounded manifest JSON. JPEGs are embedded with the mark, NOT left
  behind in a separate image directory. The active preview is the only page
  whose photos are decoded into Qt pixmaps.
- Existing notebook format v5 / tab-project format v4 remains unchanged;
  previously saved highlights, annotations, notes, reading ticks, OCR and
  native text selection remain valid.
- Release builders are versioned for v0.8.6a so an eventual tag cannot produce
  misleading v0.8.5 installers. **Do not tag or publish this candidate until GUI CI and user testing pass.**

## Suggested acceptance checks

1. Clipboard screenshot → navigator paste → Undo → Redo → save/reopen.
2. Clipboard image → Photo on a PDF → move → resize → Undo/Redo → save/reopen.
3. Transfer a photo-annotated page to another tab and back using Undo.
4. Import/export a tab containing photos and images, verify all survive.
5. Paste into the notes editor and verify ordinary text/HTML paste still works.
6. Paste an oversized/malformed clipboard image: confirm safe rejection.

