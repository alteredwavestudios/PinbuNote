# Pinbu Note v0.9.0b4 — Quick Start

1. Extract the full source ZIP to a fresh folder. Do not replace your older installation or delete any backup folders.
2. On Windows run `run-windows.bat`. On macOS run `./run-mac.command`. The source launcher needs Python and installation of app dependencies.
3. Open **Settings → Preferences** and locate **Migrate Legacy Backups…** under SafeSave backup settings.
4. Choose **Scan Folder**. Browse to an older Yomu/Pinbu backup directory if needed.
5. Inspect the preview, click **Migrate Found Backups…** and confirm. This can take time for notebooks with large PDFs. Leave Pinbu running until completion.
6. Use **File → Restore From Backup…** and choose the project folder's `history.pinbubackup`. Test restoring a version into a fresh notebook and check its PDF pages and annotations before cleaning anything up.

## Backup folder layout

```
Backups/
  Sociology/
    PLEASE READ - About Your Backups.txt
    history.pinbubackup
    assets/
    data/
      objects/
      snapshots/
  Sociology (2)/
    ...
  _Legacy Originals (kept)/
    Sociology--...--.../
      history.pinbubackup
      assets/
      data/
```

Original complete `.pinbunote`/`.yomunote`/`.yominote` backup files are not deleted or moved by migration. Early indexed project directories are moved to `_Legacy Originals (kept)` only after a checked new copy is made.

## Important

This is an experimental source build. Back up irreplaceable coursework independently, and do not assume local filesystem checks solve all Dropbox cross-device races. If migration reports an error, keep the original files and use a separate working copy while investigating.
