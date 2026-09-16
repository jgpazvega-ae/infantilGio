"""
Fase 3 — Loop de footage para videos largos de dormir.

Toma un clip corto de footage/ (por ejemplo, 10-15 min del mar) y lo repite
hasta cubrir una duración total deseada, generando un mp4 1920x1080 a 30 fps
en output/loops/.

Estrategia:
  - Por defecto usa -stream_loop (repetición limpia, rápida y sin recodificar
    innecesariamente el contenido interno). Es ideal si el clip ya empieza y
    termina de forma parecida.
  - Con --xfade aplica una transición de crossfade entre el final y el inicio
    del clip para crear un "loop perfecto" antes de repetirlo. Es más lento
    porque requiere recodificar.

Uso:
    python scripts/loop_footage.py footage/mar.mp4 --hours 5 --minutes 55
    python scripts/loop_footage.py footage/mar.mp4 --seconds 21300 --xfade
    python scripts/loop_footage.py footage/mar.mp4          # usa duración por defecto
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


def _crear_clip_loopeable(entrada, salida, xfade_seg):
    """
    Crea una versión "loopeable" del clip aplicando un crossfade entre su
    final y su inicio, de modo que al repetirlo la transición sea suave.
    """
    dur = get_media_duration(entrada)
    if dur <= xfade_seg * 2:
        raise ValueError(
            f"El clip ({format_duration(dur)}) es demasiado corto para un "
            f"crossfade de {xfade_seg}s."
        )
    offset = dur - xfade_seg
    # Divide el video en tres copias (split=3): el cuerpo principal, la cola
    # (últimos xfade_seg segundos) y la cabeza (primeros xfade_seg segundos).
    # La cola se funde (xfade) sobre la cabeza para que, al repetir el clip
    # resultante, el final enlace suavemente con el inicio.
    # Nota: xfade exige frame rate constante, por lo que normalizamos con
    # fps/format antes de dividir y en cada rama que entra al crossfade.
    fps = config.VIDEO_FPS
    filtro = (
        f"[0:v]fps={fps},format=yuv420p,split=3[a][b][c];"
        f"[a]trim=end={offset},setpts=PTS-STARTPTS[main];"
        f"[b]trim=start={offset},setpts=PTS-STARTPTS,fps={fps}[tail];"
        f"[c]trim=end={xfade_seg},setpts=PTS-STARTPTS,fps={fps}[head];"
        f"[tail][head]xfade=transition=fade:duration={xfade_seg}:offset=0[xf];"
        f"[main][xf]concat=n=2:v=1:a=0[v]"
    )
    run_ffmpeg([
        "-i", str(entrada),
        "-filter_complex", filtro,
        "-map", "[v]",
        "-an",  # el audio del loop se añade en el ensamblado final
        "-c:v", "libx264",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-r", str(config.VIDEO_FPS),
        str(salida),
    ])


def loop_footage(entrada, segundos=None, usar_xfade=False):
    """
    Genera un loop del clip `entrada` de duración total `segundos`.
    Devuelve la ruta del mp4 resultante.
    """
    check_ffmpeg()

    entrada = Path(entrada)
    if not entrada.exists():
        candidato = config.FOOTAGE_DIR / entrada.name
        if candidato.exists():
            entrada = candidato
        else:
            raise FileNotFoundError(
                f"No se encontró el clip de footage: {entrada}"
            )

    segundos = segundos or config.DEFAULT_LOOP_SECONDS
    config.ensure_dirs()

    dur_clip = get_media_duration(entrada)
    print(
        f"Clip base: {entrada.name} ({format_duration(dur_clip)}) | "
        f"objetivo: {format_duration(segundos)}"
    )

    fuente = entrada
    temporal = None
    try:
        if usar_xfade:
            temporal = config.LOOPS_DIR / (entrada.stem + "_loopeable.mp4")
            print("Creando clip loopeable con crossfade...")
            _crear_clip_loopeable(entrada, temporal, config.LOOP_XFADE_SECONDS)
            fuente = temporal

        salida = config.LOOPS_DIR / f"{entrada.stem}_{format_duration(segundos)}.mp4"
        print("Repitiendo el clip hasta la duración objetivo...")
        # -stream_loop -1 repite indefinidamente; -t recorta a la duración.
        run_ffmpeg([
            "-stream_loop", "-1",
            "-i", str(fuente),
            "-t", str(segundos),
            "-c:v", "libx264",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-r", str(config.VIDEO_FPS),
            "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}",
            "-an",
            str(salida),
        ])
    finally:
        # Limpia el clip loopeable intermedio si se creó.
        if temporal is not None and temporal.exists():
            temporal.unlink()

    print(f"OK: loop guardado en {salida}")
    return salida


def main():
    parser = argparse.ArgumentParser(
        description="Convierte un clip corto en un loop de larga duración."
    )
    parser.add_argument("clip", help="Ruta al clip (o nombre dentro de footage/)")
    parser.add_argument("--hours", type=int, default=0, help="Horas objetivo")
    parser.add_argument("--minutes", type=int, default=0, help="Minutos objetivo")
    parser.add_argument(
        "--seconds",
        type=int,
        default=0,
        help="Segundos objetivo (se suman a horas/minutos si se combinan)",
    )
    parser.add_argument(
        "--xfade",
        action="store_true",
        help="Aplica crossfade para un loop perfecto (más lento)",
    )
    args = parser.parse_args()

    total = args.hours * 3600 + args.minutes * 60 + args.seconds
    total = total or None  # None -> usa el valor por defecto de config

    try:
        loop_footage(args.clip, segundos=total, usar_xfade=args.xfade)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
