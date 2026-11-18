# Pinbu Note v0.9.0b3 — Save Copy As overwrite and future-version protection (experimental)

**Full source testing build — please use a disposable notebook copy, not your only coursework file.**

## Save Copy As — confirmed overwrite, with backup first

- Selecting an existing notebook offers **Save as New Copy**, **Overwrite After Backup**, or **Cancel**. The safest **Save as New Copy** is the default.
- **Existing destination history is preserved in its own project backup directory** (`Backups/<dest-name>--<source-key>--<dest-ID>/{assets,data}`). An immutable `pre-overwrite` snapshot is written and every referenced asset/metadata object is hash-verified before a replacement is attempted.
- Only after backup verification, the new copy is prepared independently, SQLite integrity-checked and flushed, then installed with an OS-level `os.replace`.
- Failure to inspect/backup/verify/flush/replace leaves the existing notebook untouched. The separate recovery backup stays available if replacement fails after backup completion.
- Overwriting the **currently open notebook** is blocked via Save Copy As (use normal Save). A local origin lease also blocks overwriting another notebook already open in a cooperating Pinbu instance on that machine.

## Newer-version safeguards

- If the destination was saved by a **newer Pinbu app version but has a supported notebook format**, the overwrite dialog strongly recommends **Save as New Copy**. Overwrite After Backup remains an explicit, risk-labelled option; its backup may require the newer app to restore.
- If the destination uses an **unsupported future notebook format**, overwriting is blocked entirely, even if the user tried to approve it. Updating Pinbu Note is required to edit that format.
- Opening a notebook from a newer app displays an **upgrade warning** and prevents unsafe editing in this build. Older v5/v6 compatibility remains intact.
- Autosave continues **only to the private local working database**. If Dropbox synchronises a newer app's notebook into the original destination while the current session is open, the first local autosave or five-minute backup detects the newer external version and warns once. Explicit Save refuses to publish over the newer original.

## Limitations and caution

- **Cloud folders do not offer atomic distributed compare-and-swap via `os.replace`.** Changes from another unsynchronised device can still race with an explicit publish or Save Copy As overwrite. These are not yet safe for simultaneous cross-device writes.
- A newer app release might have functionality that this older one cannot preserve. **Save as New Copy** and upgrading Pinbu remain strongly recommended. For **incompatible format versions**, overwrite is prohibited.
- Real Windows/macOS GUI, Dropbox/OneDrive/iCloud synchronisation, forced-error and large-notebook testing remain necessary before stable release.
- Notebook format stays **v6** and `.pinbubackup` format stays **v1**. v0.9.0b2 close and crash recovery is retained.

## Expected release packages after building from source

- Windows: `PinbuNote_Setup_v0.9.0b3.exe`
- macOS arm64: `PinbuNote-0.9.0b3-macOS-arm64-unsigned.dmg`
- macOS x86_64: `PinbuNote-0.9.0b3-macOS-x86_64-unsigned.dmg`

## Manual testing

1. Create **two disposable notebooks** with different notes. Save Copy As over one. Confirm warning, choose Save as New Copy first.
2. Repeat and choose Overwrite After Backup. Confirm it replaced the selected notebook; then **Restore From Backup** using the destination notebook's own `history.pinbubackup`, and verify the old notes are intact.
3. Save a test notebook with a future app version and compatible format; confirm the stronger warning and Save as New Copy recommendation. Never try this on real work.
4. From another test process change the destination during backup; confirm overwrite fails and the external version survives.
5. Keep a copy open while synchronising a newer-app-format test notebook to its original path; confirm local autosaving warns once but does not overwrite the original.
