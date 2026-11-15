# Pinbu Note v0.8.7c

Start with the source build from the ZIP. From PowerShell inside the folder:

```powershell
.\run-windows.bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-installer-windows.ps1
```

See `RELEASE_NOTES_v0.8.7c.md` for features and required native smoke checks. Keep v0.8.7b and original notebook backups until verified.
