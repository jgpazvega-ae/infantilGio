"""
Fase 4 — Ensamblado del video final.

Combina:
  - Audio de narración (audio/narration/) al 100% de volumen.
  - Un clip de footage, repetido automáticamente para cubrir la duración de
    la narración.
  - (Opcional) Audio ambiental de fondo a bajo volumen (15-20%).

Exporta un mp4 1920x1080 a output/ con el mismo nombre base que el cuento.

Uso:
    # Cuento narrado sobre el mar, con ambiente por defecto (audio del mar):
    python scripts/assemble_video.py mi_cuento --footage footage/mar.mp4

    # Sin ambiente de fondo:
    python scripts/assemble_video.py mi_cuento --footage footage/mar.mp4 --no-ambient

    # Con un ambiente concreto:
    python scripts/assemble_video.py mi_cuento --footage footage/mar.mp4 \
        --ambient audio/ambient/ambient_mar.mp3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scripts.utils import (  # noqa: E402
    check_ffmpeg,
    format_duration,
    get_media_duration,
    run_ffmpeg,
)


def _resolver(ruta, carpeta, sufijo=None):
    """Resuelve una ruta aceptando ruta completa o solo el nombre base."""
    ruta = Path(ruta)
    if ruta.exists():
        return ruta
    candidato = carpeta / ruta.name
    if sufijo and candidato.suffix == "":
        candidato = candidato.with_suffix(sufijo)
    if candidato.exists():
        return candidato
    raise FileNotFoundError(f"No se encontró: {ruta} (ni en {carpeta})")


def ensamblar(nombre, footage, ambient=None, usar_ambient=True):
    """
    Ensambla el video final de un cuento.

    Parámetros:
      nombre   -> nombre base del cuento (busca audio/narration/<nombre>.mp3)
      footage  -> ruta o nombre del clip de fondo
      ambient  -> ruta del audio ambiental (por defecto, el del mar)
      usar_ambient -> si es False, no mezcla ambiente

    Devuelve la ruta del mp4 final.
    """
    check_ffmpeg()
    config.ensure_dirs()

    # 1. Localizar la narración
    narracion = _resolver(
        Path(nombre).with_suffix(".mp3") if Path(nombre).suffix == "" else nombre,
        config.NARRATION_DIR,
        ".mp3",
    )
    dur = get_media_duration(narracion)
    print(f"Narración: {narracion.name} ({format_duration(dur)})")

    # 2. Localizar el footage
    footage = _resolver(footage, config.FOOTAGE_DIR, ".mp4")
    print(f"Footage: {footage.name}")

    # 3. Localizar ambiente (opcional)
    ruta_ambient = None
    if usar_ambient:
        origen = ambient or config.DEFAULT_AMBIENT_FILE
        try:
            ruta_ambient = _resolver(origen, config.AMBIENT_DIR, ".mp3")
            print(f"Ambiente: {ruta_ambient.name} (volumen {config.AMBIENT_VOLUME})")
        except FileNotFoundError:
            print("Aviso: no se encontró audio ambiental; se omite el fondo.")
            ruta_ambient = None

    salida = config.OUTPUT_DIR / (narracion.stem + ".mp4")

    # 4. Construir el comando de ffmpeg
    entradas = [
        "-stream_loop", "-1", "-i", str(footage),   # entrada 0: video (loop)
        "-i", str(narracion),                        # entrada 1: narración
    ]
    if ruta_ambient is not None:
        entradas += ["-stream_loop", "-1", "-i", str(ruta_ambient)]  # entrada 2

    escala = (
        f"[0:v]scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},"
        f"fps={config.VIDEO_FPS}[v]"
    )

    if ruta_ambient is not None:
        filtro = (
            f"{escala};"
            f"[1:a]volume={config.NARRATION_VOLUME}[narr];"
            f"[2:a]volume={config.AMBIENT_VOLUME}[amb];"
            f"[narr][amb]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )
    else:
        filtro = f"{escala};[1:a]volume={config.NARRATION_VOLUME}[a]"

    run_ffmpeg([
        *entradas,
        "-filter_complex", filtro,
        "-map", "[v]",
        "-map", "[a]",
        "-t", str(dur),          # recorta todo a la duración de la narración
        "-c:v", "libx264",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(salida),
    ])

    print(f"OK: video final guardado en {salida}")
    return salida


def main():
    parser = argparse.ArgumentParser(
        description="Ensambla narración + footage + ambiente en un mp4 final."
    )
    parser.add_argument("nombre", help="Nombre base del cuento (narración en audio/narration/)")
    parser.add_argument("--footage", required=True, help="Clip de fondo (ruta o nombre en footage/)")
    parser.add_argument("--ambient", default=None, help="Audio ambiental (por defecto: el del mar)")
    parser.add_argument("--no-ambient", action="store_true", help="No mezclar audio ambiental")
    args = parser.parse_args()

    try:
        ensamblar(
            args.nombre,
            footage=args.footage,
            ambient=args.ambient,
            usar_ambient=not args.no_ambient,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
