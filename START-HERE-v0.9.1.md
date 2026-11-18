# Pinbu Note v0.9.1 — Test First

This ZIP is full Python source, **not** a prebuilt installer.

1. Extract into a NEW directory, not over the last working version.
2. Duplicate a test `.pinbunote` file. Do not use the only copy of important coursework.
3. Windows: `run-windows.bat`. macOS: `./run-mac.command`. Linux: `python main.py` after installing requirements.
4. Open test notebook, edit, and confirm `Autosave · HH:MM` appears quietly in the footer.
5. Open Preferences; select a secondary backup root on a different drive, enable it, and click OK.
6. Wait for five-minute backup, or close normally to trigger close backups in both stores.
7. Preferences → SafeSave Health & Verify Backups → Verify Latest Backup; confirm BOTH stores are reported independently.
8. Disconnect secondary disk in a disposable test and confirm failure is explicit without deleting primary history.
9. File → Restore From Backup; verify previous pages, notes, PDFs and annotations in a new copy.
10. Confirm the first Save publishes to the original location and a second Save without changes doesn't rewrite it.

To build a Windows installer, use `build-windows.ps1` followed by
`build-installer-windows.ps1` on Windows. On macOS use `build-mac.command` and
`scripts/package-macos-dmg.sh` on macOS. Draft release workflow accepts tag
`v0.9.1` **after the source is pushed and tagged**, builds platform assets and
leaves a draft release for manual publication.

**Known limitation:** two machines can still publish to Dropbox during a sync
race. The second backup folder is an independent recovery store, not distributed
locking. See `RELEASE_NOTES_v0.9.1.md` for details.
