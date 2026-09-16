"""
assemble_video.py — Ensamblado de video de cuento (Fase 4).

Combina narración (100%) + footage (en loop hasta cubrir la narración) +
ambiente opcional (~18%). El video termina exactamente cuando termina la
narración. Salida 1920x1080 en video/final/.

Uso:
    python scripts/assemble_video.py andre --footage assets/footage/mar.mp4
    python scripts/assemble_video.py andre --footage mar.mp4 --no-ambient
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.ffmpeg_utils import (check_ffmpeg, get_duration,  # noqa: E402
                               run_ffmpeg)
from core.logging_utils import get_logger  # noqa: E402

log = get_logger("assemble_video")


def _resolve(ref, folder, suffixes=(".mp4", ".mp3")):
    ref = Path(ref)
    if ref.exists():
        return ref
    for cand in [folder / ref.name] + [(folder / ref.name).with_suffix(s) for s in suffixes]:
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No se encontró: {ref} (ni en {folder})")


def assemble(name, footage, ambient=None, use_ambient=True, force=False, dry_run=False):
    """Ensambla el video del cuento. Devuelve la ruta del mp4 final."""
    check_ffmpeg()
    config.ensure_dirs()

    narration = _resolve(Path(name).with_suffix(".mp3") if Path(name).suffix == "" else name,
                         config.NARRATION_DIR, (".mp3",))
    dur = get_duration(narration)
    footage = _resolve(footage, config.FOOTAGE_DIR, (".mp4", ".mov", ".mkv"))

    amb = None
    if use_ambient:
        try:
            amb = _resolve(ambient or "ambient_mar.mp3", config.ASSETS_AMBIENT_DIR, (".mp3",))
        except FileNotFoundError:
            log.warning("Sin ambiente disponible; se omite el fondo.")

    vp = config.video_preset()
    ap = config.audio_preset()
    w, h, fps = vp.get("width", 1920), vp.get("height", 1080), vp.get("fps", 30)
    out = config.VIDEO_FINAL_DIR / f"{narration.stem}.mp4"

    if dry_run:
        log.info("[dry-run] narración=%s (%.1fs) footage=%s ambiente=%s -> %s",
                 narration.name, dur, footage.name, amb.name if amb else "no", out)
        return out

    if out.exists() and not force and abs(get_duration(out) - dur) <= 2:
        log.info("Ya existe y coincide: %s (usa --force)", out)
        return out

    scale = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
             f"crop={w}:{h},fps={fps}[v]")
    inputs = ["-stream_loop", "-1", "-i", footage, "-i", narration]
    if amb is not None:
        inputs += ["-stream_loop", "-1", "-i", amb]
        filtro = (f"{scale};[1:a]volume={ap.get('narration_volume', 1.0)}[n];"
                  f"[2:a]volume={ap.get('ambient_volume', 0.18)}[b];"
                  f"[n][b]amix=inputs=2:duration=first:dropout_transition=0[a]")
    else:
        filtro = f"{scale};[1:a]volume={ap.get('narration_volume', 1.0)}[a]"

    run_ffmpeg([
        *inputs, "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
        "-t", f"{dur}", "-c:v", vp.get("video_codec", "libx264"),
        "-preset", vp.get("preset", "medium"), "-pix_fmt", vp.get("pixel_format", "yuv420p"),
        "-r", str(fps), "-c:a", vp.get("audio_codec", "aac"),
        "-b:a", vp.get("audio_bitrate", "192k"), "-shortest", out,
    ], logger=log)

    log.info("OK video -> %s | duración=%.1fs", out, get_duration(out))
    return out


def main():
    ap = argparse.ArgumentParser(description="Ensambla video de cuento (narración+footage+ambiente).")
    ap.add_argument("name", help="Nombre base de la narración (audio/narration/)")
    ap.add_argument("--footage", required=True, help="Clip de fondo (assets/footage/)")
    ap.add_argument("--ambient", default=None, help="Audio ambiental (por defecto el del mar)")
    ap.add_argument("--no-ambient", action="store_true", help="No mezclar ambiente")
    ap.add_argument("--force", action="store_true", help="Regenera aunque exista")
    ap.add_argument("--dry-run", action="store_true", help="Muestra sin generar")
    args = ap.parse_args()
    try:
        assemble(args.name, footage=args.footage, ambient=args.ambient,
                 use_ambient=not args.no_ambient, force=args.force, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
