# Pinbu Note v0.96 — Finishing Touches (test candidate)

Built on the original v0.95 stability release. No PinbuBoard code, new notebook
schema, speech-model downloads or OCR language-download service.

* Navigator: readable secondary bibliographic/citation text in dark themes.
* Windows/Linux: F11 fullscreen toggle and View-menu command. Restores a
  previously maximized window when returning from fullscreen.
* Preferences: optional **display-only** reference-based labels for pages and
  groups. Uses existing assignments, inherited references and printed locator
  rules. Original editable page/group titles and notebook data are preserved.
* Appearance: new flat Minimal Light and Minimal Dark themes.
* Help: searchable Keyboard Shortcuts dialog (F1), combining current main-menu
  bindings with documented notes editor and page navigator shortcuts.

## Verification guidance

A full test pass and syntax check were run in the headless development
container; tests requiring PySide6/OS windows are skipped here and must run
on Windows and macOS before publishing. Start with a **copy** of a notebook.
Switch the reference-label preference on, drag a group, reopen, then switch it
back off and ensure original titles remain. Test F11 from normal and maximized
Windows/Linux windows. Check dark-mode bibliographic text in both navigators,
plus the new themes and the Help dialog.

Windows draft installer filename: `PinbuNote_Setup_v0.96.exe`.
