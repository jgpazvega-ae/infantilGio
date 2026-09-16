"""
generate_thumbnail.py — Miniaturas 1280x720 (Fase 6).

Toma un frame de un video o una imagen fija, superpone el título con
tipografía legible y buen contraste, y exporta a thumbnails/<slug>.jpg.
El estilo se configura en config/styles.yaml.

Uso:
    python scripts/generate_thumbnail.py --video video/final/andre.mp4 --titulo "André y el Tren"
    python scripts/generate_thumbnail.py --imagen assets/images/portada.jpg --titulo "..." --salida andre
"""

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.ffmpeg_utils import check_ffmpeg, run_ffmpeg  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.paths import slugify  # noqa: E402

log = get_logger("generate_thumbnail")


def _extract_frame(video, segundo):
    check_ffmpeg()
    tmp = Path(tempfile.mkstemp(suffix=".png")[1])
    run_ffmpeg(["-ss", str(segundo), "-i", str(video), "-frames:v", "1", "-q:v", "2", tmp],
               logger=log)
    return tmp


def _load_font(size):
    from PIL import ImageFont
    style = config.thumbnail_style()
    font_file = config.BASE_DIR / style.get("font_file", "assets/fonts/title.ttf")
    if Path(font_file).exists():
        return ImageFont.truetype(str(font_file), size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, texto, font, max_w):
    palabras, lineas, actual = texto.split(), [], ""
    for w in palabras:
        prueba = (actual + " " + w).strip()
        if draw.textbbox((0, 0), prueba, font=font)[2] <= max_w or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = w
    if actual:
        lineas.append(actual)
    return lineas


def _cover(img, w, h):
    rd, ri = w / h, img.width / img.height
    if ri > rd:
        nh, nw = h, int(h * ri)
    else:
        nw, nh = w, int(w / ri)
    img = img.resize((nw, nh))
    x, y = (nw - w) // 2, (nh - h) // 2
    return img.crop((x, y, x + w, y + h))


def generate_thumbnail(titulo, video=None, imagen=None, segundo=None, salida=None,
                       force=False, dry_run=False):
    from PIL import Image, ImageDraw, ImageFilter
    if not video and not imagen:
        raise ValueError("Indica --video o --imagen.")
    config.ensure_dirs()
    style = config.thumbnail_style()
    W, H = style.get("width", 1280), style.get("height", 720)

    nombre = salida or slugify(titulo)
    destino = config.THUMBNAILS_DIR / f"{nombre}.jpg"
    if dry_run:
        log.info("[dry-run] miniatura '%s' -> %s", titulo, destino)
        return destino
    if destino.exists() and not force:
        log.info("Ya existe: %s (usa --force)", destino)
        return destino

    frame_tmp = None
    try:
        if imagen:
            src = Path(imagen)
            if not src.exists():
                src = config.IMAGES_DIR / Path(imagen).name
            if not src.exists():
                raise FileNotFoundError(f"No existe la imagen: {imagen}")
        else:
            v = Path(video)
            if not v.exists():
                raise FileNotFoundError(f"No existe el video: {video}")
            frame_tmp = _extract_frame(v, segundo if segundo is not None else 5)
            src = frame_tmp

        base = _cover(Image.open(src).convert("RGB"), W, H)

        if style.get("darken_bottom", True):
            overlay = Image.new("RGB", base.size, (0, 0, 0))
            mask = Image.new("L", base.size, 0)
            ImageDraw.Draw(mask).rectangle([0, int(H * 0.45), W, H], fill=130)
            mask = mask.filter(ImageFilter.GaussianBlur(60))
            base = Image.composite(overlay, base, mask)

        draw = ImageDraw.Draw(base)
        font = _load_font(style.get("font_size", 90))
        lineas = _wrap(draw, titulo, font, W - 200)
        alto = draw.textbbox((0, 0), "Ay", font=font)[3] + 18
        y = H - alto * len(lineas) - 70
        for ln in lineas:
            ancho = draw.textbbox((0, 0), ln, font=font)[2]
            draw.text(((W - ancho) // 2, y), ln, font=font,
                      fill=tuple(style.get("text_color", [255, 255, 255])),
                      stroke_width=style.get("stroke_width", 6),
                      stroke_fill=tuple(style.get("stroke_color", [0, 0, 0])))
            y += alto

        base.save(destino, "JPEG", quality=90)
        log.info("OK miniatura -> %s", destino)
        return destino
    finally:
        if frame_tmp and frame_tmp.exists():
            frame_tmp.unlink()


def main():
    ap = argparse.ArgumentParser(description="Genera una miniatura 1280x720.")
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--video", default=None)
    ap.add_argument("--imagen", default=None)
    ap.add_argument("--segundo", type=int, default=None)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        generate_thumbnail(args.titulo, video=args.video, imagen=args.imagen,
                           segundo=args.segundo, salida=args.salida,
                           force=args.force, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
