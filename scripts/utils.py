"""
Utilidades compartidas por los scripts del pipeline.

Incluye comprobaciones de dependencias (ffmpeg), ayudas para localizar
ffmpeg/ffprobe y funciones de formato. Mantener aquí la lógica común evita
duplicar el manejo de errores en cada script.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def check_ffmpeg():
    """
    Verifica que ffmpeg y ffprobe estén instalados en el sistema.

    Termina el programa con un mensaje claro si falta alguno, indicando
    cómo instalarlo según el sistema operativo.
    """
    faltan = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if faltan:
        print(
            "ERROR: no se encontró(n) "
            + ", ".join(faltan)
            + " en el sistema.\n\n"
            "ffmpeg es necesario para procesar audio y video. Instálalo:\n"
            "  - Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg\n"
            "  - macOS (Homebrew): brew install ffmpeg\n"
            "  - Windows (Chocolatey): choco install ffmpeg\n"
            "  - O descárgalo desde https://ffmpeg.org/download.html\n",
            file=sys.stderr,
        )
        sys.exit(1)


def get_media_duration(path):
    """
    Devuelve la duración (en segundos, float) de un archivo de audio o video
    usando ffprobe. Lanza RuntimeError si no se puede leer.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        salida = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        ).stdout.strip()
        return float(salida)
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise RuntimeError(
            f"No se pudo obtener la duración de {path}: {exc}"
        ) from exc


def format_duration(segundos):
    """Formatea una duración en segundos como 'HhMMmSSs' para logs legibles."""
    segundos = int(round(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    return f"{horas}h{minutos:02d}m{segs:02d}s"


def run_ffmpeg(cmd):
    """
    Ejecuta un comando de ffmpeg (lista de argumentos, sin el binario inicial).

    Muestra el comando, lo ejecuta y, si falla, imprime el error de ffmpeg y
    lanza una excepción. Devuelve el código de salida (0 si todo fue bien).
    """
    comando = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *cmd]
    print("  $ ffmpeg " + " ".join(str(a) for a in cmd))
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(
            "ffmpeg falló:\n" + (resultado.stderr or "(sin salida de error)")
        )
    return resultado.returncode
