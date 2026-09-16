"""
Motor de loop de audio.

Genera audio en bucle de una duración exacta a partir de un clip base,
usando crossfade para evitar clicks/cortes audibles en el empalme. La
duración final coincide con la solicitada (ffmpeg -t recorta con precisión).
"""

from pathlib import Path

from core.ffmpeg_utils import get_duration, run_ffmpeg


def normalize_audio(src, dst, sample_rate=44100, channels=2, logger=None):
    """
    Normaliza el volumen (EBU R128 loudnorm) y estandariza sample rate/canales,
    sin destruir la dinámica natural del sonido (loudnorm de una pasada). No
    modifica el archivo original. Devuelve dst.
    """
    src, dst = Path(src), Path(dst)
    run_ffmpeg([
        "-i", src,
        "-af", "loudnorm=I=-18:TP=-1.5:LRA=11",
        "-ar", str(sample_rate), "-ac", str(channels),
        "-c:a", "libmp3lame", "-q:a", "2", dst,
    ], logger=logger)
    return dst


def build_seamless_audio(src, dst, crossfade, logger=None):
    """
    Crea una versión "loopeable" del audio: funde (acrossfade) el final con el
    inicio para que, al repetirse, el empalme sea suave. Devuelve dst.
    """
    src, dst = Path(src), Path(dst)
    dur = get_duration(src)
    offset = dur - crossfade
    filtro = (
        f"[0:a]asplit=3[a][b][c];"
        f"[a]atrim=end={offset},asetpts=PTS-STARTPTS[main];"
        f"[b]atrim=start={offset},asetpts=PTS-STARTPTS[tail];"
        f"[c]atrim=end={crossfade},asetpts=PTS-STARTPTS[head];"
        f"[tail][head]acrossfade=d={crossfade}[xf];"
        f"[main][xf]concat=n=2:v=0:a=1[a]"
    )
    run_ffmpeg([
        "-i", src, "-filter_complex", filtro, "-map", "[a]",
        "-c:a", "libmp3lame", "-q:a", "2", dst,
    ], logger=logger)
    return dst


def build_audio_loop(src, dst, target_seconds, crossfade=2, fade_out=2,
                     logger=None, cache_dir=None):
    """
    Genera en `dst` un audio en bucle de exactamente `target_seconds`.

    - Si el clip es más largo que 2x crossfade, primero crea una versión
      loopeable con acrossfade (empalme suave) y la repite.
    - Aplica un breve fundido de salida para evitar un click al cortar.
    Devuelve la ruta dst.
    """
    src, dst = Path(src), Path(dst)
    dur = get_duration(src)

    fuente = src
    if crossfade and dur > crossfade * 2:
        cache_dir = Path(cache_dir) if cache_dir else dst.parent
        cache_dir.mkdir(parents=True, exist_ok=True)
        seamless = cache_dir / f"{src.stem}_seamless.mp3"
        if not seamless.exists():
            build_seamless_audio(src, seamless, crossfade, logger=logger)
        fuente = seamless

    args = ["-stream_loop", "-1", "-i", fuente, "-t", f"{target_seconds}"]
    # Fundido de salida en los últimos `fade_out` segundos.
    if fade_out and target_seconds > fade_out:
        args += ["-af", f"afade=t=out:st={target_seconds - fade_out}:d={fade_out}"]
    args += ["-c:a", "libmp3lame", "-q:a", "2", dst]
    run_ffmpeg(args, logger=logger)
    return dst
