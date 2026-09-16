"""
Producto 1 — Video "loop para dormir" completo (video + sonido ambiental).

Combina un clip de footage y un audio ambiental (por defecto, el audio del
mar incluido en audio/ambient/ambient_mar.mp3), repitiendo AMBOS hasta cubrir
una duración total (por defecto 5 h 55 min), y exporta un mp4 1920x1080 en
output/loops/.

A diferencia de assemble_video.py (que sirve para cuentos narrados), aquí no
hay narración: es solo paisaje + ambiente, ideal para dormir.

Uso:
    # 5 h 55 min con el ambiente por defecto (mar):
    python scripts/make_sleep_loop.py --footage footage/mar.mp4

    # Duración e ambiente personalizados:
    python scripts/make_sleep_loop.py --footage footage/mar.mp4 \
        --ambient audio/ambient/ambient_mar.mp3 --hours 3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from scripts.utils import (  # noqa: E402
    check_ffmpeg,
    format_duration,
    run_ffmpeg,
)


def _resolver(ruta, carpeta, sufijo):
    ruta = Path(ruta)
    if ruta.exists():
        return ruta
    candidato = carpeta / ruta.name
    if candidato.suffix == "":
        candidato = candidato.with_suffix(sufijo)
    if candidato.exists():
        return candidato
    raise FileNotFoundError(f"No se encontró: {ruta} (ni en {carpeta})")


def make_sleep_loop(footage, ambient=None, segundos=None, volumen_ambiente=None):
    """
    Genera el video de dormir. Devuelve la ruta del mp4 resultante.

    footage           -> clip de video base (se repite)
    ambient           -> audio ambiental (se repite); por defecto, el del mar
    segundos          -> duración total (por defecto, 5h55m = 21300 s)
    volumen_ambiente  -> volumen del ambiente (por defecto 1.0, es el único audio)
    """
    check_ffmpeg()
    config.ensure_dirs()

    footage = _resolver(footage, config.FOOTAGE_DIR, ".mp4")
    ruta_ambient = _resolver(
        ambient or config.DEFAULT_AMBIENT_FILE, config.AMBIENT_DIR, ".mp3"
    )
    segundos = segundos or config.DEFAULT_LOOP_SECONDS
    # En un loop para dormir el ambiente es el audio principal, así que va al
    # 100% salvo que se indique otra cosa.
    volumen = 1.0 if volumen_ambiente is None else volumen_ambiente

    print(
        f"Footage: {footage.name} | Ambiente: {ruta_ambient.name} | "
        f"Duración: {format_duration(segundos)}"
    )

    salida = config.LOOPS_DIR / f"{footage.stem}_dormir_{format_duration(segundos)}.mp4"

    run_ffmpeg([
        "-stream_loop", "-1", "-i", str(footage),      # video en loop
        "-stream_loop", "-1", "-i", str(ruta_ambient), # ambiente en loop
        "-filter_complex",
        (
            f"[0:v]scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},"
            f"fps={config.VIDEO_FPS}[v];"
            f"[1:a]volume={volumen}[a]"
        ),
        "-map", "[v]",
        "-map", "[a]",
        "-t", str(segundos),
        "-c:v", "libx264",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(salida),
    ])

    print(f"OK: loop para dormir guardado en {salida}")
    return salida


def main():
    parser = argparse.ArgumentParser(
        description="Genera un video 'loop para dormir' (video + ambiente)."
    )
    parser.add_argument("--footage", required=True, help="Clip de fondo (ruta o nombre en footage/)")
    parser.add_argument("--ambient", default=None, help="Audio ambiental (por defecto: el del mar)")
    parser.add_argument("--hours", type=int, default=0, help="Horas objetivo")
    parser.add_argument("--minutes", type=int, default=0, help="Minutos objetivo")
    parser.add_argument("--seconds", type=int, default=0, help="Segundos objetivo")
    parser.add_argument("--volumen", type=float, default=None, help="Volumen del ambiente (0-1)")
    args = parser.parse_args()

    total = args.hours * 3600 + args.minutes * 60 + args.seconds
    total = total or None

    try:
        make_sleep_loop(
            args.footage,
            ambient=args.ambient,
            segundos=total,
            volumen_ambiente=args.volumen,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
