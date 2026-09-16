"""
Motor de loop de video.

Estrategia eficiente para duraciones muy largas (p. ej. 5 h 55 min):
solo se re-codifica UNA vez un clip base corto (normalizado al formato de
salida y, opcionalmente, con crossfade para un loop perfecto). El video largo
se produce repitiendo ese clip con stream-copy (sin recodificar horas de
video), y el audio se mezcla/recodifica aparte. Python solo orquesta.
"""

from pathlib import Path

from core.ffmpeg_utils import get_duration, run_ffmpeg


def normalize_clip(src, dst, width, height, fps, preset="medium",
                   gop_seconds=2, crossfade=0, logger=None):
    """
    Re-codifica el clip base al formato de salida (WxH, fps, h264) con un GOP
    corto (keyframes frecuentes) para que el recorte por stream-copy quede
    ajustado. Si `crossfade` > 0, aplica un loop perfecto con xfade.
    Devuelve dst.
    """
    src, dst = Path(src), Path(dst)
    scale = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )
    gop = max(1, int(round(fps * gop_seconds)))

    if crossfade and get_duration(src) > crossfade * 2:
        dur = get_duration(src)
        offset = dur - crossfade
        # xfade exige frame rate constante: normalizamos antes de dividir.
        filtro = (
            f"[0:v]{scale},split=3[a][b][c];"
            f"[a]trim=end={offset},setpts=PTS-STARTPTS[main];"
            f"[b]trim=start={offset},setpts=PTS-STARTPTS,fps={fps}[tail];"
            f"[c]trim=end={crossfade},setpts=PTS-STARTPTS,fps={fps}[head];"
            f"[tail][head]xfade=transition=fade:duration={crossfade}:offset=0[xf];"
            f"[main][xf]concat=n=2:v=1:a=0[v]"
        )
        args = ["-i", src, "-filter_complex", filtro, "-map", "[v]"]
    else:
        args = ["-i", src, "-vf", scale]

    args += [
        "-an", "-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p",
        "-r", str(fps), "-g", str(gop), "-keyint_min", str(gop), dst,
    ]
    run_ffmpeg(args, logger=logger)
    return dst


def build_video_loop(src, dst, target_seconds, width, height, fps,
                     preset="medium", crossfade=0, logger=None, cache_dir=None):
    """
    Genera un video SILENCIOSO en bucle de `target_seconds` a partir de `src`.
    Normaliza el clip una vez y luego repite con stream-copy (eficiente).
    Devuelve dst. (El recorte por copy queda alineado al keyframe: tolerancia
    <= gop_seconds; el audio exacto se añade en el muxeo final.)
    """
    src, dst = Path(src), Path(dst)
    cache_dir = Path(cache_dir) if cache_dir else dst.parent
    cache_dir.mkdir(parents=True, exist_ok=True)

    norm = cache_dir / f"{src.stem}_norm_{width}x{height}_{fps}.mp4"
    if not norm.exists():
        normalize_clip(src, norm, width, height, fps, preset=preset,
                       crossfade=crossfade, logger=logger)

    run_ffmpeg([
        "-stream_loop", "-1", "-i", norm, "-t", f"{target_seconds}",
        "-c:v", "copy", dst,
    ], logger=logger)
    return dst


def build_sleep_video(video_src, audio_src, dst, target_seconds, width, height,
                      fps, preset="medium", crossfade=0, audio_volume=1.0,
                      logger=None, cache_dir=None):
    """
    Produce el video de dormir (video en loop + audio en loop) de duración
    `target_seconds`, de forma eficiente: el clip base se normaliza una sola
    vez y el resultado largo se genera con video stream-copy + audio AAC.
    Devuelve dst.
    """
    video_src, audio_src, dst = Path(video_src), Path(audio_src), Path(dst)
    cache_dir = Path(cache_dir) if cache_dir else dst.parent
    cache_dir.mkdir(parents=True, exist_ok=True)

    norm = cache_dir / f"{video_src.stem}_norm_{width}x{height}_{fps}.mp4"
    if not norm.exists():
        normalize_clip(video_src, norm, width, height, fps, preset=preset,
                       crossfade=crossfade, logger=logger)

    run_ffmpeg([
        "-stream_loop", "-1", "-i", norm,        # entrada 0: video (loop)
        "-stream_loop", "-1", "-i", audio_src,   # entrada 1: audio (loop)
        "-filter_complex", f"[1:a]volume={audio_volume}[a]",
        "-map", "0:v", "-map", "[a]",
        "-t", f"{target_seconds}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", dst,
    ], logger=logger)
    return dst
