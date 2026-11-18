# Pinbu v0.9.2a — First research build 🌸

This is experimental source, **not** a stable replacement for v0.9.1.

## Try these controls

1. Open a **copy** of a notebook and switch the navigator to **Groups**.
2. Right-click your book's parent group → **Research · References & Tags** →
   **New reference…**. Select *Book*, enter author, title, year and publisher.
3. Right-click a page inside it → **Copy Reference → Bibliography · formatted**.
   Paste into Word, Google Docs or Pinbu's notes editor and inspect italics.
4. Right-click the group → **Bulk printed-page offset…**, map PDF page 7 to
   printed page 1. Right-click its PDF page 7 → **Copy Reference → In text ·
   with printed page**. It should now use `p. 1`.
5. Create a research tag on the group. Right-click its child page to see the
   inherited tag checked; uncheck it on one page to mask it there only.
6. Right-click the navigator → **Find pages by research tag…** to jump to a
   tagged page.
7. Right-click a page and override its printed page number. Try Undo and Redo,
   save, close, reopen, and restore from a SafeSave snapshot.
8. Ungroup some pages; their effective citations, tags and labels should remain.

## First chapter reference

Create a separate parent *Book* reference for an edited collection, filling
in its editors and publisher. Then create a *Chapter in edited book* reference
on a subgroup, choosing that book in the **Parent edited book** selector.
Enter the chapter's own author/title/page range. The live preview will use
both records without copying the entire book metadata into every chapter.

## Build/run

Windows: extract ZIP, use `run-windows.bat`; to package, run `build-windows.ps1`
then `build-installer-windows.ps1` on a Windows development machine.

macOS: extract ZIP, run `./run-mac.command`; to package use `build-mac.command`
and `scripts/package-macos-dmg.sh`.

Run tests: `python -m pytest -q` with Python and requirements installed.

## Important compatibility note

Opening/saving a notebook with v0.9.2a upgrades the notebook container to
**format v7** and tab manifest to **v5**. v0.9.1 cannot safely write that
notebook; keep a separate copy in case you roll back.

**SafeSave still does not guarantee distributed conflict-free Dropbox writes.**
Test on disposable notebooks first and verify actual recoveries.
