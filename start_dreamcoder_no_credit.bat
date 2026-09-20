@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"

REM -----------------------------------------------------------------------------
REM DreamCoder local/no-credit launcher
REM -----------------------------------------------------------------------------
REM Prefer local open-source models via Ollama instead of paid credit-based APIs.
set "DREAMCODER_LOCAL_BACKEND=ollama"
set "OLLAMA_BASE_URL=http://localhost:11434"
set "OLLAMA_MODEL=qwen2.5-coder:7b"
set "DREAMCODER_OLLAMA_PRIMARY_URL=http://localhost:11434"
set "DREAMCODER_OLLAMA_PRIMARY_MODEL=qwen2.5-coder:7b"
set "HF_TOKEN=hf_your_huggingface_token_here"
set "HF_MODEL=meta-llama/Llama-3.1-8B-Instruct"

REM Optional GitHub settings
set "GITHUB_TOKEN="
set "DREAMCODER_GITHUB_REPO=PcButNoBTC/DreamCoder"
set "DREAMCODER_GITHUB_BRANCH=main"
set "DREAMCODER_GITHUB_AUTOSYNC=true"

REM Detect/install Ollama automatically, then start it.
set "OLLAMA_EXE="
where ollama >nul 2>nul
if not errorlevel 1 for /f "delims=" %%I in ('where ollama 2^>nul') do set "OLLAMA_EXE=%%I"
if not defined OLLAMA_EXE if exist "%USERPROFILE%\.ollama\bin\ollama.exe" set "OLLAMA_EXE=%USERPROFILE%\.ollama\bin\ollama.exe"
if not defined OLLAMA_EXE if exist "C:\Program Files\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "C:\Program Files (x86)\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files (x86)\Ollama\ollama.exe"
if not defined OLLAMA_EXE (
    echo Ollama was not detected. Trying to install it automatically...
    where winget >nul 2>nul
    if not errorlevel 1 (
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
        if not errorlevel 1 (
            where ollama >nul 2>nul
            if not errorlevel 1 for /f "delims=" %%I in ('where ollama 2^>nul') do set "OLLAMA_EXE=%%I"
        )
    )
)
if defined OLLAMA_EXE (
    echo Starting Ollama server...
    start "Ollama Server" cmd /k ""%OLLAMA_EXE%" serve"
    ping 127.0.0.1 -n 4 > nul
    echo Pulling model qwen2.5-coder:7b...
    call "%OLLAMA_EXE%" pull qwen2.5-coder:7b
    set "DREAMCODER_LOCAL_BACKEND=ollama"
) else (
    echo Ollama could not be installed automatically.
    echo Falling back to the Hugging Face backend instead of blocking startup.
    set "DREAMCODER_LOCAL_BACKEND=huggingface"
)

REM Start backend
start "DreamCoder Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

REM Pause briefly to allow the API time to bind.
ping 127.0.0.1 -n 4 > nul

REM Start the static frontend from the actual frontend/ directory
start "DreamCoder Frontend" cmd /k "cd /d ""%ROOT%frontend"" && python -m http.server 8001"

REM Open browser
start "" "http://127.0.0.1:8001/index.html"

echo DreamCoder local/no-credit launcher started.
echo.
echo If Ollama is not running yet, install/start it and pull a model:
echo   ollama pull qwen2.5-coder:7b

echo Then start the app and select the local provider in the model selector.
echo.
echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:8001/index.html

echo If the page still shows offline, open DevTools and run:
echo   window.DREAMCODER_API = "http://127.0.0.1:8000";
echo   location.reload();

exit /b 0
