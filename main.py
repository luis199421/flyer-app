"""
main.py — Generador de Flyers Inmobiliarios (versión Android / Kivy).

Port de la app original de escritorio (tkinter) a Kivy para poder empaquetarla
como APK con Buildozer. Toda la lógica de dibujo vive en flyer_render.py
(Pillow puro), que funciona igual en Android.

Ejecutar en escritorio para probar:   python main.py
Empaquetar para Android:              buildozer -v android debug
"""

import os
import json
import threading 
from datetime import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.image import Image as KivyImage
from kivy.uix.popup import Popup

import flyer_render as fr

# ---- Paleta (equivalente a la del original) -------------------------------- #
C = {
    "amber":  (0.96, 0.65, 0.14, 1),
    "amber_d":(0.83, 0.54, 0.10, 1),
    "dark":   (0.10, 0.10, 0.18, 1),
    "dark2":  (0.18, 0.18, 0.27, 1),
    "ink":    (0.24, 0.24, 0.24, 1),
    "muted":  (0.53, 0.53, 0.53, 1),
    "bg":     (0.97, 0.96, 0.94, 1),
    "surface":(1, 1, 1, 1),
    "green":  (0.14, 0.83, 0.40, 1),
    "white":  (1, 1, 1, 1),
}

# --------------------------------------------------------------------------- #
#  Almacenamiento / rutas (compatibles con Android)
# --------------------------------------------------------------------------- #
def app_dir():
    """Carpeta con permiso de escritura, tanto en Android como en escritorio."""
    try:
        from android.storage import app_storage_path  # type: ignore
        base = app_storage_path()
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".flyer_app")
    os.makedirs(base, exist_ok=True)
    return base


def output_dir():
    d = os.path.join(app_dir(), "Flyers")
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_FILE = os.path.join(app_dir(), "flyer_config.json")


def request_android_permissions():
    """Solicita permisos de almacenamiento/fotos en Android (no-op en escritorio)."""
    try:
        from android.permissions import request_permissions, Permission  # type: ignore
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_MEDIA_IMAGES,
        ])
    except Exception:
        pass


def pick_image(callback):
    """Abre el selector de imágenes (plyer). callback(path|None)."""
    try:
        from plyer import filechooser  # type: ignore

        def _on_selection(selection):
            callback(selection[0] if selection else None)

        filechooser.open_file(
            on_selection=_on_selection,
            filters=[["Imágenes", "*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"]],
        )
    except Exception as e:
        print("filechooser no disponible:", e)
        callback(None)


# --------------------------------------------------------------------------- #
#  Widgets reutilizables
# --------------------------------------------------------------------------- #
class SectionLabel(Label):
    def __init__(self, text, **kw):
        super().__init__(
            text=f"[b]{text}[/b]", markup=True, color=C["amber_d"],
            size_hint_y=None, height=dp(34), halign="left", valign="middle",
            font_size=dp(16), **kw,
        )
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))


class Field(BoxLayout):
    """Etiqueta + TextInput vertical."""
    def __init__(self, label, hint="", multiline=False, **kw):
        super().__init__(orientation="vertical", size_hint_y=None,
                         spacing=dp(2), **kw)
        self.height = dp(78) if multiline else dp(58)
        self.add_widget(Label(
            text=label, size_hint_y=None, height=dp(18), halign="left",
            valign="middle", color=C["ink"], font_size=dp(12),
            text_size=(Window.width, dp(18)),
        ))
        self.input = TextInput(
            hint_text=hint, multiline=multiline, size_hint_y=None,
            height=dp(52) if multiline else dp(36), font_size=dp(15),
            padding=[dp(8), dp(8)],
        )
        self.add_widget(self.input)

    @property
    def value(self):
        return self.input.text.strip()

    @value.setter
    def value(self, v):
        self.input.text = v or ""


class PhotoPicker(BoxLayout):
    """Botón para elegir una imagen + muestra la ruta elegida."""
    def __init__(self, label, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(48), spacing=dp(6), **kw)
        self.path = ""
        self._label = label
        self.btn = Button(text=f"📷 {label}", size_hint_x=0.5,
                          background_color=C["dark2"], color=C["white"],
                          font_size=dp(13))
        self.btn.bind(on_release=lambda *_: pick_image(self._set))
        self.status = Label(text="Sin imagen", color=C["muted"],
                            font_size=dp(12), halign="left", valign="middle")
        self.status.bind(size=lambda *_: setattr(self.status, "text_size", self.status.size))
        self.clear_btn = Button(text="✕", size_hint_x=None, width=dp(36),
                                background_color=(0.9, 0.27, 0.27, 1), color=C["white"])
        self.clear_btn.bind(on_release=lambda *_: self._set(None))
        self.add_widget(self.btn)
        self.add_widget(self.status)
        self.add_widget(self.clear_btn)

    @mainthread
    def _set(self, path):
        self.path = path or ""
        self.status.text = os.path.basename(path) if path else "Sin imagen"


# --------------------------------------------------------------------------- #
#  Pantalla principal
# --------------------------------------------------------------------------- #
class FlyerRoot(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.caract_fields = []
        self.last_output = ""
        self._build()
        Clock.schedule_once(lambda *_: self._load_config(), 0.2)

    # ---- construcción de la interfaz ---- #
    def _build(self):
        # Barra superior
        top = BoxLayout(size_hint_y=None, height=dp(52), padding=[dp(12), 0])
        with top.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*C["dark"])
            self._top_rect = Rectangle(pos=top.pos, size=top.size)
        top.bind(pos=lambda *_: setattr(self._top_rect, "pos", top.pos),
                 size=lambda *_: setattr(self._top_rect, "size", top.size))
        title = Label(text="[b]🏠 Generador de Flyers[/b]", markup=True,
                      color=C["white"], font_size=dp(18), halign="left", valign="middle")
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))
        top.add_widget(title)
        self.add_widget(top)

        # Formulario desplazable
        scroll = ScrollView()
        form = GridLayout(cols=1, size_hint_y=None, padding=dp(12), spacing=dp(4))
        form.bind(minimum_height=form.setter("height"))
        self.form = form

        # Sección: Operación y propiedad
        form.add_widget(SectionLabel("Operación y Propiedad"))
        self.sp_op = Spinner(text="VENTA", values=fr.TIPOS_OP, size_hint_y=None,
                             height=dp(40), background_color=C["amber"])
        form.add_widget(self._labeled("Tipo de operación", self.sp_op))
        self.sp_prop = Spinner(text="Casa", values=fr.TIPOS_PROP, size_hint_y=None,
                               height=dp(40), background_color=C["dark2"], color=C["white"])
        form.add_widget(self._labeled("Tipo de propiedad", self.sp_prop))

        # Sección: Encabezado
        form.add_widget(SectionLabel("Encabezado"))
        self.f_titulo = Field("Título", "Ej: Hermosa casa en venta")
        self.f_sub = Field("Subtítulo", "Ej: Excelente ubicación")
        form.add_widget(self.f_titulo)
        form.add_widget(self.f_sub)

        # Sección: Precio
        form.add_widget(SectionLabel("Precio"))
        self.f_precio = Field("Precio", "Ej: 3450000  o  $3,450,000 MXN")
        form.add_widget(self.f_precio)

        # Sección: Contacto
        form.add_widget(SectionLabel("Contacto"))
        self.f_marca = Field("Marca / Inmobiliaria", "Ej: Luis Studio")
        self.f_tel1 = Field("Teléfono 1", "Ej: 555-123-4567")
        self.f_tel2 = Field("Teléfono 2 (WhatsApp)", "Ej: 555-765-4321")
        for w in (self.f_marca, self.f_tel1, self.f_tel2):
            form.add_widget(w)

        # Sección: Ubicación
        form.add_widget(SectionLabel("Ubicación"))
        self.f_colonia = Field("Colonia", "Ej: Col. Del Valle")
        self.f_direccion = Field("Dirección", "Ej: Av. Principal #123")
        form.add_widget(self.f_colonia)
        form.add_widget(self.f_direccion)

        # Sección: Fotos
        form.add_widget(SectionLabel("Fotos"))
        self.pk_principal = PhotoPicker("Foto principal")
        self.pk_ad1 = PhotoPicker("Foto adicional 1")
        self.pk_ad2 = PhotoPicker("Foto adicional 2")
        self.pk_ad3 = PhotoPicker("Foto adicional 3")
        for w in (self.pk_principal, self.pk_ad1, self.pk_ad2, self.pk_ad3):
            form.add_widget(w)

        # Sección: Logos
        form.add_widget(SectionLabel("Logos"))
        self.pk_logo = PhotoPicker("Logo 1")
        self.pk_logo2 = PhotoPicker("Logo 2")
        form.add_widget(self.pk_logo)
        form.add_widget(self.pk_logo2)

        # Sección: Características
        form.add_widget(SectionLabel("Características (hasta 8)"))
        self.caract_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        self.caract_box.bind(minimum_height=self.caract_box.setter("height"))
        form.add_widget(self.caract_box)
        for label, valor in fr.CARACT_DEF[:4]:
            self._add_caract(label, valor)
        add_c = Button(text="+ Añadir característica", size_hint_y=None, height=dp(38),
                       background_color=C["dark2"], color=C["white"])
        add_c.bind(on_release=lambda *_: self._add_caract("", ""))
        form.add_widget(add_c)

        # Sección: Nota y QR
        form.add_widget(SectionLabel("Nota y QR"))
        self.f_nota = Field("Nota", "Ej: Aceptamos crédito Infonavit", multiline=True)
        self.f_qr = Field("Enlace para QR", "Ej: https://...")
        form.add_widget(self.f_nota)
        form.add_widget(self.f_qr)

        scroll.add_widget(form)
        self.add_widget(scroll)

        # Barra inferior de acciones
        bottom = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8),
                           padding=[dp(10), dp(8)])
        gen = Button(text="✨ Generar Flyer", background_color=C["amber"],
                     color=C["dark"], font_size=dp(16), bold=True)
        gen.bind(on_release=lambda *_: self._generate())
        self.btn_gen = gen
        bottom.add_widget(gen)
        self.add_widget(bottom)

    def _labeled(self, label, widget):
        box = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=dp(62), spacing=dp(2))
        lb = Label(text=label, size_hint_y=None, height=dp(18), halign="left",
                   valign="middle", color=C["ink"], font_size=dp(12),
                   text_size=(Window.width, dp(18)))
        box.add_widget(lb)
        box.add_widget(widget)
        return box

    def _add_caract(self, label, valor):
        if len(self.caract_fields) >= 8:
            return
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(40), spacing=dp(6))
        lab = TextInput(text=label, hint_text="Etiqueta", multiline=False,
                        size_hint_x=0.5, font_size=dp(13), padding=[dp(6), dp(8)])
        val = TextInput(text=valor, hint_text="Valor", multiline=False,
                        size_hint_x=0.5, font_size=dp(13), padding=[dp(6), dp(8)])
        rm = Button(text="✕", size_hint_x=None, width=dp(36),
                    background_color=(0.9, 0.27, 0.27, 1), color=C["white"])
        entry = {"row": row, "label": lab, "valor": val}

        def _remove(*_):
            self.caract_box.remove_widget(row)
            if entry in self.caract_fields:
                self.caract_fields.remove(entry)
        rm.bind(on_release=_remove)
        row.add_widget(lab)
        row.add_widget(val)
        row.add_widget(rm)
        self.caract_box.add_widget(row)
        self.caract_fields.append(entry)

    # ---- recolección de datos ---- #
    def _collect(self):
        adic = [p.path for p in (self.pk_ad1, self.pk_ad2, self.pk_ad3) if p.path]
        caract = []
        for e in self.caract_fields:
            lb = e["label"].text.strip()
            vl = e["valor"].text.strip()
            if lb or vl:
                caract.append({"label": lb, "valor": vl})
        return {
            "tipo_operacion": self.sp_op.text,
            "tipo_propiedad": self.sp_prop.text,
            "titulo": self.f_titulo.value,
            "subtitulo": self.f_sub.value,
            "precio": self.f_precio.value,
            "marca": self.f_marca.value,
            "telefono1": self.f_tel1.value,
            "telefono2": self.f_tel2.value,
            "colonia": self.f_colonia.value,
            "direccion": self.f_direccion.value,
            "foto_principal": self.pk_principal.path,
            "fotos_adicionales": adic,
            "logo_path": self.pk_logo.path,
            "logo2_path": self.pk_logo2.path,
            "caracteristicas": caract,
            "nota": self.f_nota.value,
            "qr_link": self.f_qr.value,
        }

    # ---- generación (en hilo aparte para no congelar la UI) ---- #
    def _generate(self):
        self.btn_gen.text = "Generando..."
        self.btn_gen.disabled = True
        data = self._collect()
        self._save_config(data)
        threading.Thread(target=self._do_generate, args=(data,), daemon=True).start()

    def _do_generate(self, data):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = os.path.join(output_dir(), f"flyer_{ts}.png")
            fr.generate_flyer(data, out)
            self.last_output = out
            self._show_result(out)
        except Exception as e:
            self._show_error(str(e))
        finally:
            self._reset_btn()

    @mainthread
    def _reset_btn(self):
        self.btn_gen.text = "✨ Generar Flyer"
        self.btn_gen.disabled = False

    @mainthread
    def _show_result(self, path):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        content.add_widget(KivyImage(source=path, allow_stretch=True, keep_ratio=True))
        info = Label(text=f"Guardado en:\n{path}", size_hint_y=None, height=dp(52),
                     color=C["ink"], font_size=dp(12), halign="center")
        content.add_widget(info)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        share = Button(text="Compartir", background_color=C["green"], color=C["white"])
        share.bind(on_release=lambda *_: self._share(path))
        close = Button(text="Cerrar", background_color=C["dark2"], color=C["white"])
        row.add_widget(share)
        row.add_widget(close)
        content.add_widget(row)
        popup = Popup(title="Flyer generado", content=content, size_hint=(0.95, 0.9))
        close.bind(on_release=popup.dismiss)
        popup.open()

    @mainthread
    def _show_error(self, msg):
        popup = Popup(title="Error",
                      content=Label(text=msg, color=C["white"]),
                      size_hint=(0.8, 0.4))
        popup.open()

    def _share(self, path):
        """Comparte la imagen usando un Intent de Android (no-op en escritorio)."""
        try:
            from jnius import autoclass, cast  # type: ignore
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            File = autoclass("java.io.File")
            FileProvider = autoclass("androidx.core.content.FileProvider")
            activity = PythonActivity.mActivity
            f = File(path)
            authority = activity.getPackageName() + ".fileprovider"
            uri = FileProvider.getUriForFile(activity, authority, f)
            intent = Intent(Intent.ACTION_SEND)
            intent.setType("image/png")
            intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            activity.startActivity(Intent.createChooser(intent, cast("java.lang.CharSequence", "Compartir flyer")))
        except Exception as e:
            print("Compartir no disponible en esta plataforma:", e)

    # ---- persistencia de configuración ---- #
    def _save_config(self, data):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("No se pudo guardar config:", e)

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return
        self.sp_op.text = cfg.get("tipo_operacion", "VENTA")
        self.sp_prop.text = cfg.get("tipo_propiedad", "Casa")
        self.f_titulo.value = cfg.get("titulo", "")
        self.f_sub.value = cfg.get("subtitulo", "")
        self.f_precio.value = cfg.get("precio", "")
        self.f_marca.value = cfg.get("marca", "")
        self.f_tel1.value = cfg.get("telefono1", "")
        self.f_tel2.value = cfg.get("telefono2", "")
        self.f_colonia.value = cfg.get("colonia", "")
        self.f_direccion.value = cfg.get("direccion", "")
        self.f_nota.value = cfg.get("nota", "")
        self.f_qr.value = cfg.get("qr_link", "")


class FlyerApp(App):
    def build(self):
        self.title = "Generador de Flyers Inmobiliarios"
        Window.clearcolor = C["bg"]
        request_android_permissions()
        return FlyerRoot()


if __name__ == "__main__":
    FlyerApp().run()
