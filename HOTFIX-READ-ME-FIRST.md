# v0.9.0b1 — Fixing `[Errno 9] Bad file descriptor` on Windows

The original v0.9.0b uses `open('rb')` followed by `os.fsync()` on a temporary publish file. Windows uses `_commit()` for `fsync`, which requires a writable descriptor. The result was that Save could fail while attempting to publish the completed local SQLite copy to the original notebook.

The corrected version uses `open('r+b')` on the temporary copy before syncing, **without changing any file contents**. Existing destination-conflict and SQLite-integrity checks remain in place. The saved notebook format remains v6. The fixed source identifies itself as v0.9.0b1.

**Important:** A failed publish may still leave valid edits in a private *local working copy*. Do **not** delete the previous version's local working copies or backup directory while diagnosing save failures. In Pinbu's File menu, use the available local-working-copy recovery command to restore unpublished changes as a **separate** notebook before testing publication again. Keep a separate copy of the original Dropbox notebook.

## Test on Windows

1. Extract this source ZIP to a NEW folder, not on top of an installation or previous source.
2. Keep the previous version installed and make a *disposable copy* of a notebook for testing.
3. Open a terminal in the source folder. Run `run-windows.bat`.
4. Edit some notes and press Save. Verify the original destination changes only after explicit Save and reopens with the edited text.
5. Test a deliberately changed destination: Pinbu must refuse to overwrite it and must retain local edits.

For an installed application, rebuild the app and installer with `build-windows.ps1` and `build-installer-windows.ps1` (see the included build guides). Changing the source file does **not** fix an already-built `.exe`.

## Test coverage

- Regression test emulates Windows's EBADF for an `os.fsync` call on a read-only file descriptor.
- A simulated I/O failure before publishing verifies that the cloud-facing original remains untouched and local edits remain recoverable.
- Full non-GUI regression suite: 563 passed, 50 skipped, 3 subtests passed on Linux. Native Windows validation remains required.

This is an experimental hotfix. Atomic cross-device cloud publication is **not** guaranteed by filesystem-level signatures; simultaneous device edits must still be handled cautiously.
