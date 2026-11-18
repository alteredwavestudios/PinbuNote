# Pinbu Note v0.96 — source test candidate

This continues from v0.95 and does **not** include PinbuBoard.

**Windows:** extract the whole ZIP, then run `run-windows.bat` (or use an
existing venv and `python main.py`). For an installer build, follow
`docs/BUILD_RELEASES.md` and use the updated Windows scripts.

**macOS:** use `run-mac.command` on an appropriate environment.
**Linux:** use `run-linux.sh` with the documented libraries.

After starting the application:

1. Choose Minimal Light and Minimal Dark in View → Colour Theme.
2. Open a notebook with references; enable Preferences → Automatically label
   pages and groups from assigned references. Try group drag/reorder. Toggle
   this setting off: original titles should return unchanged.
3. Windows/Linux: press F11 twice from a maximized window.
4. Open Help → Keyboard Shortcuts (F1); search for a command.
5. Check secondary citation text in page list and Groups view in dark themes.
6. Save, close and reopen a **copy** of the notebook.

For audit: `python -m pytest -q` and `python -m compileall -q main.py yomunote tests`.
The notebook schema and v0.95 SafeSave hardening are unchanged.
