# Yomu Note v0.8.6b — Development Testing 🌸

Unzip the **complete source ZIP** to a new directory such as
`H:\dev\Yomu-Note-v0.8.6b`, and double-click `RUN_DEV_SAFELY.cmd`.
It uses the separate development QSettings namespace and does NOT replace the
installed v0.8.5 release. Work against a **copy** of a real notebook.

### Windows manual checklist

1. Open two v0.8.6b windows and try opening the same `.yomunote` in each.
   The second attempt must display **Notebook already open** and must not
   offer to recover/overwrite it. Open *different* notebooks in each instance
   to confirm multi-window use remains possible. Restart after force-closing
   a dev instance; stale lockfile alone must not block reopening.
2. On an image/PDF page choose **Sticky**, type text, change paper colour,
   font, size, bold/italic and Save. Drag, resize, double-click and edit again.
   Check Undo/Redo, save/close/reopen, and move the page between tabs.
3. Right-click a page in **Individual** and **Groups** to bookmark it.
   Reorder pages, jump via **Bookmarks**, rename a bookmark, navigate across
   tabs via the app-wide **Bookmarks** menu, and confirm deletion/Undo.
4. Test photo annotations, Ctrl+V image pages, native text selection, OCR,
   autosave and tab exchange for regressions.
5. **Do not test mixed-version concurrent edits on a valuable notebook.**
   Older installed versions cannot honour the new cooperative lock.

The `.yomunote.lock` sidecar file is harmless; it deliberately remains on disk.
Closing a window releases the live OS-level file lock immediately.
