# Pinbu Note v0.96 — verification notes

Source baseline: Pinbu Note v0.95 (based on pre-PinbuBoard v0.9.2b).
No PinbuBoard components or notebook schema changes were introduced.

## This environment

- Python source compilation: PASS (`python -m compileall -q main.py yomunote tests`).
- Regression tests: **646 passed, 55 skipped, 3 subtests passed**.
- Added focused tests for reference labels (off by default, inherited references,
  explicit exclusions, preservation of original metadata) and native Qt tests
  for group reordering, title editor, Help dialog, and fullscreen.
- The 55 skipped tests need native GUI/Qt environments; this container does not
  include PySide6. Do not interpret skipped GUI tests as platform success.
- Windows/macOS standalone apps were NOT built or launched in this environment.

## Critical Windows/Linux manual checks

1. F11 from a normal window and from a maximized window; verify restore.
2. Help → Keyboard Shortcuts (F1), search for 'Save' and a formatting command.
3. Select dark theme; inspect citation/author details in both navigator views.
4. Enable automatic reference labels; create one referenced group and page.
5. Drag/reorder a referenced group, Save, reopen. Turn reference labels OFF;
   confirm original page and group titles are unchanged.
6. Check the two Minimal themes and switch between them and existing themes.
7. Run a notebook recovery test on a COPY and confirm v0.95 notebooks open.

GitHub Actions native release workflow remains to be run on an actual release
branch/tag. The repository was not modified or published by this source build.
