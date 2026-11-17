@echo off
setlocal
cd /d "%~dp0"
title Descargador
set "VENV=%LOCALAPPDATA%\Descargador\venv"

if exist "%VENV%\Scripts\pythonw.exe" goto actualizar

echo Preparando el descargador por primera vez. Tarda un par de minutos...
py -3 -m venv "%VENV%" >nul 2>nul
if not exist "%VENV%\Scripts\python.exe" python -m venv "%VENV%" >nul 2>nul
if not exist "%VENV%\Scripts\python.exe" goto sinpython

:actualizar
echo Buscando actualizaciones...
"%VENV%\Scripts\python.exe" -m pip install -q --disable-pip-version-check -U -r requirements.txt
if errorlevel 1 echo No se pudo actualizar. Sigo con la version que ya tengo.
"%VENV%\Scripts\python.exe" -c "import yt_dlp, tkinter" >nul 2>nul
if errorlevel 1 goto roto

start "" "%VENV%\Scripts\pythonw.exe" "%~dp0descargador.py"
exit /b 0

:sinpython
echo.
echo No encontre Python en este PC.
echo Instalalo desde https://www.python.org/downloads/
echo Durante la instalacion marca la casilla "Add python.exe to PATH".
echo Luego vuelve a abrir este archivo.
echo.
pause
exit /b 1

:roto
echo.
echo Algo fallo al instalar lo necesario. Revisa tu internet y vuelve a abrir este archivo.
echo Si sigue fallando, borra la carpeta "%LOCALAPPDATA%\Descargador" y prueba otra vez.
echo.
pause
exit /b 1
