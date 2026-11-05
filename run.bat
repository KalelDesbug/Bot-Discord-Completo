@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Crie-o ou atualize o caminho neste script.
    exit /b 1
)

".venv\Scripts\python.exe" -m src.bot_app
exit /b %errorlevel%
