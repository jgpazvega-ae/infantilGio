"""
Generación de metadata de YouTube (título, descripción, tags, categoría...).

Produce títulos naturales (no spam) y descripciones completas usando la
identidad del canal definida en config/channels.yaml.
"""

import re


# Sufijos naturales según el género/tipo de contenido.
_TITLE_SUFFIX = {
    "bedtime": "Cuento para Dormir 🌙",
    "sleep": "Sonido Relajante para Dormir 🌊",
    "ambient": "Sonido Ambiental Relajante 🎵",
    "adventure": "Cuento Infantil ✨",
    "animals": "Cuento de Animales 🐾",
    "trains": "Cuento del Tren 🚂",
    "nature": "Sonidos de la Naturaleza 🌿",
}


def _keywords(texto, limite=15):
    """Extrae palabras frecuentes (>3 letras) como base para tags."""
    palabras = re.findall(r"[a-záéíóúñ]{4,}", (texto or "").lower())
    stop = {
        "para", "como", "pero", "porque", "cuando", "donde", "entre", "sobre",
        "todo", "todos", "esta", "este", "esto", "muy", "más", "sus", "una",
        "unos", "unas", "los", "las", "del", "con", "que", "por", "había",
        "hacía", "hasta", "desde", "cada", "también", "eran", "estaba",
    }
    frecuencia = {}
    for p in palabras:
        if p in stop:
            continue
        frecuencia[p] = frecuencia.get(p, 0) + 1
    ordenadas = sorted(frecuencia, key=frecuencia.get, reverse=True)
    return ordenadas[:limite]


def build_metadata(content_type, title, channel, story_meta=None,
                   duration_seconds=None, extra_tags=None):
    """
    Construye la metadata de YouTube. Devuelve un dict con:
    title, description, tags, category, language, age_recommendation.
    """
    story_meta = story_meta or {}
    channel = channel or {}
    genre = story_meta.get("genre", content_type)

    # --- Título natural ---
    suffix = _TITLE_SUFFIX.get(genre) or _TITLE_SUFFIX.get(content_type, "")
    if suffix and suffix.lower() not in title.lower():
        full_title = f"{title} | {suffix}"
    else:
        full_title = title
    full_title = full_title[:100]  # límite de YouTube

    # --- Descripción ---
    edad = story_meta.get("age_range", "2-5")
    partes = []
    resumen = story_meta.get("summary")
    if not resumen and story_meta.get("story"):
        primera = re.split(r"(?<=[.!?…])\s+", story_meta["story"].strip())
        resumen = " ".join(primera[:2])[:300]
    if resumen:
        partes.append(resumen)

    partes.append(f"Edad recomendada: {edad} años.")
    tema = story_meta.get("theme")
    if tema:
        partes.append(f"Tema: {tema}.")
    if duration_seconds:
        mins = int(round(duration_seconds / 60))
        partes.append(f"Duración: aproximadamente {mins} minutos.")

    signature = channel.get("signature", "").strip()
    if signature:
        partes.append(signature)

    hashtags = channel.get("default_hashtags", [])
    if hashtags:
        partes.append(" ".join(hashtags))

    description = "\n\n".join(partes).strip()

    # --- Tags ---
    tags = list(extra_tags or [])
    tags += _keywords(story_meta.get("story", "") + " " + title)
    for base in (genre, content_type, "cuentos infantiles", "para dormir"):
        if base and base not in tags:
            tags.append(base)
    # Únicos, respetando orden, máximo 30 (límite razonable YouTube).
    vistos, tags_final = set(), []
    for t in tags:
        if t and t not in vistos:
            vistos.add(t)
            tags_final.append(t)
    tags_final = tags_final[:30]

    return {
        "title": full_title,
        "description": description,
        "tags": tags_final,
        "category": channel.get("category", "education"),
        "language": story_meta.get("language", channel.get("language", "es-MX")),
        "age_recommendation": edad,
        "made_for_kids": channel.get("made_for_kids", True),
        "privacy": channel.get("default_privacy", "private"),
    }
