$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot ".python312\python.exe"
$tempRoot = Join-Path $repoRoot ".tmp_pytest_runtime"
$baseTemp = Join-Path $repoRoot ".pytest_tmp"
$pythonPath = $repoRoot

if (!(Test-Path $pythonExe)) {
    throw "Yerel Python bulunamadi: $pythonExe"
}

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $baseTemp | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = $pythonPath
$pytestArgs = @()
if ($args.Count -gt 0) {
    $pytestArgs += $args
} else {
    $pytestArgs += @("tests/test_comparison_reports_view_model.py", "tests/test_ui_section_helpers.py")
}
$pytestArgs += @("--basetemp", $baseTemp, "-p", "no:cacheprovider")
& $pythonExe -c "import sys; from _pytest.config import main; raise SystemExit(main(sys.argv[1:]))" @pytestArgs
exit $LASTEXITCODE
