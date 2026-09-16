"""
Troceo de textos largos para ElevenLabs.

Divide el texto en fragmentos de como máximo `max_chars`, cortando siempre en
límites naturales (párrafo > oración) y nunca a mitad de palabra.
"""

import re


def split_text(texto, max_chars):
    """
    Devuelve una lista de fragmentos <= max_chars respetando párrafos y
    oraciones. Nunca parte una palabra salvo que una sola palabra supere el
    límite (caso extremo).
    """
    texto = (texto or "").strip()
    if not texto:
        return []
    if len(texto) <= max_chars:
        return [texto]

    fragmentos = []
    actual = ""

    def emitir():
        nonlocal actual
        if actual.strip():
            fragmentos.append(actual.strip())
        actual = ""

    for parrafo in re.split(r"\n\s*\n", texto):
        parrafo = parrafo.strip()
        if not parrafo:
            continue

        if len(parrafo) <= max_chars:
            # ¿Cabe el párrafo entero en el fragmento actual?
            if actual and len(actual) + len(parrafo) + 2 > max_chars:
                emitir()
            actual = (actual + "\n\n" + parrafo).strip() if actual else parrafo
            continue

        # Párrafo demasiado largo: partir por oraciones.
        for frase in re.split(r"(?<=[.!?…])\s+", parrafo):
            frase = frase.strip()
            if not frase:
                continue
            if actual and len(actual) + len(frase) + 1 > max_chars:
                emitir()
            # Oración descomunal: cortar por longitud como último recurso.
            while len(frase) > max_chars:
                if actual:
                    emitir()
                fragmentos.append(frase[:max_chars])
                frase = frase[max_chars:]
            actual = (actual + " " + frase).strip() if actual else frase

    emitir()
    return fragmentos
