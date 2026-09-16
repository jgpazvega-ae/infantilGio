"""
generate_story.py — Story engine (Fase 5).

Crea un archivo de cuento estructurado en content/stories/<slug>.md con
front-matter YAML (metadata) + texto. Puede:

  - Registrar/normalizar un cuento que ya tienes (--from-text archivo.txt).
  - Generar un cuento de prueba por plantilla determinista (--template),
    útil para probar el pipeline de extremo a extremo sin depender de un LLM.

Nota: la generación creativa con un LLM es una mejora futura; esta interfaz ya
deja el punto de integración preparado (generate_story_from_params()).

Uso:
    python scripts/generate_story.py --template --title "André y el Tren de las Estrellas" \
        --character "André" --theme "amistad" --setting "el bosque de los sueños"
    python scripts/generate_story.py --from-text mi_cuento.txt --title "Mi Cuento"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

import config  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.paths import slugify  # noqa: E402
from core.story import (generate_story_from_params,  # noqa: E402
                        parse_story_file)

log = get_logger("generate_story")


def _write_story(meta, force=False):
    config.ensure_dirs()
    slug = slugify(meta["title"])
    out = config.STORIES_DIR / f"{slug}.md"
    if out.exists() and not force:
        log.info("Ya existe: %s (usa --force)", out)
        return out
    body = meta.pop("story", "")
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    out.write_text(f"---\n{front}\n---\n\n{body}\n", encoding="utf-8")
    log.info("OK cuento -> %s", out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Crea/normaliza un cuento estructurado.")
    ap.add_argument("--title", required=True, help="Título del cuento")
    ap.add_argument("--template", action="store_true", help="Genera cuento por plantilla")
    ap.add_argument("--from-text", default=None, help="Archivo de texto existente a normalizar")
    ap.add_argument("--character", default="Andrés")
    ap.add_argument("--theme", default="amistad")
    ap.add_argument("--setting", default="el bosque de los sueños")
    ap.add_argument("--paragraphs", type=int, default=5)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    try:
        if args.from_text:
            src = Path(args.from_text)
            if not src.exists():
                src = config.STORIES_DIR / Path(args.from_text).name
            meta = parse_story_file(src)
            meta["title"] = args.title
        elif args.template:
            meta = generate_story_from_params(
                args.title, character=args.character, theme=args.theme,
                setting=args.setting, paragraphs=args.paragraphs)
        else:
            ap.error("Indica --template o --from-text")
        _write_story(meta, force=args.force)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
