@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"

REM -----------------------------------------------------------------------------
REM DreamCoder Windows launcher
REM -----------------------------------------------------------------------------
REM Edit these values if needed before running.
set "DREAMCODER_LOCAL_BACKEND=ollama"
set "OLLAMA_BASE_URL=http://localhost:11434"
set "OLLAMA_MODEL=qwen2.5-coder:7b"
set "DREAMCODER_OLLAMA_PRIMARY_URL=http://localhost:11434"
set "DREAMCODER_OLLAMA_PRIMARY_MODEL=qwen2.5-coder:7b"
set "HF_TOKEN=hf_your_huggingface_token_here"
set "HF_MODEL=meta-llama/Llama-3.1-8B-Instruct"
set "GITHUB_TOKEN=your_github_token_here"
set "DREAMCODER_GITHUB_REPO=PcButNoBTC/DreamCoder"
set "DREAMCODER_GITHUB_BRANCH=main"
set "DREAMCODER_GITHUB_AUTOSYNC=true"

REM Optional GitHub OAuth values
REM set "DREAMCODER_GITHUB_CLIENT_ID="
REM set "DREAMCODER_GITHUB_CLIENT_SECRET="
REM set "DREAMCODER_OAUTH_STATE_SECRET="
REM set "DREAMCODER_GITHUB_CALLBACK=http://127.0.0.1:8000/api/github/oauth/callback"

REM Start Ollama if it is installed locally.
set "OLLAMA_EXE="
if exist "%USERPROFILE%\.ollama\bin\ollama.exe" set "OLLAMA_EXE=%USERPROFILE%\.ollama\bin\ollama.exe"
if not defined OLLAMA_EXE if exist "C:\Program Files\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "C:\Program Files (x86)\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files (x86)\Ollama\ollama.exe"
if defined OLLAMA_EXE (
    echo Starting Ollama server...
    start "Ollama Server" cmd /k ""%OLLAMA_EXE%" serve"
    ping 127.0.0.1 -n 4 > nul
    echo Pulling model qwen2.5-coder:7b...
    call "%OLLAMA_EXE%" pull qwen2.5-coder:7b
) else (
    echo Ollama was not found on this machine. Install it from https://ollama.com/download and rerun this launcher.
)

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
