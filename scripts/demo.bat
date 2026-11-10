@echo off
rem One click demo for the committee: starts the API and the dashboard, opens the browser, then plays a developer
rem through the whole loop (pull request, QA, security, approvals) while the dashboard shows it.
rem
rem     scripts\demo.bat             the agent uses the language model (needs LLM_API_KEY in .env and free tokens)
rem     scripts\demo.bat template    explanations come from the fixed template: no model, no tokens, cannot hit a limit
rem
rem The API token is made fresh for each run and is never written to a file. The dashboard password is printed in the
rem dashboard window. Demo data lives in %TEMP%\yaqidh-demo and is wiped at every start.
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo The Python environment is missing. Run once:  python -m venv .venv  then  .venv\Scripts\activate  then
  echo pip install -e ".[dev]" flask semgrep
  pause
  exit /b 1
)
set "PATH=C:\Tools;%CD%\.venv\Scripts;%PATH%"
set "PYTHONUTF8=1"
for /f %%i in ('.venv\Scripts\python.exe -c "import secrets;print(secrets.token_urlsafe(24))"') do set "API_TOKEN=%%i"
set "YAQIDH_API_TOKEN=%API_TOKEN%"
if exist "%TEMP%\yaqidh-demo" rmdir /s /q "%TEMP%\yaqidh-demo"
set "DATA_DIR=%TEMP%\yaqidh-demo\releases"
set "HISTORY_DIR=%TEMP%\yaqidh-demo\history"
set "GITHUB_TOKEN="
if /i "%~1"=="template" set "AGENT_MODE=template"

echo Putting the demo app back to its starting state...
.venv\Scripts\python.exe scripts\demo_fix.py reset

echo Starting the API...
start "YAQIDH API" cmd /k ".venv\Scripts\python.exe -m uvicorn src.api.main:app --port 8000"
:wait
curl -s http://127.0.0.1:8000/health 2>nul | find "ok" >nul
if errorlevel 1 (
  timeout /t 2 /nobreak >nul
  goto wait
)

echo Starting the dashboard...
start "YAQIDH Dashboard" cmd /k "cd frontend-preview && ..\.venv\Scripts\python.exe server.py --live --api-url http://127.0.0.1:8000"
timeout /t 4 /nobreak >nul
start "" http://127.0.0.1:8765/dashboard

echo.
echo The dashboard is open in your browser. Log in with developer, qa or security.
echo The password is printed in the "YAQIDH Dashboard" window.
echo.
pause

cd backend
..\.venv\Scripts\python.exe scripts\walkthrough.py --url http://127.0.0.1:8000 --exception-in-dashboard ^
  --on-fix-qa "python ..\scripts\demo_fix.py qa" ^
  --on-fix-security "python ..\scripts\demo_fix.py security"
cd ..
echo.
echo Putting the demo app back as it was...
.venv\Scripts\python.exe scripts\demo_fix.py reset
echo Done. Close the two server windows when you finish.
pause
