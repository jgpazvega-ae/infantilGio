"""
generate_scene_plan.py — Planificador de escenas (Fase 5).

Convierte un cuento en un plan de escenas (narración + tiempo + visual) y lo
guarda en content/scene_plans/<slug>.json y .txt. Si existe la narración,
usa su duración real para repartir los tiempos.

Uso:
    python scripts/generate_scene_plan.py content/stories/andre.txt
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.ffmpeg_utils import get_duration  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.paths import slugify  # noqa: E402
from core.scene_plan import build_scene_plan, render_scene_plan  # noqa: E402
from core.story import parse_story_file  # noqa: E402

log = get_logger("generate_scene_plan")


def _resolve_story(ref):
    ref = Path(ref)
    if ref.exists():
        return ref
    for cand in (config.STORIES_DIR / ref.name,
                 (config.STORIES_DIR / ref.name).with_suffix(".txt"),
                 (config.STORIES_DIR / ref.name).with_suffix(".md")):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No se encontró el cuento: {ref}")


def generate_scene_plan(story_ref, force=False, dry_run=False):
    config.ensure_dirs()
    ruta = _resolve_story(story_ref)
    meta = parse_story_file(ruta)
    slug = slugify(meta["title"])

    narration = config.NARRATION_DIR / f"{slug}.mp3"
    narr_secs = None
    if narration.exists():
        try:
            narr_secs = get_duration(narration)
        except Exception:  # noqa: BLE001
            narr_secs = None

    hint = config.STYLES.get("visual_styles", {}).get(
        meta.get("visual_style", "soft_storybook"), {}).get("prompt_hint", "")
    plan = build_scene_plan(meta, narration_seconds=narr_secs, visual_style_hint=hint)

    out_json = config.SCENE_PLANS_DIR / f"{slug}.json"
    out_txt = config.SCENE_PLANS_DIR / f"{slug}.txt"

    if dry_run:
        log.info("[dry-run] %d escenas -> %s", len(plan["scenes"]), out_json)
        return plan
    if out_json.exists() and not force:
        log.info("Ya existe: %s (usa --force)", out_json)
        return json.loads(out_json.read_text(encoding="utf-8"))

    out_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    out_txt.write_text(render_scene_plan(plan), encoding="utf-8")
    log.info("OK plan -> %s (%d escenas, %.0fs)", out_json, len(plan["scenes"]),
             plan["total_seconds"])
    return plan


def main():
    ap = argparse.ArgumentParser(description="Genera el plan de escenas de un cuento.")
    ap.add_argument("story", help="Ruta o nombre del cuento")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        generate_scene_plan(args.story, force=args.force, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
