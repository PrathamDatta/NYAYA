@echo off
REM ===========================================================================
REM  One-click launcher for Windows 10/11.  Double-click this file.
REM  The window stays open on purpose, so you can always read what happened.
REM  First run: installs missing tools, downloads ~6 GB of models, loads sample
REM  judgments, then starts the app. Every finished step is remembered.
REM ===========================================================================
if /i not "%~1"=="stay" (
  cmd /k ""%~f0" stay"
  exit /b
)
setlocal EnableExtensions
title Nyaya Bharatha launcher
set "REPO_URL=https://github.com/PrathamDatta/NYAYA"
set "BRANCH=main"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "LOG=%TEMP%\nyaya-launcher.log"
echo Launcher started %DATE% %TIME%> "%LOG%"

echo.
echo  ==============  Nyaya Bharatha launcher  ==============
echo.

REM --- Where is the project? (works even if only this one file was downloaded) ---
set "ROOT=%~dp0"
if not exist "%ROOT%backend\app\main.py" set "ROOT=%USERPROFILE%\NYAYA\"
echo  Project folder: %ROOT%

REM --- Git (only needed when the project has to be downloaded) ---
if not exist "%ROOT%backend\app\main.py" (
  where git >nul 2>nul
  if errorlevel 1 call :install Git.Git "Git"
  call :refreshpath
  where git >nul 2>nul
  if errorlevel 1 goto :fail_tool
  echo  Downloading the project from GitHub...
  git clone -b %BRANCH% %REPO_URL% "%ROOT:~0,-1%"
  if errorlevel 1 goto :fail_clone
)

REM --- Pick up fixes: update an existing download (only when this file is NOT the one inside the project, since git would rewrite a running script) ---
if exist "%ROOT%.git" if /i not "%~dp0"=="%ROOT%" (
  echo  Checking for updates...
  git -C "%ROOT:~0,-1%" pull --ff-only
)

REM --- Python 3.11 or 3.12 (3.10 and older are too old for the pinned packages) ---
call :findpython
if not defined PY (
  call :install Python.Python.3.12 "Python 3.12"
  call :refreshpath
  call :findpython
)
if not defined PY goto :fail_tool
echo  Python found: %PY%

REM --- Node.js (to build the web interface once) ---
where npm >nul 2>nul
if errorlevel 1 (
  if not exist "%ROOT%frontend\dist\index.html" (
    call :install OpenJS.NodeJS.LTS "Node.js"
    call :refreshpath
  )
)
if not exist "%ROOT%frontend\dist\index.html" (
  where npm >nul 2>nul
  if errorlevel 1 goto :fail_tool
)

cd /d "%ROOT%"
set "VPY=%ROOT%.venv\Scripts\python.exe"

echo.
echo  [1/6] Python environment
if exist "%VPY%" (
  "%VPY%" -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo  The existing environment was built with an old Python - rebuilding it...
    rmdir /s /q .venv
  )
)
if not exist "%VPY%" (
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)

echo  [2/6] Python packages (a few minutes, first run only)
if not exist ".venv\.deps_ok" (
  "%VPY%" -m pip install --upgrade pip >nul 2>nul
  call :pipretry torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
  if errorlevel 1 goto :fail
  call :pipretry -r backend\requirements.txt
  if errorlevel 1 goto :fail
  echo ok> ".venv\.deps_ok"
)

if not exist ".env" (
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N')"`) do set "SECRET=%%i"
  powershell -NoProfile -Command "(Get-Content '.env.example') -replace 'NYAYA_SECRET_KEY=change-me','NYAYA_SECRET_KEY=%SECRET%' | Set-Content '.env' -Encoding utf8"
)

echo  [3/6] Web interface
if not exist "frontend\dist\index.html" (
  pushd frontend
  call npm ci
  if errorlevel 1 ( popd & goto :fail )
  call npm run build
  if errorlevel 1 ( popd & goto :fail )
  popd
)

echo  [4/6] Database
cd /d "%ROOT%backend"
"%VPY%" -m app.cli migrate
if errorlevel 1 goto :fail

echo  [5/6] AI models (about 5.7 GB, first run only - keep this window open)
if not exist "%ROOT%data" mkdir "%ROOT%data"
if not exist "%ROOT%data\.models_ok" (
  call :cliretry download-models
  if errorlevel 1 goto :fail
  echo ok> "%ROOT%data\.models_ok"
)

echo  [6/6] Legal sources
if not exist "%ROOT%data\.corpus_ok" (
  echo.
  echo   The app answers only from legal sources it has loaded.
  echo   Loading 15 sample Supreme Court judgments takes about 15-20 minutes.
  echo   Press Y to load them now, or S to skip and start right away.
  choice /C YS /N /M "   Load now? [Y/S] "
  if errorlevel 2 goto :start
  call :cliretry ingest-sci --year 2023 --limit 15
  if errorlevel 1 goto :fail
  echo ok> "%ROOT%data\.corpus_ok"
)

:start
cd /d "%ROOT%backend"
echo.
echo  ===========================================================
echo    Nyaya Bharatha is starting at  http://127.0.0.1:8000
echo    Your browser opens in a few seconds.
echo    The first question or translation is slow: models load once.
echo    To stop the app, close this window.
echo  ===========================================================
echo.
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://127.0.0.1:8000"
"%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo  The app stopped. Scroll up to see why, or run this file again.
goto :eof

REM ------------------------------ helpers ------------------------------------
:findpython
set "PY="
py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3.11 --version >nul 2>nul && set "PY=py -3.11"
exit /b 0

:pipretry
REM Downloads can drop on unstable Wi-Fi: retry up to 5 times; pip resumes from its cache.
set "N=0"
:pipretry_loop
set /a N+=1
"%VPY%" -m pip install --retries 10 --timeout 120 %*
if not errorlevel 1 exit /b 0
if %N% GEQ 5 exit /b 1
echo.
echo  The connection dropped. Retrying, attempt %N% of 5...
timeout /t 5 /nobreak >nul
goto :pipretry_loop

:cliretry
REM Same idea for the model and judgment downloads (both are safe to repeat and resume).
set "M=0"
:cliretry_loop
set /a M+=1
"%VPY%" -m app.cli %*
if not errorlevel 1 exit /b 0
if %M% GEQ 5 exit /b 1
echo.
echo  The connection dropped. Retrying, attempt %M% of 5...
timeout /t 5 /nobreak >nul
goto :cliretry_loop

:install
echo  Installing %~2 - Windows may ask for permission...
where winget >nul 2>nul
if errorlevel 1 (
  echo  winget is not available on this PC.
  exit /b 1
)
winget install -e --id %~1 --accept-package-agreements --accept-source-agreements
exit /b 0

:refreshpath
REM Pick up tools that were installed a moment ago without opening a new window.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%PATH%"
exit /b 0

:fail_tool
echo.
echo  A required tool (Git, Python 3.11 or 3.12, or Node.js) is missing and could not be installed automatically.
echo  Install these by hand, then double-click this file again:
echo    Python 3.12 : https://www.python.org/downloads/windows/   (tick "Add py launcher")
echo    Node.js LTS : https://nodejs.org
echo    Git         : https://git-scm.com
goto :eof

:fail_clone
echo.
echo  Could not download the project from %REPO_URL%
echo  If the repository is private, sign in to GitHub when Git asks, or download the ZIP from GitHub,
echo  unzip it, put this file inside the unzipped folder and run it from there.
goto :eof

:fail
echo.
echo  Something went wrong - see the message above. Take a screenshot of this window and send it over.
echo  Steps that already finished are remembered, so running this file again continues from here.
goto :eof
