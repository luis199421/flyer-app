"""
flyer_render.py — Motor de generación de flyers inmobiliarios (Pillow puro).

Reconstruido a partir del .exe original (flyer_todo_en_uno, Python 3.14 + tkinter).
Esta parte NO depende de tkinter, así que funciona igual en escritorio y en Android
(Pillow se compila con buildozer). La interfaz (Kivy) vive en main.py.

API principal:
    generate_flyer(data: dict, output_path: str) -> str

`data` es un diccionario con las claves que llena el formulario (ver DATA_KEYS).
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --------------------------------------------------------------------------- #
#  Constantes de lienzo y paleta (idénticas al original)
# --------------------------------------------------------------------------- #
FLYER_W, FLYER_H = 1080, 1440

_AMBER      = (245, 166, 35)
_AMBER_D    = (212, 137, 26)
_DARK       = (26, 26, 46)
_DARK2      = (45, 45, 68)
_WHITE      = (255, 255, 255)
_LIGHT_BG   = (247, 245, 240)
_INK        = (61, 61, 61)
_MUTED      = (136, 136, 136)
_GREEN      = (37, 211, 102)
_SUN_ORANGE = (244, 107, 43)

# Claves que entiende generate_flyer (para referencia del formulario)
DATA_KEYS = (
    "foto_principal", "logo_path", "logo2_path",
    "tipo_operacion", "tipo_propiedad", "titulo", "subtitulo",
    "precio", "fotos_adicionales", "caracteristicas", "nota",
    "qr_link", "telefono1", "telefono2", "colonia", "direccion", "marca",
)

# Catálogos que usaba el formulario original
TIPOS_OP = ["VENTA", "RENTA", "VENTA Y RENTA"]
OP_EMO = {"VENTA": "🔑", "RENTA": "🗓", "VENTA Y RENTA": "🔑🗓"}
TIPOS_PROP = ["Casa", "Departamento", "Terreno", "Local", "Bodega", "Rancho", "Oficina"]
PROP_EMO = {
    "Casa": "🏠", "Departamento": "🏢", "Terreno": "🌍", "Local": "🏪",
    "Bodega": "📦", "Rancho": "🌾", "Oficina": "💼",
}
CARACT_DEF = [
    ("Recámaras", "3"), ("Baños", "2"), ("Medios Baños", "1"),
    ("M² Construcción", "120 m²"), ("M² Terreno", "180 m²"),
    ("Cochera", "1 auto"), ("Piso", "1er piso"), ("Cocina", "Equipada"),
]


# --------------------------------------------------------------------------- #
#  Utilidades de fuentes y texto
# --------------------------------------------------------------------------- #
def _try_font(size, bold=False):
    """Carga una fuente TTF probando rutas comunes de cada SO; cae en la default."""
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/system/fonts/Roboto-Bold.ttf",                 # Android
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/system/fonts/Roboto-Regular.ttf",              # Android
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in (candidates_bold if bold else candidates_reg):
        try:
            if not Path(path).exists():
                continue
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_w(draw, text, font):
    """Ancho en píxeles de un texto."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    except Exception:
        return 0


def _text_h(draw, text, font):
    """Altura en píxeles de un texto."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]
    except Exception:
        return 0


def _shrink_to_fit(text, start_size, bold, max_w, draw, min_size=13):
    """Reduce el tamaño de fuente hasta que el texto entre en max_w px."""
    size = start_size
    while size >= min_size:
        f = _try_font(size, bold)
        if _text_w(draw, text, f) <= max_w:
            return (f, size)
        size -= 2
    return (_try_font(min_size, bold), min_size)


def _wrap_lines(draw, text, font, max_w):
    """Divide el texto en líneas que quepan en max_w px."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if _text_w(draw, test, font) <= max_w:
            current = test
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines if lines else [text]


def _draw_wrapped(draw, x, y, text, font, fill, max_w, line_gap=1.2):
    """Dibuja texto con wrapping automático. Devuelve la y final."""
    lines = _wrap_lines(draw, text, font, max_w)
    lh = int(_text_h(draw, "Ag", font) * line_gap)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += lh
    return y


def _truncate_fit(draw, text, font, max_w, ellipsis="…"):
    """Trunca con '…' si el texto supera max_w px."""
    if _text_w(draw, text, font) <= max_w:
        return text
    while len(text) > 1:
        text = text[:-1]
        if _text_w(draw, text + ellipsis, font) <= max_w:
            return text + ellipsis
    return ellipsis


def _draw_rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _format_precio(raw):
    """Formatea números con comas: '1250000' -> '$1,250,000'.

    Respeta prefijo $ y sufijo MXN/USD etc. No toca lo que ya tiene comas.
    """
    import re
    if not raw:
        return raw
    if "," in raw:
        return raw
    match = re.search(r"(\d{4,}(?:\.\d+)?)", raw.replace(",", ""))
    if not match:
        return raw
    num_str = match.group(1)
    try:
        if "." in num_str:
            integer, dec = num_str.split(".", 1)
            formatted = f"{int(integer):,}.{dec}"
        else:
            formatted = f"{int(num_str):,}"
        return raw[:match.start()] + formatted + raw[match.end():]
    except Exception:
        return raw


def _make_qr(url, size):
    """Genera un QR (PIL Image) del url. Devuelve None si qrcode no está instalado."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4, border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=_DARK, back_color=_WHITE).convert("RGB")
        return qr_img.resize((size, size), Image.LANCZOS)
    except Exception:
        return None


def _paste_image(canvas, img_path, box, radius=0, enhance=True):
    """Pega una imagen recortada/escalada a `box` (x0,y0,x1,y1), con esquinas
    redondeadas opcionales. Devuelve True si tuvo éxito."""
    try:
        img = Image.open(img_path).convert("RGB")
        bw = box[2] - box[0]
        bh = box[3] - box[1]
        if bw <= 0 or bh <= 0:
            return False
        iw, ih = img.size
        scale = max(bw / iw, bh / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        ox = (nw - bw) // 2
        oy = (nh - bh) // 2
        img = img.crop((ox, oy, ox + bw, oy + bh))
        if enhance:
            img = ImageEnhance.Contrast(img).enhance(1.05)
        img = ImageEnhance.Color(img).enhance(1.1)
        if radius > 0:
            mask = Image.new("L", (bw, bh), 0)
            md = ImageDraw.Draw(mask)
            md.rounded_rectangle((0, 0, bw, bh), radius=radius, fill=255)
            img.putalpha(mask)
            canvas.paste(img, (box[0], box[1]), img)
        else:
            canvas.paste(img, (box[0], box[1]))
        return True
    except Exception:
        return False


def _darken(hex_c, amt):
    """Oscurece un color hex '#rrggbb' restando `amt` a cada canal."""
    hex_c = hex_c.lstrip("#")
    r, g, b = (int(hex_c[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(max(0, r - amt), max(0, g - amt), max(0, b - amt))


# --------------------------------------------------------------------------- #
#  Generación del flyer completo
# --------------------------------------------------------------------------- #
def generate_flyer(data, output_path):
    """Renderiza el flyer 1080x1440 a partir de `data` y lo guarda como PNG."""
    img = Image.new("RGB", (FLYER_W, FLYER_H), _LIGHT_BG)
    draw = ImageDraw.Draw(img)

    FOTO_H = 660
    FOOTER_H = 260
    CONTENT_TOP = FOTO_H + 14
    CONTENT_BOT = FLYER_H - FOOTER_H - 8

    # ---- Foto principal (o degradado de respaldo) ----
    foto_ok = _paste_image(img, data.get("foto_principal", ""), (0, 0, FLYER_W, FOTO_H))
    if not foto_ok:
        for y in range(FOTO_H):
            t = y / FOTO_H
            r = int(_DARK[0] * (1 - t) + _DARK2[0] * t)
            g = int(_DARK[1] * (1 - t) + _DARK2[1] * t)
            b = int(_DARK[2] * (1 - t) + _DARK2[2] * t)
            draw.line([(0, y), (FLYER_W, y)], fill=(r, g, b))

    # Degradado inferior para legibilidad del título
    grad_h = 300
    for y in range(grad_h):
        alpha = int(210 * (y / grad_h))
        overlay = Image.new("RGBA", (FLYER_W, 1), (20, 20, 40, alpha))
        img.paste(overlay.convert("RGB"), (0, (FOTO_H - grad_h) + y), overlay.split()[3])

    BORDER_W = 14
    draw.rectangle((0, 0, FLYER_W - 1, FOTO_H - 1), outline=_SUN_ORANGE, width=BORDER_W)

    # ---- Logos (arriba a la derecha, hasta 2) ----
    logo_path = data.get("logo_path", "")
    logo2_path = data.get("logo2_path", "")
    LOGO_SIZE = 96
    LOGO_PAD = 14
    logo_right = FLYER_W - LOGO_PAD
    logo_left_x = FLYER_W

    if logo_path and Path(logo_path).exists():
        lx = logo_right - LOGO_SIZE
        _paste_image(img, logo_path, (lx, LOGO_PAD, lx + LOGO_SIZE, LOGO_PAD + LOGO_SIZE),
                     radius=12, enhance=False)
        logo_right = lx - LOGO_PAD
        logo_left_x = lx

    if logo2_path and Path(logo2_path).exists():
        lx2 = logo_right - LOGO_SIZE
        _paste_image(img, logo2_path, (lx2, LOGO_PAD, lx2 + LOGO_SIZE, LOGO_PAD + LOGO_SIZE),
                     radius=12, enhance=False)
        logo_left_x = lx2

    # ---- Precio pequeño bajo los logos ----
    precio_early = _format_precio(data.get("precio", ""))
    if precio_early and logo_left_x < FLYER_W:
        logos_right_x = FLYER_W - LOGO_PAD
        logos_span_w = logos_right_x - logo_left_x
        psmall_size = max(16, int(LOGO_SIZE * 0.2))
        f_psmall, _ = _shrink_to_fit(precio_early, psmall_size, True, logos_span_w, draw, min_size=13)
        pw = _text_w(draw, precio_early, f_psmall)
        px_ = logos_right_x - pw
        py_ = LOGO_PAD + LOGO_SIZE + 6
        draw.text((px_ + 1, py_ + 1), precio_early, font=f_psmall, fill=(0, 0, 0))
        draw.text((px_, py_), precio_early, font=f_psmall, fill=_WHITE)

    # ---- Badge de operación (VENTA / RENTA) ----
    op = data.get("tipo_operacion", "VENTA").upper()
    badge_colors = {
        "VENTA Y RENTA": (100, 180, 255),
        "RENTA": _GREEN,
        "VENTA": _AMBER,
    }
    b_color = badge_colors.get(op, _AMBER)
    badge_text = op
    f_badge = _try_font(30, bold=True)
    bw = _text_w(draw, badge_text, f_badge) + 24
    bh = 52
    by, bx = 36, 40
    _draw_rounded_rect(draw, (bx, by, bx + bw, by + bh), radius=26, fill=b_color)
    draw.text((bx + 12, by + 10), _truncate_fit(draw, badge_text, f_badge, bw - 24),
              font=f_badge, fill=_DARK)

    # ---- Chip de tipo de propiedad ----
    tipo_prop = data.get("tipo_propiedad", "Propiedad")
    CHIP_MAX_W = FLYER_W - 90
    f_chip, _ = _shrink_to_fit(f"  {tipo_prop}  ", 22, False, CHIP_MAX_W, draw, min_size=13)
    chip_text = _truncate_fit(draw, f"  {tipo_prop}  ", f_chip, CHIP_MAX_W)
    cw2 = min(_text_w(draw, chip_text, f_chip) + 20, CHIP_MAX_W)
    chip_y0 = by + bh + 12
    _draw_rounded_rect(draw, (40, chip_y0, 40 + cw2, chip_y0 + 40), radius=20, fill=(20, 20, 40))
    draw.text((52, chip_y0 + 10), chip_text, font=f_chip, fill=_WHITE)

    # ---- Título y subtítulo (sobre la foto) ----
    titulo = data.get("titulo", "")
    sub = data.get("subtitulo", "")
    MAX_TEXT_W = FLYER_W - 80
    CHIP_BOTTOM = chip_y0 + 40 + 20

    f_title, _ = _shrink_to_fit("X", 58, True, MAX_TEXT_W, draw, min_size=26)
    f_sub = _try_font(26)
    title_lines = _wrap_lines(draw, titulo, f_title, MAX_TEXT_W) if titulo else []
    lh_title = int(_text_h(draw, "Ag", f_title) * 1.15)
    sub_lines = _wrap_lines(draw, sub, f_sub, MAX_TEXT_W) if sub else []
    lh_sub = int(_text_h(draw, "Ag", f_sub) * 1.2)
    total_block = len(title_lines) * lh_title + (len(sub_lines) * lh_sub + 8 if sub else 0)
    ty = FOTO_H - total_block - 28
    ty = max(ty, CHIP_BOTTOM)

    if titulo:
        cy = ty
        for line in title_lines:
            if cy + lh_title > FOTO_H:
                break
            draw.text((42, cy + 3), line, font=f_title, fill=(0, 0, 0))
            draw.text((40, cy), line, font=f_title, fill=_WHITE)
            cy += lh_title
        ty_after_title = cy + 6
    else:
        ty_after_title = ty

    if sub:
        cy = ty_after_title
        for line in sub_lines:
            if cy + lh_sub > FOTO_H:
                break
            draw.text((40, cy), line, font=f_sub, fill=(235, 235, 235))
            cy += lh_sub

    # ---- Cuerpo: fotos adicionales ----
    cursor = CONTENT_TOP
    precio = _format_precio(data.get("precio", ""))

    adicionales = data.get("fotos_adicionales", [])
    adicionales_validas = [p for p in adicionales if p and Path(p).exists()]

    if adicionales_validas:
        COLS_FOTO = 3
        padding = 10
        thumb_h = 200
        thumb_w = (FLYER_W - padding * (COLS_FOTO + 1)) // COLS_FOTO
        n_real = min(len(adicionales_validas), 3)
        group_w = n_real * thumb_w + (n_real - 1) * padding
        start_x = (FLYER_W - group_w) // 2
        thumb_bot = cursor + thumb_h
        if thumb_bot <= CONTENT_BOT:
            for i, path in enumerate(adicionales_validas[:3]):
                tx = start_x + i * (thumb_w + padding)
                _paste_image(img, path, (tx, cursor, tx + thumb_w, cursor + thumb_h), radius=12)
            cursor = thumb_bot + 14

    # ---- Cuerpo: precio destacado + rejilla de características ----
    caract = data.get("caracteristicas", [])
    items_draw = list(caract[:8])
    rows_used = 0
    if items_draw or precio:
        f_clabel = _try_font(19)
        f_cvalue = _try_font(24, bold=True)
        cols = 4
        cell_w = (FLYER_W - 40) // cols
        cell_h = 80
        cell_inner = cell_w - 24
        x0 = 20
        cy_base = cursor

        if precio:
            label_str = {
                "VENTA Y RENTA": "PRECIO",
                "RENTA": "PRECIO DE RENTA",
                "VENTA": "PRECIO DE VENTA",
            }.get(op, "PRECIO")
            pcell_w = cell_w * cols + 8
            pcell_h = cell_h
            if cy_base + pcell_h <= CONTENT_BOT:
                f_pval, _ = _shrink_to_fit(precio, 38, True, pcell_w - 200, draw, min_size=20)
                f_plbl = _try_font(17)
                _draw_rounded_rect(draw, (x0, cy_base, x0 + pcell_w, cy_base + pcell_h),
                                   radius=10, fill=(255, 248, 220), outline=_AMBER, width=2)
                draw.rectangle((x0 + 8, cy_base, x0 + pcell_w - 8, cy_base + 4), fill=_AMBER)
                lbl_fit = _truncate_fit(draw, label_str, f_plbl, pcell_w // 2 - 20)
                draw.text((x0 + 12, cy_base + 12), lbl_fit, font=f_plbl, fill=_MUTED)
                pval_w = _text_w(draw, precio, f_pval)
                pval_x = x0 + pcell_w - pval_w - 20
                pval_y = cy_base + (pcell_h - _text_h(draw, precio, f_pval)) // 2
                draw.text((pval_x, pval_y), precio, font=f_pval, fill=_AMBER_D)
            cy_base += pcell_h + 8

        for i, item in enumerate(items_draw):
            col = i % cols
            row = i // cols
            cx = x0 + col * cell_w
            cy = cy_base + row * (cell_h + 8)
            if cy + cell_h > CONTENT_BOT:
                break
            _draw_rounded_rect(draw, (cx, cy, cx + cell_w - 8, cy + cell_h),
                               radius=10, fill=_WHITE, outline=(230, 225, 218), width=1)
            draw.rectangle((cx + 8, cy, cx + cell_w - 16, cy + 4), fill=_AMBER)
            lbl_txt = _truncate_fit(draw, item.get("label", ""), f_clabel, cell_inner)
            val_txt = _truncate_fit(draw, item.get("valor", ""), f_cvalue, cell_inner)
            draw.text((cx + 10, cy + 10), lbl_txt, font=f_clabel, fill=_MUTED)
            draw.text((cx + 10, cy + 38), val_txt, font=f_cvalue, fill=_INK)

        rows_used = (len(items_draw) + cols - 1) // cols if items_draw else 0
        cursor = cy_base + rows_used * (cell_h + 8) + 6

    # ---- Nota opcional ----
    nota = data.get("nota", "")
    if nota:
        nota_y = cursor + 10
        if nota_y < CONTENT_BOT:
            f_nota = _try_font(21)
            nota_lh = int(_text_h(draw, "Ag", f_nota) * 1.25)
            nota_lines = _wrap_lines(draw, nota, f_nota, FLYER_W - 80)
            nota_needed = len(nota_lines) * nota_lh
            if nota_y + nota_needed > CONTENT_BOT:
                avail_h = max(nota_lh, CONTENT_BOT - nota_y)
                max_lines = max(1, avail_h // nota_lh)
                nota_lines = nota_lines[:max_lines]
            x_nota = 40
            for line in nota_lines:
                if nota_y + nota_lh > CONTENT_BOT:
                    break
                draw.text((x_nota, nota_y), line, font=f_nota, fill=_MUTED)
                nota_y += nota_lh

    # ---- Separador + footer ----
    sep_y = FLYER_H - FOOTER_H - 6
    draw.rectangle((40, sep_y, FLYER_W - 40, sep_y + 2), fill=_AMBER)
    footer_y = FLYER_H - FOOTER_H
    draw.rectangle((0, footer_y, FLYER_W, FLYER_H), fill=_DARK)

    QR_SIZE = 160
    QR_PAD = 18
    qr_link = data.get("qr_link", "").strip()
    RIGHT_COL_W = QR_SIZE + QR_PAD * 2
    LEFT_MAX_W = FLYER_W - RIGHT_COL_W - 40 - 10

    if qr_link:
        qr_img = _make_qr(qr_link, QR_SIZE)
        if qr_img:
            f_qrlbl = _try_font(15)
            lbl = "Escanea aqui"
            lbl_h = _text_h(draw, lbl, f_qrlbl)
            lbl_gap = 6
            total_qr_h = lbl_h + lbl_gap + QR_SIZE
            qr_col_x = FLYER_W - RIGHT_COL_W
            qr_x = qr_col_x + (RIGHT_COL_W - QR_SIZE) // 2
            qr_y = footer_y + (FOOTER_H - total_qr_h) // 2
            qr_bg = Image.new("RGB", (QR_SIZE + 6, QR_SIZE + 6), _WHITE)
            img.paste(qr_bg, (qr_x - 3, qr_y + lbl_h + lbl_gap - 3))
            img.paste(qr_img, (qr_x, qr_y + lbl_h + lbl_gap))
            lbl_x = qr_x + (QR_SIZE - _text_w(draw, lbl, f_qrlbl)) // 2
            draw.text((lbl_x, qr_y), lbl, font=f_qrlbl, fill=_AMBER)

    # ---- Footer: marca + contacto ----
    f_tel = _try_font(32, bold=True)
    f_dir = _try_font(22)
    f_mrca = _try_font(34, bold=True)
    contact_x = 40
    ty3 = footer_y + 14

    tel1 = data.get("telefono1", "")
    tel2 = data.get("telefono2", "")
    colonia = data.get("colonia", "")
    direccion = data.get("direccion", "")
    marca = data.get("marca", "")

    if marca:
        marca_fit = _truncate_fit(draw, marca, f_mrca, LEFT_MAX_W)
        draw.text((contact_x, ty3), marca_fit, font=f_mrca, fill=_AMBER)
    ty3 += _text_h(draw, "A", f_mrca) + 8

    if tel1:
        t1 = _truncate_fit(draw, f"TEL  {tel1}", f_tel, LEFT_MAX_W)
        draw.text((contact_x, ty3), t1, font=f_tel, fill=_WHITE)
    ty3 += 46

    if tel2:
        t2 = _truncate_fit(draw, f"WA   {tel2}", f_tel, LEFT_MAX_W)
        draw.text((contact_x, ty3), t2, font=f_tel, fill=_GREEN)
    ty3 += 46

    if colonia:
        col_txt = _truncate_fit(draw, f"DIR  {colonia}", f_dir, LEFT_MAX_W)
        draw.text((contact_x, ty3), col_txt, font=f_dir, fill=_MUTED)
    ty3 += 30

    if direccion:
        dir_txt = _truncate_fit(draw, direccion, f_dir, LEFT_MAX_W)
        if ty3 + _text_h(draw, "A", f_dir) <= FLYER_H - 8:
            draw.text((contact_x, ty3), dir_txt, font=f_dir, fill=_MUTED)

    img.save(output_path, "PNG", dpi=(300, 300))
    return output_path


if __name__ == "__main__":
    # Prueba rápida del motor (sin interfaz)
    demo = {
        "tipo_operacion": "VENTA",
        "tipo_propiedad": "Casa",
        "titulo": "Hermosa casa en venta con jardín amplio",
        "subtitulo": "Excelente ubicación, lista para habitar",
        "precio": "$3,450,000 MXN",
        "caracteristicas": [
            {"label": "Recámaras", "valor": "3"},
            {"label": "Baños", "valor": "2"},
            {"label": "M² Const.", "valor": "180 m²"},
            {"label": "Cochera", "valor": "2 autos"},
        ],
        "nota": "Aceptamos crédito Infonavit, Fovissste y bancario.",
        "telefono1": "555-123-4567",
        "telefono2": "555-765-4321",
        "colonia": "Col. Del Valle",
        "direccion": "Av. Principal #123, CDMX",
        "marca": "Luis Studio Inmobiliaria",
        "qr_link": "https://ejemplo.com/propiedad/123",
    }
    out = generate_flyer(demo, "demo_flyer.png")
    print("Flyer generado:", out)
