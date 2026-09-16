"""
Utilidades de FFmpeg y de duración.

Python solo orquesta: el trabajo pesado lo hace ffmpeg vía subprocess con
listas de argumentos (nunca shell=True, para evitar inyección de comandos).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    """Error al ejecutar ffmpeg/ffprobe."""


def check_ffmpeg():
    """
    Verifica que ffmpeg y ffprobe estén en el PATH. Lanza FFmpegError con
    instrucciones de instalación si falta alguno.
    """
    faltan = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if faltan:
        raise FFmpegError(
            "FFmpeg no está instalado o no está disponible en PATH "
            f"(falta: {', '.join(faltan)}).\n"
            "Instalación:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Windows: choco install ffmpeg  (o https://ffmpeg.org/download.html)\n"
            "  Linux:   sudo apt install ffmpeg\n"
        )


def parse_duration(value):
    """
    Convierte una duración a segundos (float). Acepta:
      - "HH:MM:SS" o "MM:SS"      -> 05:55:00
      - "1h", "90m", "30s"        -> sufijos h/m/s
      - número (segundos)         -> 21300 o "21300"
    """
    if value is None:
        raise ValueError("Duración vacía.")
    if isinstance(value, (int, float)):
        return float(value)

    texto = str(value).strip().lower()
    if not texto:
        raise ValueError("Duración vacía.")

    # Formato HH:MM:SS / MM:SS
    if ":" in texto:
        partes = texto.split(":")
        if not all(p.isdigit() for p in partes):
            raise ValueError(f"Duración inválida: {value!r}")
        partes = [int(p) for p in partes]
        while len(partes) < 3:
            partes.insert(0, 0)
        h, m, s = partes[-3], partes[-2], partes[-1]
        return float(h * 3600 + m * 60 + s)

    # Sufijos h/m/s
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([hms])", texto)
    if m:
        num = float(m.group(1))
        factor = {"h": 3600, "m": 60, "s": 1}[m.group(2)]
        return num * factor

    # Número plano (segundos)
    try:
        return float(texto)
    except ValueError as exc:
        raise ValueError(f"Duración inválida: {value!r}") from exc


def format_duration(segundos):
    """Formatea segundos como 'HH:MM:SS'."""
    segundos = int(round(float(segundos)))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration_compact(segundos):
    """Formatea segundos como '5h55m00s' (útil en nombres de archivo)."""
    segundos = int(round(float(segundos)))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def probe(path):
    """Devuelve el JSON completo de ffprobe (format + streams) como dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise FFmpegError(f"ffprobe falló en {path}: {res.stderr.strip()}")
    return json.loads(res.stdout or "{}")


def get_duration(path):
    """Duración en segundos (float) de un archivo de audio/video."""
    info = probe(path)
    dur = info.get("format", {}).get("duration")
    if dur is None:
        raise FFmpegError(f"No se pudo determinar la duración de {path}")
    return float(dur)


def get_stream(path, codec_type):
    """Devuelve el primer stream del tipo dado ('video'|'audio') o None."""
    for s in probe(path).get("streams", []):
        if s.get("codec_type") == codec_type:
            return s
    return None


def run_ffmpeg(args, logger=None):
    """
    Ejecuta ffmpeg con la lista de argumentos `args` (sin el binario inicial).
    Añade -y y silencia el banner. Lanza FFmpegError con el stderr si falla.
    """
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *[str(a) for a in args]]
    if logger:
        logger.info("ffmpeg %s", " ".join(str(a) for a in args))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise FFmpegError("ffmpeg falló:\n" + (res.stderr or "(sin salida)"))
    return res.returncode
