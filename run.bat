@echo off
setlocal enabledelayedexpansion
title Gerenciador do Bot

:: Ajusta o diretorio de trabalho para a pasta do script
cd /d "%~dp0"

:: 1. Verifica se o Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao foi encontrado no PATH do sistema.
    echo Instale o Python e marque a opcao "Add Python to PATH".
    pause
    exit /b 1
)

:: 2. Instala/Atualiza as dependencias se o requirements.txt existir
if exist "requirements.txt" (
    echo [INFO] Verificando e instalando dependencias do requirements.txt...
    python -m pip install --upgrade pip >nul 2>nul
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
) else (
    echo [AVISO] Arquivo requirements.txt nao encontrado. Pulando instalacao.
)

:: 3. Executa o bot
if exist "bot.py" (
    echo.
    echo [OK] Iniciando bot.py...
    echo --------------------------------------------------
    python bot.py
) else (
    echo [ERRO] O arquivo bot.py nao foi encontrado nesta pasta.
    pause
    exit /b 1
)

pause