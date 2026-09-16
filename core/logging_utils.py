"""
Logging profesional para el pipeline.

Cada proceso obtiene un logger que escribe a consola y a un archivo diario en
logs/. Los mensajes incluyen fecha, proceso, nivel y detalle.
"""

import logging
import sys
from datetime import datetime

import config

_CONFIGURED = set()


def get_logger(process_name):
    """
    Devuelve un logger para `process_name` que escribe a consola y a
    logs/<fecha>.log. Idempotente: no duplica handlers.
    """
    logger = logging.getLogger(f"infantilgio.{process_name}")
    if process_name in _CONFIGURED:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Consola
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Archivo diario (best-effort: si no se puede escribir, seguimos con consola)
    try:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        archivo = config.LOGS_DIR / f"{datetime.now():%Y-%m-%d}.log"
        fh = logging.FileHandler(archivo, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass

    _CONFIGURED.add(process_name)
    return logger
