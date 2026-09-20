@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"

REM -----------------------------------------------------------------------------
REM DreamCoder Windows launcher
REM -----------------------------------------------------------------------------
REM Edit these values if needed before running.
set "GITHUB_TOKEN="
set "DREAMCODER_GITHUB_REPO=PcButNoBTC/DreamCoder"
set "DREAMCODER_GITHUB_BRANCH=main"
set "DREAMCODER_GITHUB_AUTOSYNC=true"

REM Optional GitHub OAuth values
REM set "DREAMCODER_GITHUB_CLIENT_ID="
REM set "DREAMCODER_GITHUB_CLIENT_SECRET="
REM set "DREAMCODER_OAUTH_STATE_SECRET="
REM set "DREAMCODER_GITHUB_CALLBACK=http://127.0.0.1:8000/api/github/oauth/callback"

REM Start the FastAPI backend
start "DreamCoder Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

REM Small pause so the backend can start before the frontend opens
ping 127.0.0.1 -n 4 > nul

REM Serve the frontend on port 8001
start "DreamCoder Frontend" cmd /k "cd /d ""%ROOT%"" && python -m http.server 8001 --directory ""%ROOT%"""

REM Open the app in the default browser
start "" "http://127.0.0.1:8001/frontend/index.html"

echo DreamCoder started.
echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:8001/frontend/index.html
echo.
echo If the page still shows offline, open DevTools and run:
echo   window.DREAMCODER_API = "http://127.0.0.1:8000";
echo   location.reload();

exit /b 0
