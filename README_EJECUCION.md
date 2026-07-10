# Proyecto Aldo - versión ligera

Esta carpeta contiene el proyecto listo para enviarse sin la carpeta `venv`, archivos temporales ni PDFs generados.

## Qué se quitó para hacerlo ligero

- `venv/`: no debe enviarse; cada computadora debe crear su propio entorno virtual.
- `__pycache__/` y `.ipynb_checkpoints/`: archivos temporales.
- PDFs de `output/` y PDFs generados en la raíz: se vuelven a crear desde la aplicación.

## Requisitos

- Python 3.11 o 3.12 recomendado.
- Conexión a internet la primera vez para instalar librerías y descargar el modelo `all-MiniLM-L6-v2`.
- Clave de Perplexity en un archivo `.env`.

## Instalación en Windows

1. Descomprime el ZIP.
2. Entra a la carpeta del proyecto.
3. Abre CMD o PowerShell dentro de esa carpeta.
4. Ejecuta:

```bat
python -m venv venv
venv\Scriptsctivate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Copia `.env.example`, renómbralo como `.env` y coloca la clave real:

```env
PERPLEXITY_API_KEY=tu_clave_real
PERPLEXITY_MODEL=sonar-pro
```

6. Ejecuta:

```bat
python app.py
```

La aplicación abre el navegador en:

```text
http://127.0.0.1:8000/
```

## Ejecución rápida en Windows

Después de instalar dependencias y configurar `.env`, puedes abrir:

```bat
run_app.bat
```

## Crear un ejecutable opcional

El archivo `build_exe.bat` intenta crear un `.exe` con PyInstaller. Ojo: por `sentence-transformers`, `torch` y el modelo de embeddings, el ejecutable puede quedar pesado. Para entregar o compartir el código, conviene más mandar este ZIP ligero.
