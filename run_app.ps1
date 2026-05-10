$ErrorActionPreference = "Stop"

$localPython = Join-Path $PSScriptRoot ".python312\python.exe"
if (Test-Path $localPython) {
    & $localPython ".\nicegui_csv_viewer.py"
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & $python.Source ".\nicegui_csv_viewer.py"
    exit $LASTEXITCODE
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & $py.Source -3 ".\nicegui_csv_viewer.py"
    exit $LASTEXITCODE
}

Write-Error "Python bulunamadi. Lutfen once Python kurup PATH degiskenine ekleyin."
