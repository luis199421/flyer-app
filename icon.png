# Cómo convertir esto en una app instalable (APK)

Compilar una app de Kivy para Android requiere el SDK/NDK de Android (varios GB) y
un entorno Linux. Aquí tienes **dos caminos**. El primero (nube) es el más fácil
y **no necesitas instalar nada** en tu computadora.

---

## ✅ Opción 1 (recomendada): compilar en la nube con GitHub — genera el APK solo

Este proyecto ya incluye un flujo de GitHub Actions (`.github/workflows/build-apk.yml`)
que compila el APK automáticamente en los servidores de GitHub. Pasos:

1. **Crea una cuenta gratis en GitHub** (github.com) si no tienes.

2. **Crea un repositorio nuevo** (botón *New repository*). Ponle cualquier nombre,
   por ejemplo `flyer-app`. Déjalo público o privado, da igual.

3. **Sube todos los archivos de este proyecto** al repositorio. La forma más fácil:
   - En la página del repo vacío, pulsa **"uploading an existing file"**.
   - Arrastra **todos** los archivos y carpetas del ZIP (incluida la carpeta
     oculta `.github`). Si tu explorador no muestra `.github`, actívalo o súbelo aparte.
   - Pulsa **Commit changes**.

   > Importante: deben ir en la **raíz** del repo (que se vean `main.py`,
   > `flyer_render.py`, `buildozer.spec`, `icon.png`, etc., y la carpeta `.github`).

4. **Espera la compilación.** Al subir, GitHub arranca el build automáticamente.
   Ve a la pestaña **Actions** del repo: verás un trabajo "Compilar APK de Android"
   en marcha. La **primera vez tarda ~20-30 min** (descarga el SDK/NDK). Las
   siguientes son mucho más rápidas.

   - Si no arranca solo, entra a **Actions → "Compilar APK de Android" → Run workflow**.

5. **Descarga el APK.** Cuando el trabajo termine (✓ verde), ábrelo y baja hasta
   **Artifacts**. Descarga **`flyer-apk`** (es un ZIP con el archivo `.apk` dentro).

6. **Instálalo en el teléfono.** Pasa el `.apk` al celular (cable, WhatsApp,
   Drive…), ábrelo y acepta **"Instalar apps de origen desconocido"**. ¡Listo!

---

## 🛠️ Opción 2: compilar en tu propia PC (solo Linux o Windows con WSL)

Si prefieres compilar localmente (necesitas Linux o WSL2 en Windows):

```bash
# Dependencias del sistema (Ubuntu/Debian)
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

# Buildozer
pip install --user buildozer cython

# Compilar (la 1ª vez descarga el SDK/NDK; tarda)
cd carpeta-del-proyecto
buildozer -v android debug
```

El APK queda en `bin/`. Para instalarlo con el teléfono conectado por USB:

```bash
buildozer android deploy run
```

---

## Probar la app en tu computadora antes de compilar (opcional)

La misma app corre en escritorio, útil para revisar el formulario:

```bash
pip install kivy pillow qrcode plyer
python main.py
```

---

## Notas

- **Nombre y datos de la app** (título, paquete, versión, permisos) se cambian en
  `buildozer.spec`.
- **Icono y splash**: `icon.png` y `presplash.png`. Reemplázalos por los tuyos si
  quieres (mismo nombre).
- **Código QR**: es opcional. Si la librería `qrcode` fallara al compilar, la app
  igual funciona, solo que sin dibujar el QR.
- **Diseño del flyer**: todo el dibujo está en `flyer_render.py`. Cambiar colores,
  posiciones o tamaños ahí se refleja tanto en escritorio como en el APK.
