# Cómo empaquetar el proyecto para abrirlo con doble clic

## Opción recomendada: carpeta con `.exe` (`ONEDIR`)

Esta es la opción más estable para este proyecto porque usa Flask, plantillas HTML, archivos estáticos, logos, XML y un modelo de `sentence-transformers`.

### 1. Descomprimir el proyecto

Descomprime el ZIP en una carpeta normal, por ejemplo:

```text
C:\Users\TuUsuario\Desktop\proyecto_aldo_ligero
```

Evita rutas con caracteres raros o dentro de OneDrive si te da problemas.

### 2. Crear el archivo `.env`

Copia el archivo:

```text
.env.example
```

Pégalo en la misma carpeta y renómbralo como:

```text
.env
```

Dentro coloca la clave real:

```text
PERPLEXITY_API_KEY=tu_clave_real_aqui
PERPLEXITY_MODEL=sonar-pro
```

No mandes tu clave real si vas a compartir el proyecto públicamente.

### 3. Construir el ejecutable

Da doble clic en:

```text
build_app_ONEDIR.bat
```

Ese archivo hará esto automáticamente:

- crea el entorno virtual si no existe;
- instala dependencias;
- instala PyInstaller;
- descarga y guarda localmente el modelo `all-MiniLM-L6-v2`;
- genera el ejecutable.

### 4. Dónde queda la app

Cuando termine, la aplicación queda aquí:

```text
dist\BoletinesCiberseguridad\BoletinesCiberseguridad.exe
```

Para abrirla, entra a esa carpeta y da doble clic en:

```text
BoletinesCiberseguridad.exe
```

La app levanta el servidor local y abre el navegador automáticamente en:

```text
http://127.0.0.1:8000/
```

### 5. Qué debes entregar

No entregues solo el `.exe` cuando uses `ONEDIR`. Debes comprimir y entregar toda esta carpeta:

```text
dist\BoletinesCiberseguridad
```

Puedes renombrar el ZIP final como:

```text
BoletinesCiberseguridad_App.zip
```

La otra persona solo descomprime, entra a la carpeta y abre el `.exe` con doble clic.

## Opción de un solo `.exe` (`ONEFILE`)

También incluí:

```text
build_app_ONEFILE.bat
```

Ese genera:

```text
dist\BoletinesCiberseguridad.exe
```

Pero no es lo más recomendable para este proyecto porque puede pesar mucho, tardar bastante en abrir y fallar más fácilmente con antivirus o rutas temporales.

## Notas importantes

- El ejecutable debe construirse en Windows si se quiere usar en Windows.
- Aunque la versión de código fuente pesa poco, el ejecutable puede pesar mucho por `sentence-transformers`, `transformers`, `torch`, `sklearn` y el modelo local.
- Si al abrirlo se cierra rápido, ejecuta el `.exe` desde CMD para ver el error.
- Si el usuario final necesita generar boletines nuevos, necesita internet y una API key válida en `.env`.
- Los PDF se guardan o generan usando la carpeta `output` junto al `.exe`.
