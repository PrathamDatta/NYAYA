@echo off
setlocal EnableExtensions
title Nyaya Bharatha launcher
REM ===========================================================================
REM  One-click launcher for Windows 10/11. Double-click this file.
REM  First run: installs missing tools, downloads ~6 GB of models, loads sample
REM  judgments, then starts the app. Later runs: starts in seconds.
REM  Safe to close and re-run: every step is skipped once it has succeeded.
REM ===========================================================================

set "REPO_URL=https://github.com/PrathamDatta/NYAYA"
set "BRANCH=claude/kind-ritchie-pj5ylh"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

REM --- 1. Where is the project? (works even if this one file was copied alone) ---
set "ROOT=%~dp0"
if not exist "%ROOT%backend\app\main.py" (
  set "ROOT=%USERPROFILE%\NYAYA\"
)
echo.
echo  Nyaya Bharatha  -  project folder: %ROOT%
echo.

REM --- 2. Tools: Git (only needed to download the project), Python, Node ---
if not exist "%ROOT%backend\app\main.py" (
  where git >nul 2>nul || call :install Git.Git "Git"
  where git >nul 2>nul || goto :relaunch
if exist "%TEMP%\nyaya_relaunch2" goto :fail_tool
if exist "%TEMP%\nyaya_relaunch1" ( echo x>"%TEMP%\nyaya_relaunch2" ) else ( echo x>"%TEMP%\nyaya_relaunch1" )
echo.
echo  A tool was just installed. Re-opening this launcher in a fresh window so Windows can see it...
timeout /t 3 /nobreak >nul
REM Explorer starts the new window with the refreshed PATH (a child of this window would inherit the old one).
explorer.exe "%~f0"
exit /b 0

:fail_tool
del "%TEMP%\nyaya_relaunch1" "%TEMP%\nyaya_relaunch2" >nul 2>nul
echo.
echo  A required tool was installed but still cannot be found.
echo  Restart your PC once, then double-click this file again. If it still fails, install by hand:
echo    Python 3.12: https://www.python.org/downloads/windows/  ^(tick "Add py launcher"^)
echo    Node.js LTS: https://nodejs.org        Git: https://git-scm.com
pause
exit /b 1

:fail_clone
)

set "PY="
for %%V in (3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V --version >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  call :install Python.Python.3.12 "Python 3.12"
  goto :relaunch
)

where npm >nul 2>nul
if errorlevel 1 (
  call :install OpenJS.NodeJS.LTS "Node.js"
  goto :relaunch
)

del "%TEMP%\nyaya_relaunch1" "%TEMP%\nyaya_relaunch2" >nul 2>nul
cd /d "%ROOT%"
set "VPY=%ROOT%.venv\Scripts\python.exe"

REM --- 3. Python environment ---
if not exist "%VPY%" (
  echo  [1/6] Creating Python environment...
  %PY% -m venv .venv || goto :fail
)
if not exist ".venv\.deps_ok" (
  echo  [2/6] Installing Python packages - a few minutes, once...
  "%VPY%" -m pip install --upgrade pip >nul
  "%VPY%" -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu || goto :fail
  "%VPY%" -m pip install -r backend\requirements.txt || goto :fail
  echo ok> ".venv\.deps_ok"
)

REM --- 4. Settings file with a generated secret ---
if not exist ".env" (
  for /f %%i in ('"%VPY%" -c "import secrets;print(secrets.token_urlsafe(48))"') do set "SECRET=%%i"
  powershell -NoProfile -Command "(Get-Content '.env.example') -replace 'NYAYA_SECRET_KEY=change-me','NYAYA_SECRET_KEY=%SECRET%' | Set-Content '.env' -Encoding utf8"
)

REM --- 5. Web interface build ---
if not exist "frontend\dist\index.html" (
  echo  [3/6] Building the web interface...
  pushd frontend
  call npm ci || (popd & goto :fail)
  call npm run build || (popd & goto :fail)
  popd
)

REM --- 6. Database ---
cd /d "%ROOT%backend"
echo  [4/6] Preparing the database...
"%VPY%" -m app.cli migrate || goto :fail

REM --- 7. AI models (about 5.7 GB, once) ---
if not exist "%ROOT%data\.models_ok" (
  echo  [5/6] Downloading the four Law-AI models - about 5.7 GB, once. Keep this window open...
  "%VPY%" -m app.cli download-models || goto :fail
  echo ok> "%ROOT%data\.models_ok"
)

REM --- 8. Legal sources: sample Supreme Court judgments ---
if not exist "%ROOT%data\.corpus_ok" (
  echo.
  echo  [6/6] The app needs legal sources to answer questions.
  echo        Loading 15 sample Supreme Court judgments takes about 15-20 minutes on a laptop.
  echo        Press Y to load them now, or S to skip and start immediately ^(questions will be declined until sources exist^).
  choice /C YS /N /M "  Load now? [Y/S] "
  if errorlevel 2 goto :start
  "%VPY%" -m app.cli ingest-sci --year 2023 --limit 15
  if errorlevel 1 goto :fail
  echo ok> "%ROOT%data\.corpus_ok"
)

:start
cd /d "%ROOT%backend"
echo.
echo  ===========================================================
echo   Nyaya Bharatha is starting at  http://127.0.0.1:8000
echo   Your browser will open in a few seconds.
echo   The first question or translation is slow - models load once.
echo   Close this window ^(or press Ctrl+C^) to stop the app.
echo  ===========================================================
echo.
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://127.0.0.1:8000"
"%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo  The app has stopped.
pause
exit /b 0

REM ------------------------------ helpers ------------------------------------
:install
where winget >nul 2>nul
if errorlevel 1 (
  echo  Please install %~2 manually, then double-click this file again.
  echo  Python: https://www.python.org/downloads/windows/  ^(tick "Add py launcher"^)
  echo  Node.js: https://nodejs.org     Git: https://git-scm.com
  pause
  exit /b 1
)
echo  Installing %~2 ^(Windows may ask for permission^)...
winget install -e --id %~1 --accept-package-agreements --accept-source-agreements
exit /b 0

:relaunch
echo.
echo  A tool was just installed. Windows needs a fresh window to see it.
echo  Re-opening this launcher automatically...
timeout /t 3 /nobreak >nul
start "" cmd /c ""%~f0""
exit /b 0

:fail_clone
echo.
echo  Could not download the project from %REPO_URL%.
echo  If the repository is private, sign in to GitHub in Git first ^(a browser prompt normally appears^), then run this file again.
pause
exit /b 1

:fail
echo.
echo  Something went wrong ^(see the message above^). Fix it or send a screenshot of this window, then double-click this file again -
echo  completed steps are remembered and will be skipped.
pause
exit /b 1
