"""
Motor de loop de audio.

Genera audio en bucle de una duración exacta a partir de un clip base,
usando crossfade para evitar clicks/cortes audibles en el empalme. La
duración final coincide con la solicitada (ffmpeg -t recorta con precisión).
"""

from pathlib import Path

from core.ffmpeg_utils import get_duration, run_ffmpeg


def _codec_args(dst):
    """Codec sin pérdida para .wav/.flac; mp3 para el resto (evita apilar
    generaciones de MP3 en los intermedios)."""
    ext = Path(dst).suffix.lower()
    if ext == ".wav":
        return ["-c:a", "pcm_s16le"]
    if ext == ".flac":
        return ["-c:a", "flac"]
    return ["-c:a", "libmp3lame", "-q:a", "2"]


def build_audio_filter(source_sample_rate=None, clean=True):
    """
    Construye la cadena de filtros de audio adecuada a la calidad del origen.

    - Fuente de baja calidad (sample_rate <= 22050, típico de grabaciones
      muffled/comprimidas): repara clipping (adeclip), reduce artefactos
      (afftdn), recorta el techo brillante/artefactado justo por debajo de
      Nyquist, añade algo de cuerpo y normaliza el volumen. Rescata lo audible
      sin inventar agudos que el archivo no tiene.
    - Fuente de buena calidad: cadena mínima (loudnorm) para no degradar.

    loudnorm va al final con TP=-1.5 dB para dejar headroom y evitar clipping.
    """
    if not clean:
        return "loudnorm=I=-16:TP=-1.5:LRA=11"

    baja = source_sample_rate is not None and source_sample_rate <= 22050
    if baja:
        # Techo ~ 92% de Nyquist del origen para tapar el brickwall/artefactos.
        techo = int(min(7600, (source_sample_rate / 2) * 0.92))
        return (
            f"adeclip,afftdn=nf=-20,highpass=f=45,lowpass=f={techo},"
            f"bass=g=2.5:f=110,loudnorm=I=-16:TP=-1.5:LRA=11"
        )
    return "adeclip,highpass=f=25,loudnorm=I=-16:TP=-1.5:LRA=11"


def build_ocean_filter(cfg):
    """
    Construye la cadena de limpieza "ocean" a partir de la config
    (presets.audio_cleanup.ocean): de-click, notch de tonos/silbidos que no son
    mar, HPF/LPF, realce de cuerpo y espuma de las olas, normalización de
    volumen y limitador. Resalta el mar y elimina lo que no lo es.
    """
    cfg = cfg or {}
    partes = []
    # Recorte de la parte inicial/final que no es mar (tonos, golpes, etc.).
    ts = cfg.get("trim_start", 0) or 0
    te = cfg.get("trim_end", 0) or 0
    if ts or te:
        trim = f"atrim=start={ts}"
        if te:
            trim += f":end={te}"
        partes.append(trim)
        partes.append("asetpts=N/SR/TB")
    if cfg.get("declick", True):
        partes.append("adeclick")
    if cfg.get("highpass_hz"):
        partes.append(f"highpass=f={cfg['highpass_hz']}")
    for i, hz in enumerate(cfg.get("notches_hz", []) or []):
        # Notch profundo y estrecho para el tono, un poco más ancho el primero.
        w = 320 if i == 0 else 180
        g = -32 if i == 0 else -16
        partes.append(f"equalizer=f={hz}:width_type=h:width={w}:g={g}")
    if cfg.get("denoise", 0):
        partes.append(f"afftdn=nr={cfg['denoise']}:nf=-40")
    if cfg.get("lowpass_hz"):
        partes.append(f"lowpass=f={cfg['lowpass_hz']}")
    if cfg.get("body_gain_db"):
        partes.append(f"equalizer=f=260:width_type=o:width=1.2:g={cfg['body_gain_db']}")
    if cfg.get("air_gain_db"):
        partes.append(f"equalizer=f=4200:width_type=o:width=1.6:g={cfg['air_gain_db']}")
    partes.append(f"loudnorm=I={cfg.get('loudnorm_i', -15)}:TP=-1.5:LRA=11")
    partes.append("alimiter=limit=0.891")  # techo ~ -1 dBFS
    return ",".join(partes)


def normalize_audio(src, dst, af=None, source_sample_rate=None, clean=True,
                    sample_rate=44100, channels=2, logger=None):
    """
    Limpia y normaliza el audio (ver build_audio_filter) y estandariza sample
    rate/canales, sin destruir la dinámica natural. No modifica el original.
    Escribe en formato sin pérdida si `dst` es .wav/.flac. Devuelve dst.
    """
    src, dst = Path(src), Path(dst)
    if af is None:
        af = build_audio_filter(source_sample_rate, clean=clean)
    run_ffmpeg([
        "-i", src, "-af", af,
        "-ar", str(sample_rate), "-ac", str(channels),
        *_codec_args(dst), dst,
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
        *_codec_args(dst), dst,
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
