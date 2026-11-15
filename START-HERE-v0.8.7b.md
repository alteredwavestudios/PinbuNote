# Pinbu Note v0.8.7b — Test this build

This ZIP contains **full source**, not a Windows installer. Extract it to a new
folder outside the v0.8.6b folder so the previous tested build stays safe.

**Windows:** In the extracted source folder, run `run-windows.bat` first.
For an installed app run `build-windows.ps1`, then
`build-installer-windows.ps1` in PowerShell. See `docs/BUILD_RELEASES.md`
for the original prerequisites (Python, Tesseract, Inno Setup).

**macOS:** run `run-mac.command` then `build-mac.command`. The scripts bundle
OCR assets from a build-machine Tesseract installation; for a DMG use
`bash scripts/package-macos-dmg.sh arm64` (or `x86_64`).

The new installer filename after successful native packaging is
`PinbuNote_Setup_v0.8.7b.exe`. The Python package still uses `yomunote`
for now as an internal compatibility measure, not as user-facing branding.

Start with a **copy** of an old notebook and follow the native acceptance
checklist in `RELEASE_NOTES_v0.8.7b.md`. Do not simultaneously open the same
file in old Yomu Note and Pinbu Note.

**New in this follow-up:** Bookmarked pages have a ribbon overlay; the sticky
Quick Edit menu has an editable font size; bullet toggle now handles mixed
lists and empty lines. The About popup and Focus labels show Pinbu branding.
Read `PINBU_REBRAND_AUDIT_v0.8.7b.md` for the audit and performance testing
checklist. The old .yomunote file extension is still supported.
