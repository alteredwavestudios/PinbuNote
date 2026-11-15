# Yomu Note v0.8.5 — GitHub-ready source

This is a complete source release candidate assembled from the **user-tested
v0.8.4c** code. It is not a precompiled Windows executable or installer.
The only application-level changes from 0.8.4c are release labels, build
metadata, documentation and version tests.

## Before uploading

1. Keep your **installed v0.8.3b** application and original notebooks intact.
2. Open v0.8.5 from an extracted source directory using `RUN_DEV_SAFELY.cmd`.
3. Check that existing notebook copies still load and all features work.
4. Push this source to **a new feature/release branch**, *not* a tag or main.
5. Run GitHub CI on the pull request (Windows, macOS, Linux).
6. Merge only after all checks pass. Create the `v0.8.5` tag **from the merged
   main branch** to start the native Windows/macOS draft release build.
7. Verify the resulting installer, then publish the draft as a **pre-release**.

Detailed commands: see `GITHUB-PUSH-START-HERE.md`.

## Compatibility

- Notebook schema v5 and project schema v4 unchanged.
- Windows installer AppId retained; no system preference migration.
- Original documents, reading progress, annotations, text selection and notes
  preserved by the existing Yomu Note notebook implementation.
- No clipboard-image or voice-recognition features are included yet.
