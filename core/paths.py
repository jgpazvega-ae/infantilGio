"""Ayudas de rutas y slugs para producciones."""

import re
import unicodedata


def slugify(texto):
    """
    Convierte un título en un slug seguro para nombres de archivo/carpeta:
    minúsculas, sin acentos, separado por guiones.
    """
    texto = str(texto).strip().lower()
    # Quita acentos
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    # Reemplaza cualquier cosa no alfanumérica por guion
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    texto = texto.strip("-")
    return texto or "sin-titulo"
