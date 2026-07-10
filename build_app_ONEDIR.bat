@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo  Construyendo aplicacion en modo ONEDIR
echo ===============================================

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

pyinstaller --noconfirm --clean --onedir --console --name BoletinesCiberseguridad ^
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

copy /Y .env.example "dist\BoletinesCiberseguridad\.env.example" >nul

echo.
echo LISTO.
echo La aplicacion quedo en:
echo dist\BoletinesCiberseguridad\BoletinesCiberseguridad.exe
echo.
echo Para entregarla, comprime TODA la carpeta:
echo dist\BoletinesCiberseguridad
echo.
pause
