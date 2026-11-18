# Pinbu Note v0.9.0b3 — experimental source build

**Start with disposable notebook copies.**

Run `run-windows.bat` on Windows or `./run-mac.command` on macOS.

The major new feature is **File → Save Copy As…**, which can overwrite an existing notebook ONLY after a version check, a verified **pre-overwrite backup in the destination notebook's backup folder**, and explicit confirmation. Newer app versions trigger stronger advice to save as a new file; incompatible future file formats cannot be overwritten. Local autosave never writes to cloud originals and warns if the external original was upgraded on another device.

See `RELEASE_NOTES_v0.9.0b3.md` and `docs/SAFE_SAVE.md`.
