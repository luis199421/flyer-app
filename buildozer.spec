[app]

# Nombre visible de la app
title = Generador de Flyers

# Identificadores del paquete
package.name = flyergen
package.domain = com.luisstudio

# Código fuente
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json,kv

# Versión
version = 1.0

# Dependencias de Python.
#  - pillow: motor de imagen (flyer_render)
#  - qrcode: códigos QR (opcional; si falla, la app funciona sin QR)
#  - plyer: selector de archivos multiplataforma
#  - pyjnius: puente Python<->Java (permisos, compartir, almacenamiento Android)
# El módulo `android` lo aporta automáticamente el bootstrap SDL2 de p4a.
requirements = python3,kivy,pillow,qrcode,plyer,pyjnius

# Icono de la app y pantalla de carga
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #1A1A2E

# Orientación
orientation = portrait

# Pantalla completa desactivada (se ve la barra de estado)
fullscreen = 0

# --- Android ---------------------------------------------------------------- #
# Permisos necesarios: leer imágenes de la galería y escribir el PNG generado.
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_IMAGES

# API objetivo y mínima (Play Store exige target alto; min 24 cubre 99% de equipos)
android.api = 34
android.minapi = 24

# NDK fija a la versión estable más probada por python-for-android.
# (Dejarla en automático descargaba la r28c, que rompe la compilación nativa.)
android.ndk = 25b

# Arquitecturas (la mayoría de teléfonos modernos son arm64; se incluye armeabi por compatibilidad)
# Una sola arquitectura: arm64-v8a cubre prácticamente todos los teléfonos
# actuales, compila el doble de rápido y evita fallos de armeabi-v7a.
android.archs = arm64-v8a

# AndroidX es necesario para FileProvider (compartir la imagen)
android.enable_androidx = True

# Acepta automáticamente las licencias del SDK durante la primera compilación
android.accept_sdk_license = True

# Bootstrap de p4a
p4a.bootstrap = sdl2


[buildozer]

# Nivel de log (2 = detallado, útil la primera vez)
log_level = 2

# No ejecutar como root
warn_on_root = 1
