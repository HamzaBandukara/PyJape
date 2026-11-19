# PyJape - build the native engine from source and run it with Python (Windows).
#
# For anyone who wants to run PyJape from source. Installs Python + the OCaml
# toolchain (once) via winget, compiles the native engine, and launches the app.
#
# Run it from PowerShell, in the repo folder:
#     powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1
#
# Safe to re-run. Pass -Rebuild to force recompiling the engine.
param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'

function Say($m)  { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[!] $m"  -ForegroundColor Yellow }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path','User')
}

# Work from the repo root (this script lives in scripts\, one level down).
Set-Location (Join-Path $PSScriptRoot '..')
Say "Working in: $((Get-Location).Path)"

# 0. winget (ships with modern Windows 10/11 as 'App Installer').
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw "winget not found. Install 'App Installer' from the Microsoft Store (or update Windows), then re-run."
}

# 1. Python 3 (the python.org/winget build includes tkinter).
# Run it rather than just looking for it: on a fresh Windows, 'python' is often
# a Microsoft Store stub that only prints a message and fails.
function Test-Python {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) { return $false }
  python -c "import sys" 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}
if (-not (Test-Python)) {
  Say "Installing Python 3..."
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  Refresh-Path
}

# 2. opam (OCaml package manager; opam 2.2+ sets up its own C toolchain on Windows).
if (-not (Get-Command opam -ErrorAction SilentlyContinue)) {
  Say "Installing opam (OCaml)..."
  winget install -e --id OCaml.opam --accept-source-agreements --accept-package-agreements
  Refresh-Path
}
if (-not (Get-Command opam -ErrorAction SilentlyContinue)) {
  throw "opam still not on PATH. Close and reopen PowerShell, then run this script again."
}

# 3. opam init + an OCaml 4.14.2 switch (engine uses Stream, gone in 5.x) + dune.
if (-not (Test-Path "$env:USERPROFILE\.opam")) {
  Say "Initialising opam (first run - can take a while)..."
  opam init -y --disable-sandboxing
}
$switches = (opam switch list --short) 2>$null
if ($switches -notcontains '4.14.2') {
  Say "Creating OCaml 4.14.2 - this compiles the compiler and can take several minutes..."
  opam switch create 4.14.2
}
opam switch set 4.14.2
Say "Installing dune..."
opam install -y dune

if (-not (Test-Python)) {
  throw "Python still isn't runnable. Close and reopen PowerShell (or turn off the 'python' App execution alias in Settings), then run this script again."
}

# 4. Verify tkinter is present. (A failing native command doesn't throw in
# PowerShell, so check the exit code.)
python -c "import tkinter" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Your Python has no tkinter. Reinstall Python from https://www.python.org/downloads/ (tick 'tcl/tk and IDLE') and re-run."
}

# 5. Build the native engine (unless already built) and launch.
if ($Rebuild -or -not (Test-Path 'resources\jape-engine.exe')) {
  Say "Building the native Jape engine..."
  python build\make_dist.py --engine-only
} else {
  Say "Native engine already built (pass -Rebuild to recompile)."
}
Say "Launching PyJape..."
python run.py
