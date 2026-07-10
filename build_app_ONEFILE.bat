@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo  Construyendo aplicacion en modo ONEFILE
echo ===============================================
echo ADVERTENCIA: este modo genera un solo .exe, pero puede tardar mucho en abrir
echo y puede ser muy pesado por las librerias de IA.
echo.

if not exist venv\Scripts\activate.bat (
    echo Creando entorno virtual...
    python -m venv venv
)

call venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

if not exist models\all-MiniLM-L6-v2 (
    echo Preparando modelo local para que el .exe no dependa de descarga externa...
    python preparar_modelo.py
)

pyinstaller --noconfirm --clean --onefile --console --name BoletinesCiberseguridad ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "assets;assets" ^
  --add-data "mnt;mnt" ^
  --add-data "models;models" ^
  --add-data "boletin_diario.json;." ^
  --add-data "history.json;." ^
  --collect-all sentence_transformers ^
  --collect-all transformers ^
  --collect-all tokenizers ^
  --collect-all huggingface_hub ^
  --collect-all sklearn ^
  app.py

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo construir el ejecutable.
    pause
    exit /b 1
)

copy /Y .env.example "dist\.env.example" >nul

echo.
echo LISTO.
echo El ejecutable quedo en:
echo dist\BoletinesCiberseguridad.exe
echo.
echo Recuerda poner un archivo .env junto al .exe si necesita la API key.
echo.
pause
