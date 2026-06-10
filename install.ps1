# install.ps1 -- SSM Tunnel GUI Windows installer
# Run: powershell -ExecutionPolicy Bypass -File install.ps1
# Flags:
#   -BuildExe   : build a standalone .exe with PyInstaller
#   -NoShortcut : skip desktop shortcut
param(
    [switch]$BuildExe,
    [switch]$NoShortcut
)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppFile   = Join-Path $ScriptDir "ssm_tunnel_gui.py"
$ExeDir    = Join-Path $ScriptDir "dist"
$ExePath   = Join-Path $ExeDir "SSM Tunnel.exe"

function Step($n, $msg) { Write-Host "[$n] $msg" -ForegroundColor Cyan }
function OK($msg)        { Write-Host "  OK   $msg" -ForegroundColor Green }
function Warn($msg)      { Write-Host "  WARN $msg" -ForegroundColor Yellow }
function Fail($msg)      { Write-Host "  ERR  $msg" -ForegroundColor Red; exit 1 }

Write-Host "=== SSM Tunnel GUI - Windows Setup ===" -ForegroundColor White

# -- 1. Python ----------------------------------------------------------------
Step "1/5" "Python"
$python = $null
foreach ($cmd in @("python", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.") { $python = $cmd; break }
    } catch {}
}
if (-not $python) {
    Warn "Python 3 not found. Installing via winget..."
    winget install --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    $python = "python"
}
OK (& $python --version)

# -- 2. pip packages ----------------------------------------------------------
$pkgs = @("PyQt5")
if ($BuildExe) { $pkgs += "pyinstaller" }
Step "2/5" "pip install $($pkgs -join ', ')"
& $python -m pip install --upgrade --quiet @pkgs
OK "packages installed"

# -- 3. AWS CLI ---------------------------------------------------------------
Step "3/5" "AWS CLI"
if (Get-Command aws -ErrorAction SilentlyContinue) {
    OK (aws --version 2>&1)
} else {
    Warn "AWS CLI not found. Installing via winget..."
    winget install --id Amazon.AWSCLI --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    if (Get-Command aws -ErrorAction SilentlyContinue) { OK "AWS CLI installed" }
    else { Warn "Restart terminal after install to use aws" }
}

# -- 4. Session Manager Plugin ------------------------------------------------
Step "4/5" "Session Manager Plugin"
$smpPath = "$env:ProgramFiles\Amazon\SessionManagerPlugin\bin\session-manager-plugin.exe"
if (Test-Path $smpPath) {
    OK "Session Manager Plugin found"
} else {
    Warn "Not found. Downloading..."
    $tmp = Join-Path $env:TEMP "SessionManagerPluginSetup.exe"
    $url = "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe"
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
        Start-Process -FilePath $tmp -ArgumentList "/S" -Wait
        OK "Session Manager Plugin installed"
    } catch {
        Warn "Auto-install failed. Download manually:"
        Warn "  $url"
    }
    Remove-Item $tmp -ErrorAction SilentlyContinue
}

# -- 5. Build or launcher -----------------------------------------------------
if ($BuildExe) {
    Step "5/5" "Building single EXE (PyInstaller)"
    Push-Location $ScriptDir
    & $python -m PyInstaller `
        --onefile `
        --windowed `
        --name "SSM Tunnel" `
        $AppFile
    Pop-Location
    if (Test-Path $ExePath) { OK "Build complete: $ExePath" }
    else { Fail "Build failed. Check output above." }
    $launchTarget = $ExePath
} else {
    Step "5/5" "Creating run.bat"
    $launcher = Join-Path $ScriptDir "run.bat"
    Set-Content -Encoding ASCII $launcher "@echo off`r`n`"$python`" `"$AppFile`" %*"
    OK "Launcher: $launcher"
    $launchTarget = $launcher
}

# -- Desktop shortcut ---------------------------------------------------------
if (-not $NoShortcut) {
    $desktop  = [Environment]::GetFolderPath("Desktop")
    $lnkPath  = Join-Path $desktop "SSM Tunnel.lnk"
    $shell    = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($lnkPath)
    $shortcut.TargetPath       = $launchTarget
    $shortcut.WorkingDirectory = $ScriptDir
    $shortcut.Description      = "AWS SSM Port Forwarding GUI"
    $shortcut.Save()
    OK "Desktop shortcut: $lnkPath"
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
if ($BuildExe) {
    Write-Host "  EXE: $ExePath"
} else {
    Write-Host "  Run: python `"$AppFile`""
    Write-Host "  Or:  double-click 'SSM Tunnel' on desktop"
}
