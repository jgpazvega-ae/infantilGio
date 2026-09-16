"""
Fase 5 — Generación de miniaturas para YouTube.

Toma un frame representativo de un video (o una imagen fija indicada), le
superpone el título del cuento con una tipografía legible, y exporta una
miniatura de 1280x720 en thumbnails/.

Uso:
    # A partir de un frame del video final (segundo 30 por defecto):
    python scripts/generate_thumbnail.py --video output/mi_cuento.mp4 \
        --titulo "El Barquito Dormilón"

    # A partir de una imagen fija:
    python scripts/generate_thumbnail.py --imagen footage/portada.jpg \
        --titulo "El Barquito Dormilón" --salida mi_cuento
"""

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scripts.utils import check_ffmpeg, run_ffmpeg  # noqa: E402


def _extraer_frame(video, segundo):
    """Extrae un frame del video en el segundo indicado a un PNG temporal."""
    check_ffmpeg()
    tmp = Path(tempfile.mkstemp(suffix=".png")[1])
    run_ffmpeg([
        "-ss", str(segundo),
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "2",
        str(tmp),
    ])
    return tmp


def _cargar_fuente(tamano):
    """Carga la fuente configurada; si no existe, usa la de Pillow por defecto."""
    from PIL import ImageFont

    if config.THUMB_FONT_PATH.exists():
        return ImageFont.truetype(str(config.THUMB_FONT_PATH), tamano)
    try:
        # Intenta una fuente común del sistema como respaldo legible.
        return ImageFont.truetype("DejaVuSans-Bold.ttf", tamano)
    except OSError:
        print("Aviso: usando la fuente por defecto de Pillow (tamaño fijo).")
        return ImageFont.load_default()


def _ajustar_texto(draw, texto, fuente, ancho_max):
    """Divide el título en varias líneas para que quepa en el ancho dado."""
    palabras = texto.split()
    lineas = []
    actual = ""
    for palabra in palabras:
        prueba = (actual + " " + palabra).strip()
        ancho = draw.textbbox((0, 0), prueba, font=fuente)[2]
        if ancho <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def generar_thumbnail(titulo, video=None, imagen=None, segundo=30, salida=None):
    """
    Genera la miniatura. Requiere `titulo` y una fuente de imagen (video o
    imagen fija). Devuelve la ruta del PNG generado.
    """
    from PIL import Image, ImageDraw, ImageFilter

    if not video and not imagen:
        raise ValueError("Indica --video o --imagen como fuente de la miniatura.")

    config.ensure_dirs()

    frame_temporal = None
    try:
        if imagen:
            ruta_img = Path(imagen)
            if not ruta_img.exists():
                raise FileNotFoundError(f"No existe la imagen: {ruta_img}")
        else:
            ruta_video = Path(video)
            if not ruta_video.exists():
                raise FileNotFoundError(f"No existe el video: {ruta_video}")
            frame_temporal = _extraer_frame(ruta_video, segundo)
            ruta_img = frame_temporal

        # 1. Redimensionar/recortar la imagen a 1280x720
        base = Image.open(ruta_img).convert("RGB")
        base = _cubrir(base, config.THUMB_WIDTH, config.THUMB_HEIGHT)

        # 2. Oscurecer ligeramente la parte inferior para que el texto resalte
        overlay = Image.new("RGB", base.size, (0, 0, 0))
        mascara = Image.new("L", base.size, 0)
        md = ImageDraw.Draw(mascara)
        md.rectangle(
            [0, int(config.THUMB_HEIGHT * 0.45), config.THUMB_WIDTH, config.THUMB_HEIGHT],
            fill=120,
        )
        mascara = mascara.filter(ImageFilter.GaussianBlur(60))
        base = Image.composite(overlay, base, mascara)

        # 3. Dibujar el título centrado en la mitad inferior
        draw = ImageDraw.Draw(base)
        fuente = _cargar_fuente(config.THUMB_FONT_SIZE)
        margen = 100
        lineas = _ajustar_texto(draw, titulo, fuente, config.THUMB_WIDTH - margen * 2)

        alto_linea = draw.textbbox((0, 0), "Ay", font=fuente)[3] + 18
        alto_total = alto_linea * len(lineas)
        y = config.THUMB_HEIGHT - alto_total - 70

        for linea in lineas:
            ancho = draw.textbbox((0, 0), linea, font=fuente)[2]
            x = (config.THUMB_WIDTH - ancho) // 2
            draw.text(
                (x, y),
                linea,
                font=fuente,
                fill=config.THUMB_TEXT_COLOR,
                stroke_width=config.THUMB_STROKE_WIDTH,
                stroke_fill=config.THUMB_STROKE_COLOR,
            )
            y += alto_linea

        # 4. Guardar
        nombre = salida or (Path(video).stem if video else Path(imagen).stem)
        destino = config.THUMBNAILS_DIR / f"{nombre}.png"
        base.save(destino, "PNG")
        print(f"OK: miniatura guardada en {destino}")
        return destino
    finally:
        if frame_temporal is not None and frame_temporal.exists():
            frame_temporal.unlink()


def _cubrir(img, ancho, alto):
    """Redimensiona y recorta (estilo 'cover') para llenar ancho x alto."""
    ratio_destino = ancho / alto
    ratio_img = img.width / img.height
    if ratio_img > ratio_destino:
        nuevo_alto = alto
        nuevo_ancho = int(alto * ratio_img)
    else:
        nuevo_ancho = ancho
        nuevo_alto = int(ancho / ratio_img)
    img = img.resize((nuevo_ancho, nuevo_alto))
    izq = (nuevo_ancho - ancho) // 2
    arr = (nuevo_alto - alto) // 2
    return img.crop((izq, arr, izq + ancho, arr + alto))


def main():
    parser = argparse.ArgumentParser(description="Genera una miniatura 1280x720.")
    parser.add_argument("--titulo", required=True, help="Título a superponer")
    parser.add_argument("--video", default=None, help="Video del que extraer un frame")
    parser.add_argument("--imagen", default=None, help="Imagen fija a usar como fondo")
    parser.add_argument("--segundo", type=int, default=30, help="Segundo del frame (con --video)")
    parser.add_argument("--salida", default=None, help="Nombre base del archivo de salida")
    args = parser.parse_args()

    try:
        generar_thumbnail(
            args.titulo,
            video=args.video,
            imagen=args.imagen,
            segundo=args.segundo,
            salida=args.salida,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
