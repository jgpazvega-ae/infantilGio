"""
Planificador de escenas (scene planner).

Convierte un cuento en una lista de escenas con tiempos aproximados y una
descripción visual por escena, asociando narración + escena + visual. Los
tiempos se reparten proporcionalmente a la longitud de cada párrafo sobre la
duración real de la narración (si se conoce) o la estimada.
"""

import re

from core.ffmpeg_utils import format_duration
from core.story import estimate_duration_minutes


def _paragraphs(texto):
    return [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]


def build_scene_plan(story_meta, narration_seconds=None, visual_style_hint=""):
    """
    Devuelve un dict con la lista de escenas. Cada escena tiene:
      index, start, end, start_hms, end_hms, narration, visual.
    """
    texto = story_meta.get("story", "")
    parrafos = _paragraphs(texto)
    if not parrafos:
        return {"scenes": [], "total_seconds": 0}

    total = narration_seconds
    if not total:
        total = estimate_duration_minutes(texto) * 60 or len(parrafos) * 30

    # Reparto proporcional al número de caracteres de cada párrafo.
    longitudes = [len(p) for p in parrafos]
    suma = sum(longitudes) or 1

    escenas = []
    t = 0.0
    for i, (parrafo, ln) in enumerate(zip(parrafos, longitudes), start=1):
        dur = total * (ln / suma)
        inicio, fin = t, t + dur
        t = fin
        # Descripción visual derivada del contenido + estilo global.
        visual = _visual_hint(parrafo, visual_style_hint)
        escenas.append({
            "index": i,
            "start": round(inicio, 2),
            "end": round(fin, 2),
            "start_hms": format_duration(inicio),
            "end_hms": format_duration(fin),
            "narration": parrafo,
            "visual": visual,
        })

    return {"scenes": escenas, "total_seconds": round(total, 2)}


def _visual_hint(parrafo, style_hint):
    """Genera una pista visual sencilla a partir del texto de la escena."""
    # Toma la primera frase como base de la descripción visual.
    primera = re.split(r"(?<=[.!?…])\s+", parrafo.strip())[0]
    base = primera[:140]
    if style_hint:
        return f"{base} — estilo: {style_hint}"
    return base


def render_scene_plan(plan):
    """Representación de texto legible del plan de escenas."""
    lines = []
    for e in plan.get("scenes", []):
        lines.append(f"Scene {e['index']:02d}")
        lines.append(f"{e['start_hms']} - {e['end_hms']}")
        lines.append(f"Narration: {e['narration']}")
        lines.append(f"Visual: {e['visual']}")
        lines.append("")
    return "\n".join(lines).strip()
