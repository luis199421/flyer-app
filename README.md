# Generador de Flyers Inmobiliarios — versión Android (Kivy)

Port a Python-para-Android del programa original `Muther_program__2_.exe`
(una app de escritorio en **tkinter + Pillow**, empaquetada con PyInstaller,
Python 3.14). Genera flyers inmobiliarios de 1080×1440 px.

## Por qué fue necesario reescribir la interfaz

El programa original usa **tkinter**, que **no funciona en Android**. La lógica
de dibujo, en cambio, usa **Pillow**, que sí se puede compilar para Android con
Buildozer. Por eso el port separa el proyecto en dos partes:

| Archivo | Qué es | Cambió respecto al original |
|---|---|---|
| `flyer_render.py` | Motor de imagen (Pillow puro) | Portado casi literal — misma lógica y diseño |
| `main.py` | Interfaz (Kivy) | Reescrito desde cero (tkinter → Kivy) |
| `buildozer.spec` | Configuración de empaquetado Android | Nuevo |
| `flyer_recovered_original.py` | Código fuente recuperado del .exe | Solo referencia |

El resultado visual es el mismo: cabecera con foto y borde naranja, badge de
operación, chip de tipo de propiedad, título/subtítulo, miniaturas de fotos,
celda de precio, rejilla de características, nota, y pie con contacto + QR.

## Archivos

- **`flyer_render.py`** — `generate_flyer(data, output_path)` y todas las
  funciones de apoyo (fuentes, ajuste de texto, precio con comas, QR, pegado de
  imágenes con esquinas redondeadas). Funciona igual en escritorio y en Android.
- **`main.py`** — App Kivy con formulario desplazable (operación, propiedad,
  encabezado, precio, contacto, ubicación, fotos, logos, características, nota,
  QR), selector de imágenes, generación en segundo plano, vista previa y botón
  de compartir (Intent de Android).
- **`buildozer.spec`** — Empaqueta todo como APK.

## Probar en escritorio (rápido)

```bash
pip install pillow qrcode          # qrcode es opcional
python flyer_render.py             # genera demo_flyer.png (sin interfaz)

pip install kivy plyer             # para la interfaz
python main.py                     # abre la app en una ventana
```

## Compilar el APK (Android)

Buildozer solo funciona en **Linux** (o WSL en Windows). En una máquina limpia:

```bash
# 1) Dependencias del sistema (Ubuntu/Debian)
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

# 2) Buildozer
pip install --user buildozer cython

# 3) Compilar (la primera vez descarga el Android SDK/NDK; tarda bastante)
cd carpeta_del_proyecto
buildozer -v android debug
```

El APK queda en `bin/flyergen-1.0-arm64-v8a_armeabi-v7a-debug.apk`.
Instálalo en el teléfono con:

```bash
buildozer android deploy run          # con el teléfono conectado por USB
# o copia el .apk al teléfono y ábrelo (activa "instalar apps desconocidas")
```

> **Nota sobre el QR:** si `qrcode` no compila en tu entorno, la app sigue
> funcionando: simplemente no dibuja el código QR. Es opcional por diseño.

## Modelo de datos

`generate_flyer` recibe un diccionario con estas claves (todas opcionales):

```
tipo_operacion   "VENTA" | "RENTA" | "VENTA Y RENTA"
tipo_propiedad   "Casa", "Departamento", ...
titulo, subtitulo
precio           "3450000"  ->  se formatea a  "$3,450,000"
foto_principal   ruta de imagen
fotos_adicionales  lista de rutas (se muestran hasta 3)
logo_path, logo2_path  rutas de logos
caracteristicas  lista de {"label": "...", "valor": "..."} (hasta 8)
nota
qr_link          URL para el código QR
telefono1, telefono2, colonia, direccion, marca
```

## Sobre la recuperación del código

El `.exe` era un ejecutable de PyInstaller con bytecode de **Python 3.14**, para
el cual todavía no existe un decompilador público. El código se recuperó
extendiendo el decompilador `pycdc` con soporte completo para el bytecode 3.14
(nuevos opcodes como `LOAD_FAST_BORROW`, `LOAD_SMALL_INT`, `CALL_KW`,
`SET_FUNCTION_ATTRIBUTE`, la fusión de `BINARY_SUBSCR` en `BINARY_OP`, etc.).
`flyer_recovered_original.py` es esa recuperación (≈95 % limpia; algunos
bloques `try/except` y bucles `while` de la interfaz tkinter quedaron con
pequeños defectos de reconstrucción, irrelevantes porque la interfaz se
reescribió en Kivy).
