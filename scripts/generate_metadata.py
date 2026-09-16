"""
generate_metadata.py — Metadata de YouTube (Fase 7).

Produce título, descripción, tags, categoría, idioma y edad recomendada, y los
guarda en content/metadata/<slug>.json (+ description.txt). No genera títulos
spam: usa la identidad del canal (config/channels.yaml).

Uso:
    python scripts/generate_metadata.py --story content/stories/andre.md
    python scripts/generate_metadata.py --title "Sonido del Mar" --content-type sleep --duration 21300
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.metadata import build_metadata  # noqa: E402
from core.paths import slugify  # noqa: E402
from core.story import parse_story_file  # noqa: E402

log = get_logger("generate_metadata")


def generate_metadata(story=None, title=None, content_type="story",
                      duration=None, force=False, dry_run=False):
    config.ensure_dirs()
    story_meta = {}
    if story:
        src = Path(story)
        if not src.exists():
            src = config.STORIES_DIR / Path(story).name
        story_meta = parse_story_file(src)
        title = title or story_meta.get("title")
        content_type = story_meta.get("genre", content_type)
    if not title:
        raise ValueError("Indica --story o --title.")

    meta = build_metadata(content_type, title, config.default_channel(),
                          story_meta=story_meta,
                          duration_seconds=float(duration) if duration else None)

    slug = slugify(title)
    out = config.METADATA_DIR / f"{slug}.json"
    desc = config.METADATA_DIR / f"{slug}.description.txt"
    if dry_run:
        log.info("[dry-run] metadata '%s' (%d tags) -> %s",
                 meta["title"], len(meta["tags"]), out)
        return meta
    if out.exists() and not force:
        log.info("Ya existe: %s (usa --force)", out)
        return json.loads(out.read_text(encoding="utf-8"))

    out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    desc.write_text(meta["description"], encoding="utf-8")
    log.info("OK metadata -> %s | título='%s' | %d tags", out, meta["title"], len(meta["tags"]))
    return meta


def main():
    ap = argparse.ArgumentParser(description="Genera metadata de YouTube.")
    ap.add_argument("--story", default=None, help="Cuento (content/stories/)")
    ap.add_argument("--title", default=None, help="Título (si no hay cuento)")
    ap.add_argument("--content-type", default="story", help="story|sleep|ambient")
    ap.add_argument("--duration", default=None, help="Duración en segundos")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        generate_metadata(story=args.story, title=args.title,
                          content_type=args.content_type, duration=args.duration,
                          force=args.force, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
