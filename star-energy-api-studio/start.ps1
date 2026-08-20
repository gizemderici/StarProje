$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir '.venv\Scripts\python.exe'
$Requirements = Join-Path $ProjectDir 'requirements.txt'

function Test-Python([string]$Candidate) {
    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        return $false
    }
    try {
        & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

if (-not (Test-Python $VenvPython)) {
    $Candidates = @(
        (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    )
    $CommandPython = Get-Command python -ErrorAction SilentlyContinue
    if ($CommandPython) {
        $Candidates += $CommandPython.Source
    }
    $BasePython = $Candidates | Where-Object { Test-Python $_ } | Select-Object -First 1
    if (-not $BasePython) {
        throw 'Python 3.11+ bulunamadı. Önce Python 3.12 kurun.'
    }
    & $BasePython -m venv (Join-Path $ProjectDir '.venv')
}

& $VenvPython -c "import nicegui, fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install --disable-pip-version-check -r $Requirements
}

$env:PYTHONUTF8 = '1'
$ApiPort = 8091
if ($env:ENERJI_API_PORT) {
    $ApiPort = [int]$env:ENERJI_API_PORT
}
$ApiUrl = "http://127.0.0.1:$ApiPort"
$env:ENERJI_API_URL = $ApiUrl
Set-Location -LiteralPath $ProjectDir
& $VenvPython (Join-Path $ProjectDir 'system_launcher.py')
