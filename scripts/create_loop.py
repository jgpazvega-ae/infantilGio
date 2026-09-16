"""
create_loop.py — Motor de loop de audio y/o video (Fase 3 / Sleep engine).

Genera audio y/o video en bucle de una duración exacta (por defecto 5h55m).

Uso:
    # Solo audio (loop suave con crossfade, duración exacta):
    python scripts/create_loop.py --audio assets/ambient/ambient_mar.mp3 --duration 05:55:00

    # Video de dormir completo (video + audio en loop):
    python scripts/create_loop.py --audio assets/ambient/ambient_mar.mp3 \
        --video assets/footage/mar.mp4 --duration 05:55:00

    # Ver qué haría, sin crear archivos:
    python scripts/create_loop.py --audio ... --duration 02:00:00 --dry-run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.audio_loop import build_audio_loop  # noqa: E402
from core.ffmpeg_utils import (check_ffmpeg, format_duration,  # noqa: E402
                               format_duration_compact, get_duration,
                               parse_duration)
from core.logging_utils import get_logger  # noqa: E402
from core.video_loop import build_sleep_video  # noqa: E402

log = get_logger("create_loop")


def _valid(path, target=None, tol=3.0):
    try:
        if not path.exists():
            return False
        if target is None:
            return get_duration(path) > 0
        return abs(get_duration(path) - target) <= tol
    except Exception:  # noqa: BLE001
        return False


def create_loop(audio, video=None, duration=None, force=False, dry_run=False):
    """
    Crea el loop. Si se da --video produce el video de dormir; si no, solo
    el audio en bucle. Devuelve la ruta principal generada.
    """
    check_ffmpeg()
    config.ensure_dirs()

    lp = config.loop_preset()
    vp = config.video_preset()
    target = parse_duration(duration or lp.get("default_duration", "05:55:00"))
    crossfade = lp.get("crossfade_seconds", 2)

    audio = Path(audio)
    if not audio.exists():
        cand = config.ASSETS_AMBIENT_DIR / audio.name
        if cand.exists():
            audio = cand
        else:
            raise FileNotFoundError(f"No existe el audio: {audio}")

    audio_dur = get_duration(audio)
    tag = format_duration_compact(target)
    log.info("Audio base: %s (%.1fs) | objetivo: %s",
             audio.name, audio_dur, format_duration(target))

    if video:
        video = Path(video)
        if not video.exists():
            cand = config.FOOTAGE_DIR / video.name
            if cand.exists():
                video = cand
            else:
                raise FileNotFoundError(f"No existe el video: {video}")
        out = config.OUTPUT_SLEEP_DIR / f"{video.stem}_dormir_{tag}.mp4"
    else:
        out = config.AUDIO_FINAL_DIR / f"{audio.stem}_loop_{tag}.mp3"

    if dry_run:
        log.info("[dry-run] Pasos:")
        log.info("  ✓ Analizar audio base (%.1fs)", audio_dur)
        log.info("  ✓ Calcular repeticiones para %s", format_duration(target))
        if video:
            log.info("  ✓ Normalizar clip base a %sx%s@%sfps (una vez)",
                     vp.get("width"), vp.get("height"), vp.get("fps"))
            log.info("  ✓ Muxear video (loop, stream-copy) + audio (loop, AAC)")
        else:
            log.info("  ✓ Loop de audio con crossfade %ss + fundido de salida", crossfade)
        log.info("  → salida: %s", out)
        return out

    if _valid(out, target if video else target, tol=3.0) and not force:
        log.info("Ya existe y coincide la duración: %s (usa --force)", out)
        return out

    if video:
        build_sleep_video(
            video, audio, out, target,
            width=vp.get("width", 1920), height=vp.get("height", 1080),
            fps=vp.get("fps", 30), preset=vp.get("preset", "medium"),
            crossfade=crossfade, audio_volume=1.0,
            logger=log, cache_dir=config.CACHE_DIR,
        )
    else:
        build_audio_loop(
            audio, out, target, crossfade=crossfade, fade_out=2,
            logger=log, cache_dir=config.CACHE_DIR,
        )

    dur = get_duration(out)
    log.info("OK loop -> %s | duración=%s (objetivo %s)",
             out, format_duration(dur), format_duration(target))
    return out


def main():
    ap = argparse.ArgumentParser(description="Genera loops de audio/video de duración exacta.")
    ap.add_argument("--audio", required=True, help="Audio base (assets/ambient/)")
    ap.add_argument("--video", default=None, help="Video base opcional (assets/footage/)")
    ap.add_argument("--duration", default=None, help="Duración objetivo (HH:MM:SS). Def: 05:55:00")
    ap.add_argument("--force", action="store_true", help="Regenera aunque exista")
    ap.add_argument("--dry-run", action="store_true", help="Muestra sin generar")
    args = ap.parse_args()
    try:
        create_loop(args.audio, video=args.video, duration=args.duration,
                    force=args.force, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
