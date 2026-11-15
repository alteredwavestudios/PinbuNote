# Upload Yomu Note v0.8.5 using the same safe branch/CI/release process

**Source:** the `Yomu-Note-v0.8.5-Full-Source.zip` prepared from the tested
0.8.4c candidate. Alternative: the `Yomu-Note-v0.8.5-Overlay-for-v0.8.3b-GitHub.zip`
contains only changed and added files relative to the published 0.8.3b source.

1. Extract the **full source** ZIP into a fresh source folder such as
   `H:\dev\Yomu-Note-v0.8.5`.
2. Start PowerShell and follow the commands below. Choose an unused Git clone
   destination so no existing folder is overwritten.

```powershell
$source = 'H:\dev\Yomu-Note-v0.8.5'
$repo = 'H:\dev\Yomu-Note-v085-Git'
if (Test-Path $repo) { throw 'Choose another unused Git checkout directory' }
if (-not (Test-Path "$source\yomunote\__init__.py")) { throw 'Full source folder not found' }

git clone https://github.com/alteredwavestudios/Yomu-Note.git $repo
if ($LASTEXITCODE -ne 0) { throw 'Git clone failed' }
Set-Location $repo
git switch -c release/v0.8.5
if ($LASTEXITCODE -ne 0) { throw 'Creating release branch failed' }

Get-ChildItem -LiteralPath $source -Force |
    Where-Object { $_.Name -ne '.git' } |
    Copy-Item -Destination $repo -Recurse -Force

git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff validation failed' }
git status --short
git add -A
git diff --cached --stat
git commit -m 'Prepare Yomu Note v0.8.5 reliability and performance release'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed' }
git push -u origin release/v0.8.5
if ($LASTEXITCODE -ne 0) { throw 'Push failed' }
```

3. Open <https://github.com/alteredwavestudios/Yomu-Note/pulls>, create a
   PR from `release/v0.8.5` into `main`, and check all CI jobs.
4. After merging and verifying *main* is current, tag the merged commit:

```powershell
Set-Location 'H:\dev\Yomu-Note-v085-Git'
git switch main
git pull --ff-only origin main
git log -1 --oneline
git tag -a v0.8.5 -m 'Yomu Note v0.8.5 reliability and performance'
git push origin v0.8.5
```

5. GitHub Actions builds Windows Setup and both Mac DMGs, verifies OCR and
   frozen Windows SQLite startup, and creates a **draft**, not a published
   release. Test the installer, then publish explicitly as a pre-release.

Never tag the feature branch, use `git push --force`, or replace the v0.8.3b
installation before the 0.8.5 installer has passed native checks.
