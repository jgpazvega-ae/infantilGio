"""
pipeline.py — Orquestador principal de infantilGio (Fase 9).

Ejecuta flujos completos y arma el paquete final + manifest de cada
producción. Python solo orquesta; FFmpeg hace el trabajo pesado.

Comandos:
    python pipeline.py story  content/stories/andre.md --footage mar.mp4
    python pipeline.py sleep  assets/ambient/ambient_mar.mp3 --video mar.mp4 --duration 05:55:00
    python pipeline.py ambient assets/ambient/ambient_mar.mp3 --duration 03:00:00 --title "Sonido del Mar"
    python pipeline.py thumbnail --video video/final/andre.mp4 --titulo "André"
    python pipeline.py metadata --story content/stories/andre.md
    python pipeline.py qc --package output/packages/andre/

Opciones globales por comando: --force, --dry-run.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from core.ffmpeg_utils import check_ffmpeg, get_duration, parse_duration  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.manifest import Manifest, ProductionState  # noqa: E402
from core.paths import slugify  # noqa: E402
from core.story import parse_story_file  # noqa: E402

from scripts import assemble_video, generate_audio, generate_metadata  # noqa: E402
from scripts import generate_scene_plan, generate_thumbnail, create_loop  # noqa: E402
from scripts import quality_check  # noqa: E402

log = get_logger("pipeline")


# ---------------------------------------------------------------------------
# Empaquetado
# ---------------------------------------------------------------------------
def _build_package(slug, content_type, video=None, audio=None, thumbnail=None,
                   metadata=None, qc_status=None, info=None):
    """Copia los artefactos a output/packages/<slug>/ y escribe el manifest."""
    pkg = config.PACKAGES_DIR / slug
    pkg.mkdir(parents=True, exist_ok=True)

    manifest = Manifest.load_or_create(pkg / "manifest.json", slug, content_type)
    if video and Path(video).exists():
        shutil.copy2(video, pkg / "video.mp4")
        manifest.set_artifact("video", "video.mp4")
        manifest.advance_state(ProductionState.VIDEO_READY)
    if audio and Path(audio).exists():
        shutil.copy2(audio, pkg / "audio.mp3")
        manifest.set_artifact("audio", "audio.mp3")
        manifest.advance_state(ProductionState.AUDIO_READY)
    if thumbnail and Path(thumbnail).exists():
        shutil.copy2(thumbnail, pkg / "thumbnail.jpg")
        manifest.set_artifact("thumbnail", "thumbnail.jpg")
        manifest.advance_state(ProductionState.THUMBNAIL_READY)
    if metadata:
        (pkg / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        (pkg / "description.txt").write_text(metadata.get("description", ""), encoding="utf-8")
        manifest.set_artifact("metadata", "metadata.json")
        manifest.set_artifact("description", "description.txt")

    for k, v in (info or {}).items():
        manifest.set_info(k, v)

    if qc_status:
        manifest.set_quality(qc_status)
        if qc_status == "PASS":
            manifest.advance_state(ProductionState.QC_PASSED)
            manifest.advance_state(ProductionState.READY_TO_UPLOAD)
    manifest.save()
    log.info("Package -> %s (estado=%s, QC=%s)", pkg, manifest.data["state"], qc_status)
    return pkg


# ---------------------------------------------------------------------------
# Comando: story
# ---------------------------------------------------------------------------
def cmd_story(args):
    check_ffmpeg()
    config.ensure_dirs()
    story_path = Path(args.input)
    if not story_path.exists():
        story_path = config.STORIES_DIR / Path(args.input).name
    meta = parse_story_file(story_path)
    slug = slugify(meta["title"])
    log.info("=== STORY: %s (%s) ===", meta["title"], slug)

    # 1) Narración
    narration = generate_audio.generate_audio(story_path, voice_id=args.voice_id,
                                              force=args.force, dry_run=args.dry_run)
    # 2) Plan de escenas
    generate_scene_plan.generate_scene_plan(story_path, force=args.force, dry_run=args.dry_run)
    # 3) Video
    video = assemble_video.assemble(slug, footage=args.footage, ambient=args.ambient,
                                    use_ambient=not args.no_ambient,
                                    force=args.force, dry_run=args.dry_run)
    # 4) Miniatura
    thumb = generate_thumbnail.generate_thumbnail(
        meta["title"], video=str(video), salida=slug,
        force=args.force, dry_run=args.dry_run)
    # 5) Metadata
    dur = None
    if not args.dry_run and Path(video).exists():
        dur = get_duration(video)
    metadata = generate_metadata.generate_metadata(story=str(story_path),
                                                   duration=dur, force=args.force,
                                                   dry_run=args.dry_run)
    if args.dry_run:
        log.info("[dry-run] STORY completo (sin archivos).")
        return

    # 6) QC + package
    qc = quality_check.run_qc(video=str(video), thumbnail=str(thumb),
                              metadata=metadata, exp_duration=dur)
    print(qc.render())
    _build_package(slug, "story", video=video, thumbnail=thumb, metadata=metadata,
                   qc_status=qc.status, info={"duration_seconds": dur})


# ---------------------------------------------------------------------------
# Comando: sleep
# ---------------------------------------------------------------------------
def cmd_sleep(args):
    check_ffmpeg()
    config.ensure_dirs()
    target = parse_duration(args.duration or config.loop_preset().get("default_duration"))
    title = args.title or f"{Path(args.input).stem} para dormir"
    slug = slugify(title)
    log.info("=== SLEEP: %s (%s) ===", title, args.duration or "05:55:00")

    if not args.video:
        # Busca cualquier footage disponible.
        cands = sorted(config.FOOTAGE_DIR.glob("*.mp4"))
        if not cands:
            raise SystemExit("Falta --video (o coloca un clip en assets/footage/).")
        args.video = str(cands[0])
        log.info("Usando footage: %s", args.video)

    video = create_loop.create_loop(args.input, video=args.video, duration=args.duration,
                                    force=args.force, dry_run=args.dry_run)
    thumb = generate_thumbnail.generate_thumbnail(title, video=str(video), salida=slug,
                                                  segundo=5, force=args.force,
                                                  dry_run=args.dry_run)
    metadata = generate_metadata.generate_metadata(title=title, content_type="sleep",
                                                   duration=target, force=args.force,
                                                   dry_run=args.dry_run)
    if args.dry_run:
        log.info("[dry-run] SLEEP completo (sin archivos).")
        return

    dur = get_duration(video)
    qc = quality_check.run_qc(video=str(video), thumbnail=str(thumb),
                              metadata=metadata, exp_duration=target)
    print(qc.render())
    _build_package(slug, "sleep", video=video, thumbnail=thumb, metadata=metadata,
                   qc_status=qc.status, info={"duration_seconds": dur,
                                              "target_seconds": target})


# ---------------------------------------------------------------------------
# Comando: ambient (solo audio)
# ---------------------------------------------------------------------------
def cmd_ambient(args):
    check_ffmpeg()
    config.ensure_dirs()
    target = parse_duration(args.duration or config.loop_preset().get("default_duration"))
    title = args.title or f"{Path(args.input).stem} ambiental"
    slug = slugify(title)
    log.info("=== AMBIENT: %s ===", title)

    audio = create_loop.create_loop(args.input, video=None, duration=args.duration,
                                    force=args.force, dry_run=args.dry_run)
    metadata = generate_metadata.generate_metadata(title=title, content_type="ambient",
                                                   duration=target, force=args.force,
                                                   dry_run=args.dry_run)
    if args.dry_run:
        log.info("[dry-run] AMBIENT completo (sin archivos).")
        return
    dur = get_duration(audio)
    qc = quality_check.run_qc(audio=str(audio), metadata=metadata)
    print(qc.render())
    _build_package(slug, "ambient", audio=audio, metadata=metadata,
                   qc_status=qc.status, info={"duration_seconds": dur})


# ---------------------------------------------------------------------------
# Comandos directos
# ---------------------------------------------------------------------------
def cmd_thumbnail(args):
    generate_thumbnail.generate_thumbnail(args.titulo, video=args.video, imagen=args.imagen,
                                          segundo=args.segundo, salida=args.salida,
                                          force=args.force, dry_run=args.dry_run)


def cmd_metadata(args):
    generate_metadata.generate_metadata(story=args.story, title=args.title,
                                        content_type=args.content_type,
                                        duration=args.duration, force=args.force,
                                        dry_run=args.dry_run)


def cmd_qc(args):
    result = quality_check.run_qc(video=args.video, audio=args.audio,
                                  thumbnail=args.thumbnail, metadata=args.metadata,
                                  package=args.package, exp_duration=args.expected_duration)
    print(result.render())
    sys.exit(0 if result.passed else 2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="pipeline.py",
        description="infantilGio — fábrica de contenido infantil para YouTube.")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--force", action="store_true", help="Regenera aunque exista")
        sp.add_argument("--dry-run", action="store_true", help="Muestra sin crear archivos")

    s = sub.add_parser("story", help="Cuento narrado completo")
    s.add_argument("input", help="Archivo del cuento (content/stories/)")
    s.add_argument("--footage", required=True, help="Clip de fondo (assets/footage/)")
    s.add_argument("--ambient", default=None)
    s.add_argument("--no-ambient", action="store_true")
    s.add_argument("--voice-id", default=None)
    add_common(s); s.set_defaults(func=cmd_story)

    s = sub.add_parser("sleep", help="Video largo para dormir (video+audio en loop)")
    s.add_argument("input", help="Audio ambiental base")
    s.add_argument("--video", default=None, help="Clip de fondo (assets/footage/)")
    s.add_argument("--duration", default=None, help="HH:MM:SS (def 05:55:00)")
    s.add_argument("--title", default=None)
    add_common(s); s.set_defaults(func=cmd_sleep)

    s = sub.add_parser("ambient", help="Loop de audio ambiental")
    s.add_argument("input", help="Audio ambiental base")
    s.add_argument("--duration", default=None)
    s.add_argument("--title", default=None)
    add_common(s); s.set_defaults(func=cmd_ambient)

    s = sub.add_parser("thumbnail", help="Genera una miniatura")
    s.add_argument("--titulo", required=True)
    s.add_argument("--video", default=None)
    s.add_argument("--imagen", default=None)
    s.add_argument("--segundo", type=int, default=None)
    s.add_argument("--salida", default=None)
    add_common(s); s.set_defaults(func=cmd_thumbnail)

    s = sub.add_parser("metadata", help="Genera metadata de YouTube")
    s.add_argument("--story", default=None)
    s.add_argument("--title", default=None)
    s.add_argument("--content-type", default="story")
    s.add_argument("--duration", default=None)
    add_common(s); s.set_defaults(func=cmd_metadata)

    s = sub.add_parser("qc", help="Control de calidad")
    s.add_argument("--video", default=None)
    s.add_argument("--audio", default=None)
    s.add_argument("--thumbnail", default=None)
    s.add_argument("--metadata", default=None)
    s.add_argument("--package", default=None)
    s.add_argument("--expected-duration", type=float, default=None)
    s.set_defaults(func=cmd_qc)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
