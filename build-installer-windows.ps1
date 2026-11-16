# Pinbu Note v0.9.1 - create an installer after building the app with PyInstaller.
# Put this script and PinbuNote_Installer.iss in the app source folder.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$exe = Join-Path $PSScriptRoot 'dist\Pinbu Note\Pinbu Note.exe'
$script = Join-Path $PSScriptRoot 'PinbuNote_Installer.iss'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Built app not found at: $exe`nFirst run: powershell -NoProfile -ExecutionPolicy Bypass -File .\build-windows.ps1"
}
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
    throw "Installer script not found: $script"
}

# Inno Setup can be installed per-user or system-wide; support v6 and v7.
$cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$candidates = @()
if ($cmd) { $candidates += $cmd.Source }
$candidates += @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
)
$iscc = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $iscc) {
    throw 'Inno Setup compiler not found. Install Inno Setup from https://jrsoftware.org/isdl.php or open the .iss file in the Inno Setup Compiler and choose Build > Compile.'
}
# Refuse a misleading installer that launches successfully but cannot OCR.
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Build virtual environment is missing' }
& $python ocr_packaging\verify_ocr_bundle.py --target windows --dist (Join-Path $PSScriptRoot 'dist\Pinbu Note')
if ($LASTEXITCODE -ne 0) { throw 'Standalone OCR verification failed; installer will not be produced' }
Write-Host "Using Inno Setup compiler: $iscc"
& $iscc $script
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed (exit code $LASTEXITCODE)." }
$output = Join-Path $PSScriptRoot 'installer\PinbuNote_Setup_v0.9.1.exe'
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { throw "Compilation reported success, but output not found: $output" }
# GitHub runs a silent installation and tests the copy users actually receive.
# Do not open a real notebook; the app exits after a SQLite/GUI import probe.
if ($env:CI -eq 'true') {
    # Inno Setup is a GUI executable: PowerShell can return before it finishes.
    # Wait for installation (including child processes) before testing files.
    $installDir = Join-Path $env:RUNNER_TEMP "PinbuNote-SmokeInstall-$PID"
    $installArgs = @(
        '/VERYSILENT'
        '/SUPPRESSMSGBOXES'
        '/NORESTART'
        '/SP-'
        "/DIR=`"$installDir`""
    )
    $installer = Start-Process -FilePath $output -ArgumentList $installArgs -Wait -PassThru
    if ($installer.ExitCode -ne 0) {
        throw "Silent installer smoke-install failed (exit code $($installer.ExitCode))"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $installDir '_internal\sqlite3.dll') -PathType Leaf)) {
        throw 'Installer completed but the installed copy is missing _internal\sqlite3.dll'
    }
    & $python scripts\verify_windows_frozen.py --dist $installDir
    if ($LASTEXITCODE -ne 0) { throw 'Installed application failed its frozen runtime smoke test' }
}
Write-Host "Installer created: $output"
Write-Host 'Run the installer to add Pinbu Note to Program Files, Start Menu, and Installed Apps.'
