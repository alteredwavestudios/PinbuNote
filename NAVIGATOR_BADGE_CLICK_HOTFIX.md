# Pinbu Note v0.9.2b — Navigator click safety hotfix

This hotfix addresses the one failing Windows GUI audit module from v0.9.2b.

- The Individual-list Qt test now configures a page row at the same height as the production navigator, so the test's badge hit target is inside a real row.
- In both Groups and Individual views, page-number clicks are intercepted on mouse-down **and** mouse-up. Clicking a number cannot change the selected page first.
- The Individual navigator insert-page (+) affordance no longer animates over a number badge when hovering.
- Added assertions verifying the number badge resolves to the right item and does not select it.
- **No SQLite, research metadata or `.pinbunote` format change.** Notebook v7, project v5, backup v1 remain unchanged.

On Windows: `python YomuNote-Full-Test-Audit.py --per-file-timeout 90`.
The audit's test module `tests/test_v092b_navigator_qt.py` should pass both tests.
Native PySide6 Qt interaction tests could not be run in the packaging environment; the Windows audit is the verification gate.
