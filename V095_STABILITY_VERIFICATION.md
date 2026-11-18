# Pinbu Note v0.95 — Stability release verification

**Source baseline:** original v0.9.2b Navigator Click Hotfix archive, SHA256
`1d37d73a612bd406bd5010344708eec412ace456a83ff5a119f10565a287f313`.

**New version label:** exactly `0.95` (not `0.9.5`).
**Notebook container version:** 7 (unchanged). **PinbuBoard:** not included.

## Fixes

1. A shared `read_bounded_manifest()` loader checks the manifest's UTF-8 **byte**
   length inside SQLite before fetching user-controlled text into Python.
   This is used for ordinary opening, working-copy sessions, legacy-backup
   migration, SafeSave backup creation, overwrite checks, tab exchange,
   restoration and cleaned-share copies.
2. Cleaned-share copies validate input *before* running `VACUUM INTO`,
   preventing malformed input from reaching the full-database copying stage.
3. The application version parser supports `0.95` and legacy three-part labels.
   Future versions remain protected against accidental older-app overwrites.
4. Closing after a save failure keeps the window open, logs diagnostics and
   provides retry/Save Copy As guidance. **Audit correction:** v0.9.2b's
   actual closeEvent already ignored the close event and did NOT re-raise.
   v0.95 improves the message/logging; it does not invent a new save policy.
5. Windows Inno Setup keeps the existing upgrade GUID, with `v0.95` version
   metadata. macOS DMG names and release-asset checks use the source version;
   the GitHub tag is verified against that version before a draft is created.

## Headless verification

- **641 passed, 51 skipped, 3 subtests passed**, Linux Python 3.13, `pytest -q`.
- `compileall` passed for application code and tests.
- YAML workflow parses successfully. (Native GitHub Actions itself not run.)
- No NodeGraphQt/PinbuBoard code introduced.

## Repeated storage benchmark — disposable synthetic notebooks

| Pages | v0.9.2b open | v0.95 open | v0.9.2b no-change save | v0.95 no-change save |
|---:|---:|---:|---:|---:|
| 100 | 0.0212s | 0.0129s | 0.0062s | 0.0056s |
| 1,000 | 0.2014s | 0.1625s | 0.0587s | 0.0521s |
| 5,000 | 0.6444s | 0.7037s | 0.2879s | 0.2874s |

These are short single-run measurements subject to OS/cache noise, **not**
GUI frame-rate measurements. The changed manifest loader is not a significant
storage bottleneck in these runs. The 400-page lazy PDF import in the second
run indexed in 0.0102 seconds with zero materialised previews.

## Remaining release blockers

- Real PySide6 GUI/Qt lifetime, OCR/voice, large PDF scroll/zoom, installer
  startup and tab shutdown still need native Windows and macOS testing.
- Mac arm64 and x86_64 package jobs must actually run. The v0.9.1 Mac CI
  job in GitHub run 43967920528 never acquired a runner in either attempt;
  this is **not** evidence of a Python test failure and is not fixed by source
  code. Earlier v0.8.7c macOS builds did complete successfully.
- DMGs remain unsigned/ad-hoc signed and **not notarized**. Do not publish
  them as signed official macOS applications.
- No CI jobs, GitHub tags, draft releases or repository changes were pushed
  by this local release preparation. This is a source release candidate.

## Source inspection note

This is an incremental hardening patch, not a feature redesign. The audit
found no reason to refactor the 11,000+ line main window immediately before
native sign-off; such a refactor would increase regression risk.
