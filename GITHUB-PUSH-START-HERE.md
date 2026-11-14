# GitHub push instructions (v0.8.3b)

This is the **complete GitHub-ready source**, not a Git checkout; it intentionally contains no `.git` folder. First extract it, then copy its contents into a **new clone** of the repository to make a feature-branch pull request.

## Safe Windows PowerShell recipe

The source ZIP should be fully extracted to `H:\dev\Yomu-Note-v0.8.3b`. It is safe to choose a different folder by changing the `$source` variable below.

```powershell
$source = 'H:\dev\Yomu-Note-v0.8.3b'
$repo = 'H:\dev\Yomu-Note-v083b-Git'
git clone https://github.com/alteredwavestudios/Yomu-Note.git $repo
if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
Set-Location $repo
git switch -c feature/v0.8.3b-text-lab
if ($LASTEXITCODE -ne 0) { throw 'Could not create feature branch' }
Get-ChildItem -LiteralPath $source -Force | Where-Object Name -NE '.git' | Copy-Item -Destination $repo -Recurse -Force
# Confirm changes BEFORE committing
git status --short
git add -A
git diff --cached --stat
git commit -m "Integrate Text Lab and page selection updates for v0.8.3b"
git push -u origin feature/v0.8.3b-text-lab
```

**Do not push a tag yet.** Open GitHub and create a pull request from `feature/v0.8.3b-text-lab` into `main`; it will trigger the cross-platform source test workflow. Once it passes and you have tested Windows locally, merge the PR. To trigger the Windows and macOS draft release, tag the tested merged commit and push the tag:

```powershell
git switch main
git pull --ff-only origin main
git tag v0.8.3b
git push origin v0.8.3b
```

Pushing the tag runs `.github/workflows/release.yml`, which packages Windows and both macOS architectures and creates a **draft**, not a published release. Review the artifacts, native installer tests, and release notes before publishing.

### Remember the past installer regressions

Do not remove `scripts/verify_windows_frozen.py`, the `--fix-sqlite` step, offline OCR verification, the installed-app smoke test, `Start-Process -Wait -PassThru`, or the deliberate absence of a post-install `[Run]` launch in Inno Setup. Keep the stable Inno `AppId`. See `RELEASE_NOTES_v0.8.3b.md`.
