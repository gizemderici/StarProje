@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "PYTHON_EXE=%REPO_ROOT%\.python312\python.exe"
set "TEMP=%REPO_ROOT%\.tmp_pytest_runtime"
set "TMP=%TEMP%"
set "BASE_TEMP=%REPO_ROOT%\.pytest_tmp"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%REPO_ROOT%"

if not exist "%PYTHON_EXE%" (
  echo Yerel Python bulunamadi: %PYTHON_EXE%
  exit /b 1
)

if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%BASE_TEMP%" mkdir "%BASE_TEMP%"
if "%~1"=="" (
  "%PYTHON_EXE%" -c "import sys; from _pytest.config import main; raise SystemExit(main(sys.argv[1:]))" tests/test_comparison_reports_view_model.py tests/test_ui_section_helpers.py --basetemp "%BASE_TEMP%" -p no:cacheprovider
) else (
  "%PYTHON_EXE%" -c "import sys; from _pytest.config import main; raise SystemExit(main(sys.argv[1:]))" %* --basetemp "%BASE_TEMP%" -p no:cacheprovider
)
exit /b %ERRORLEVEL%
