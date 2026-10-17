@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "app\launch.py" --open
  exit /b
)
if exist "app\runtime.json" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$taskRuntime = Get-Content -LiteralPath 'app/runtime.json' -Raw | ConvertFrom-Json; & $taskRuntime.pythonw 'app/launch.py' '--open'"
  exit /b
)
echo Install dependencies using the steps in README.md first.
pause
exit /b 1
