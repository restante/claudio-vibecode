<#
.SYNOPSIS
  claudio-vibecode installer for Windows (beta). Installs claudio-tts first if needed.

.EXAMPLE
  irm https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.ps1 | iex

.PARAMETER Lite      Pass -Lite to the claudio-tts installer (smaller 92 MB voice model).
.PARAMETER NoModel   Pass -NoModel to the claudio-tts installer.
.PARAMETER Uninstall Remove the mod and its data (claudio-tts is left alone).
.PARAMETER Local     Install from the checkout this script sits in.
.PARAMETER Ref       Git ref to install (default main).

  With `irm | iex` you cannot pass parameters; set CLAUDIO_VIBECODE_UNINSTALL=1 or
  CLAUDIO_VIBECODE_REF=<ref> in the environment instead.
#>
[CmdletBinding()]
param(
  [switch]$Lite,
  [switch]$NoModel,
  [switch]$Uninstall = ($env:CLAUDIO_VIBECODE_UNINSTALL -eq '1'),
  [switch]$Local,
  [string]$Ref = $(if ($env:CLAUDIO_VIBECODE_REF) { $env:CLAUDIO_VIBECODE_REF } else { 'main' })
)

$ErrorActionPreference = 'Stop'
$Repo = if ($env:CLAUDIO_VIBECODE_REPO) { $env:CLAUDIO_VIBECODE_REPO } else { 'restante/claudio-vibecode' }
$TtsRepo = if ($env:CLAUDIO_TTS_REPO) { $env:CLAUDIO_TTS_REPO } else { 'restante/claudio-tts' }

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "warning: $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "error: $m" -ForegroundColor Red; exit 1 }
function Run {
  param([Parameter(Mandatory)][string]$Exe, [Parameter(ValueFromRemainingArguments)]$Rest)
  & $Exe @Rest
  if ($LASTEXITCODE -ne 0) { Die "$Exe $($Rest -join ' ') failed (exit $LASTEXITCODE)" }
}

$HomeDir = if ($env:CLAUDIO_TTS_HOME) { $env:CLAUDIO_TTS_HOME }
           else { Join-Path $(if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME 'AppData\Local' }) 'claudio-tts' }
$Py = Join-Path $HomeDir 'venv\Scripts\python.exe'

if ($Uninstall) {
  Say 'Uninstalling claudio-vibecode (claudio-tts is left alone)'
  if (Test-Path $Py) {
    & $Py -m claudio_vibecode stop
    & $Py -m claudio_vibecode uninstall-mod
    if (Get-Command uv -ErrorAction SilentlyContinue) { & uv pip uninstall -q --python $Py claudio-vibecode }
  }
  Remove-Item -Recurse -Force (Join-Path $HomeDir 'vibecode') -ErrorAction SilentlyContinue
  Say 'Done. Restart open Claude Code sessions to drop the mod.'
  return
}

# 1. claudio-tts (speech engine, Python environment, uv) --------------------------------------------
$HaveTts = $false
if (Test-Path $Py) { & $Py -c 'import claudio_tts' 2>$null; $HaveTts = ($LASTEXITCODE -eq 0) }
if (-not $HaveTts) {
  Say 'Installing claudio-tts first (it provides the voice and the Python environment)'
  $Script = Invoke-RestMethod "https://raw.githubusercontent.com/$TtsRepo/main/install.ps1"
  $Args = @()
  if ($Lite) { $Args += '-Lite' }
  if ($NoModel) { $Args += '-NoModel' }
  & ([scriptblock]::Create($Script)) @Args
}
if (-not (Test-Path $Py)) { Die "claudio-tts did not set up $Py" }
$env:Path = "$HOME\.local\bin;$HOME\.cargo\bin;$env:Path"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Die 'uv was not found; open a new terminal and re-run.' }

# 2. claudio-vibecode ----------------------------------------------------------------------------------
if ($Local) {
  $Src = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
  if (-not (Test-Path (Join-Path $Src 'pyproject.toml'))) { Die '-Local needs to run from a claudio-vibecode checkout.' }
  Say "Installing claudio-vibecode from $Src"
  Run uv pip install -q --python $Py --no-deps $Src
  Run uv pip install -q --python $Py 'segno>=1.6' 'psutil>=5.9' 'numpy>=1.26'
} else {
  Say "Installing claudio-vibecode ($Repo@$Ref)"
  Run uv pip install -q --python $Py "claudio-vibecode @ git+https://github.com/$Repo@$Ref"
}

# 3. Claude Code mod -------------------------------------------------------------------------------------
Say 'Installing the Claude Code mod'
Run $Py -m claudio_vibecode install-mod --python $Py

Say 'Checking everything'
& $Py -m claudio_vibecode doctor
if ($LASTEXITCODE -ne 0) { Warn 'Some checks failed; see above.' }

Write-Host @"

claudio-vibecode is installed.

  1. Restart Claude Code (open sessions only pick the mod up when they start).
  2. In a session type:  /vibe      It starts the hub and shows a QR code.
  3. Scan it with your phone camera (same Wi-Fi). Allow python.exe on Private networks if Windows asks.

Windows support is in beta: please report problems at https://github.com/$Repo/issues
"@
