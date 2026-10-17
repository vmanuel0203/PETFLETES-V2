@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title PetFletes

rem Uso:  iniciar.bat          -> modo normal (sin cuentas ni datos demo)
rem       iniciar.bat demo     -> modo demo (PETFLETES_DEMO=1: cuentas de prueba y ofertas simuladas)
if /i "%~1"=="demo" (
    set PETFLETES_DEMO=1
    echo [PetFletes] Modo DEMO activado.
) else (
    echo [PetFletes] Modo normal. Para cuentas de prueba usa:  iniciar.bat demo
)

python -c "import streamlit, pandas, folium, streamlit_folium" >nul 2>&1
if errorlevel 1 (
    echo [PetFletes] Instalando dependencias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [PetFletes] No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
)

echo [PetFletes] Iniciando en http://localhost:8501  (Ctrl+C para detener)
python -m streamlit run app.py
pause
