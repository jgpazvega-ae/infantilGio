"""
Utilidades de sistema: espacio en disco y estimación de tamaño de salida.
"""

import shutil
from pathlib import Path


def disk_free_bytes(path):
    """Bytes libres en el sistema de archivos que contiene `path`."""
    path = Path(path)
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free


def estimate_video_size_bytes(duration_seconds, video_kbps=1500, audio_kbps=192):
    """
    Estima el tamaño (bytes) de un MP4 de `duration_seconds` a los bitrates
    dados. Para video oscuro y de poco movimiento el bitrate real suele ser
    mucho menor, así que esta estimación es conservadora (sobreestima).
    """
    total_kbps = video_kbps + audio_kbps
    return int(total_kbps * 1000 / 8 * duration_seconds)


def human_size(num_bytes):
    """Formatea bytes en una cadena legible (KB/MB/GB)."""
    num = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def check_disk_space(target_path, needed_bytes, margin=1.2):
    """
    Comprueba si hay espacio suficiente (con un margen). Devuelve
    (ok, free_bytes, needed_with_margin). No lanza; el llamador decide.
    """
    free = disk_free_bytes(target_path)
    needed = int(needed_bytes * margin)
    return free >= needed, free, needed
