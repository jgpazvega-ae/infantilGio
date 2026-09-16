"""
Motor de cuentos (story engine).

Un cuento se define por su texto + metadata estructurada. Esta metadata puede
venir de un front-matter YAML al inicio del archivo o inferirse del texto.

La generación automática de texto a partir de una idea idealmente usa un LLM;
como el proyecto no está acoplado a ningún proveedor de LLM, se ofrece un
generador por plantilla determinista (real y probable, sin placeholders) para
prototipar. Enchufar un LLM es una mejora futura a través de esta interfaz.
"""

import re

import yaml

# Categorías soportadas por la arquitectura.
CATEGORIES = [
    "sleep", "adventure", "animals", "vehicles", "trains", "dinosaurs",
    "nature", "friendship", "emotions", "learning", "bedtime",
]

DEFAULT_METADATA = {
    "title": "",
    "language": "es-MX",
    "age_range": "2-5",
    "genre": "bedtime",
    "theme": "friendship",
    "target_duration_minutes": 8,
    "characters": [],
    "story": "",
    "visual_style": "soft_storybook",
    "youtube": {},
}

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_story_file(path):
    """
    Lee un archivo de cuento y devuelve un dict de metadata + 'story' (texto).
    Soporta front-matter YAML opcional:

        ---
        title: André y el Tren de las Estrellas
        genre: adventure
        ---
        Había una vez...

    Si no hay front-matter, el título se toma de la primera línea.
    """
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el cuento: {path}")

    raw = path.read_text(encoding="utf-8").strip()
    meta = dict(DEFAULT_METADATA)

    m = _FRONT_MATTER_RE.match(raw)
    if m:
        front = yaml.safe_load(m.group(1)) or {}
        meta.update({k: v for k, v in front.items() if v is not None})
        body = m.group(2).strip()
    else:
        body = raw

    meta["story"] = body

    if not meta.get("title"):
        # Primera línea no vacía como título.
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        meta["title"] = first[:120] or path.stem.replace("_", " ").title()

    return meta


def estimate_duration_minutes(texto, wpm=130):
    """
    Estima la duración de la narración en minutos a partir del número de
    palabras (ritmo de lectura pausada ~130 ppm para narración infantil).
    """
    palabras = len(re.findall(r"\w+", texto or ""))
    return round(palabras / wpm, 1) if palabras else 0.0


def generate_story_from_params(title, character="Andrés", theme="amistad",
                               setting="el bosque de los sueños", paragraphs=5):
    """
    Generador por plantilla (determinista) que produce un cuento infantil
    coherente y suave para dormir. No usa LLM; sirve para prototipar y probar
    el pipeline de extremo a extremo. Devuelve metadata + texto.
    """
    intro = (
        f"Había una vez, en {setting}, un pequeño personaje llamado {character}. "
        f"A {character} le encantaba mirar el cielo por las noches, cuando todo "
        f"estaba tranquilo y en calma."
    )
    cuerpo = [
        f"Una noche muy suave, {character} salió despacito a pasear. "
        f"El aire olía a flores dormidas y las estrellas brillaban despacio, "
        f"como pequeñas luces que decían buenas noches.",
        f"Por el camino, {character} encontró nuevos amigos. Juntos aprendieron "
        f"que compartir y cuidarse es lo que hace especial la {theme}.",
        f"Poco a poco, el mundo se fue quedando quietecito. Los árboles susurraban "
        f"canciones de cuna y la luna acariciaba todo con su luz plateada.",
        f"{character} sintió los ojitos pesados, muy pesados, y una sonrisa "
        f"tranquila. Respiró hondo, una vez... y otra vez... muy despacio.",
    ]
    cierre = (
        f"Y así, arropado por la calma de {setting}, {character} se quedó "
        f"profundamente dormido. Buenas noches. Que sueñes cosas bonitas."
    )
    partes = [intro] + cuerpo[: max(1, paragraphs - 2)] + [cierre]
    texto = "\n\n".join(partes)

    meta = dict(DEFAULT_METADATA)
    meta.update({
        "title": title,
        "genre": "bedtime",
        "theme": theme,
        "story": texto,
        "characters": [{"name": character, "role": "protagonista"}],
        "target_duration_minutes": estimate_duration_minutes(texto),
    })
    return meta
