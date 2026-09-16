"""
create_sleep_video.py — Sleep Video Factory.

Produce un video de dormir de larga duración (por defecto 05:55:00) a partir
de un audio ambiental y un visual nocturno procedural (o footage propio),
de forma EFICIENTE: el clip visual se normaliza una sola vez y el resultado
largo se genera con video stream-copy + audio AAC (Python orquesta, FFmpeg
procesa). Genera thumbnail, metadata, QC y package.

Uso:
    python scripts/create_sleep_video.py \
        --audio assets/ambient/ambient_mar.mp3 \
        --duration 05:55:00 --preset ocean_night \
        --output output/sleep/ocean-night-5h55.mp4

Opciones: --footage (usar clip propio), --title, --force, --dry-run,
--no-normalize.
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.audio_loop import (build_ocean_filter, build_seamless_audio,  # noqa: E402
                             normalize_audio)
from core.ffmpeg_utils import (check_ffmpeg, format_duration,  # noqa: E402
                               format_duration_compact, get_duration,
                               get_stream, parse_duration)
from core.logging_utils import get_logger  # noqa: E402
from core.metadata import build_metadata  # noqa: E402
from core.paths import slugify  # noqa: E402
from core.qc import QCResult, check_audio, check_package, check_thumbnail, check_video  # noqa: E402
from core.system import (check_disk_space, estimate_video_size_bytes,  # noqa: E402
                         human_size)
from core.video_loop import build_sleep_video  # noqa: E402
from scripts import generate_visuals, sleep_visual  # noqa: E402

log = get_logger("create_sleep_video")

AUDIO_SEARCH_DIRS = ["assets/ambient", "assets", "audio/ambient", "audio", "footage"]
BASE_CLIP_SECONDS = 30  # duración del clip visual base que luego se repite


def _rel_to_base(path):
    """Ruta relativa a BASE_DIR si es posible; si no, la ruta tal cual."""
    import os
    try:
        return os.path.relpath(Path(path).resolve(), config.BASE_DIR)
    except ValueError:
        return str(path)


def _locate_audio(ref):
    """Localiza el audio: ruta directa o búsqueda por nombre en carpetas típicas."""
    if ref:
        p = Path(ref)
        if p.exists():
            return p
        for d in AUDIO_SEARCH_DIRS:
            cand = config.BASE_DIR / d / p.name
            if cand.exists():
                return cand
    # Autodetección: primer audio en assets/ambient.
    for d in AUDIO_SEARCH_DIRS:
        base = config.BASE_DIR / d
        if base.exists():
            for ext in ("*.mp3", "*.wav", "*.m4a", "*.ogg"):
                hits = sorted(base.glob(ext))
                if hits:
                    return hits[0]
    raise FileNotFoundError("No se encontró ningún audio (revisa assets/ambient/).")


def _intro_text_png(dst, text, size=(1920, 1080), fontsize=42):
    """
    Crea un PNG transparente con el mensaje de intro centrado (texto blanco con
    sombra suave para legibilidad sobre fondo oscuro). Devuelve dst.
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", fontsize)
    except OSError:
        font = ImageFont.load_default()

    lines = [ln.strip() for ln in str(text).strip().splitlines() if ln.strip()]
    line_h = draw.textbbox((0, 0), "Ay", font=font)[3] + 20
    total_h = line_h * len(lines)
    y = (H - total_h) // 2
    # Sombra: dibuja el texto en una capa negra difuminada.
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    for i, ln in enumerate(lines):
        w = draw.textbbox((0, 0), ln, font=font)[2]
        x = (W - w) // 2
        sdraw.text((x, y + i * line_h), ln, font=font, fill=(0, 0, 0, 220))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        w = draw.textbbox((0, 0), ln, font=font)[2]
        x = (W - w) // 2
        draw.text((x, y + i * line_h), ln, font=font, fill=(240, 244, 255, 255))
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "PNG")
    return dst


def _dark_thumbnail(dst, title, subtitle="", size=(1280, 720)):
    """Miniatura oscura: gradiente nocturno + luna + tipografía mínima."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = size
    img = Image.new("RGB", size, (2, 6, 16))
    # Gradiente vertical (más claro arriba, casi negro abajo).
    top, bot = (10, 22, 48), (1, 3, 10)
    for y in range(H):
        t = y / H
        row = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (W, y)], fill=row)
    # Luna (resplandor suave).
    moon = Image.new("RGBA", size, (0, 0, 0, 0))
    md = ImageDraw.Draw(moon)
    mx, my, mr = int(W * 0.72), int(H * 0.28), 70
    for rr in range(mr, 0, -1):
        a = int(120 * (rr / mr) ** 0.4)
        md.ellipse([mx - (mr - rr) - 40, my - (mr - rr) - 40,
                    mx + (mr - rr) + 40, my + (mr - rr) + 40], fill=(0, 0, 0, 0))
    md.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(240, 240, 220, 255))
    moon = moon.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), moon).convert("RGB")

    draw = ImageDraw.Draw(img)

    def font(sz):
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", sz)
        except OSError:
            return ImageFont.load_default()

    def centered(text, f, y, fill=(240, 244, 255)):
        w = draw.textbbox((0, 0), text, font=f)[2]
        draw.text(((W - w) // 2, y), text, font=f, fill=fill,
                  stroke_width=4, stroke_fill=(0, 0, 0))

    lines = title.upper().split("\n")
    f1 = font(96)
    y = int(H * 0.34)
    for ln in lines:
        centered(ln, f1, y)
        y += 110
    if subtitle:
        centered(subtitle, font(52), y + 8, fill=(180, 200, 230))
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "JPEG", quality=90)
    return dst


def create_sleep_video(audio=None, duration=None, preset="ocean_night", output=None,
                       footage=None, image=None, title=None, normalize=True,
                       clean_profile="ocean", force=False, dry_run=False):
    check_ffmpeg()
    config.ensure_dirs()
    t0 = time.time()

    target = parse_duration(duration or config.loop_preset().get("default_duration", "05:55:00"))
    tag = format_duration_compact(target)
    # Por defecto usa la grabación del mar (se limpia con el perfil 'ocean').
    if audio is None and config.DEFAULT_SEA_AUDIO.exists():
        audio = config.DEFAULT_SEA_AUDIO
    audio_path = _locate_audio(audio).resolve()

    # 1) Probe del audio (verifica que sea reproducible / no corrupto).
    st = get_stream(audio_path, "audio")
    if st is None:
        raise RuntimeError(f"El audio no tiene stream reproducible: {audio_path}")
    a_dur = get_duration(audio_path)
    sr, ch = int(st.get("sample_rate", 0)), int(st.get("channels", 0))
    log.info("Audio: %s | dur=%.1fs sr=%s ch=%s codec=%s",
             audio_path, a_dur, sr, ch, st.get("codec_name"))

    if not title:
        title = "Sonidos del Mar para Dormir"
    # El slug (nombre del package) sigue al --output si se indica; si no, preset+duración.
    slug = slugify(Path(output).stem) if output else slugify(f"{preset}-{tag}")
    out = Path(output) if output else (config.OUTPUT_SLEEP_DIR / f"{slug}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)  # asegura el dir de salida (p. ej. --output en un dir nuevo)

    pkg = config.PACKAGES_DIR / slug

    # 2) Reproducibilidad.
    if out.exists() and not force and not dry_run:
        try:
            if abs(get_duration(out) - target) <= 5:
                log.info("Existing valid output detected. Use --force to regenerate. (%s)", out)
                return out
        except Exception:  # noqa: BLE001
            pass

    # 3) Estimación de disco (aborta ANTES del render si no cabe).
    est = estimate_video_size_bytes(target)
    ok, free, needed = check_disk_space(out.parent, est)
    log.info("Disco: estimado=%s necesario(margen)=%s libre=%s",
             human_size(est), human_size(needed), human_size(free))

    if dry_run:
        log.info("[dry-run] Pasos:")
        log.info("  ✓ Localizar audio: %s (%.1fs)", audio_path, a_dur)
        log.info("  ✓ %sNormalizar audio (loudnorm, 44.1k stereo)",
                 "" if normalize else "[omitido] ")
        log.info("  ✓ Loop de audio con crossfade a %s", format_duration(target))
        log.info("  ✓ Visual: %s (%s)", "footage propio" if footage else f"procedural '{preset}'",
                 "clip base %ds + crossfade" % BASE_CLIP_SECONDS)
        log.info("  ✓ Muxear video (stream-copy) + audio (AAC), recorte exacto")
        log.info("  ✓ Thumbnail + metadata + QC + package")
        log.info("  → salida: %s | package: %s", out, pkg)
        if not ok:
            log.warning("  ⚠ Disco insuficiente para el render real.")
        return out

    if not ok:
        raise SystemExit(
            "ABORT: espacio en disco insuficiente para el render.\n"
            f"  Estimated required space: {human_size(needed)}\n"
            f"  Available space:         {human_size(free)}\n"
            f"  Recommended action:      libera espacio o usa una duración menor."
        )

    # 4) Limpieza/normalización de audio (sin tocar el original) + loop seamless.
    #    Intermedios sin pérdida (.wav) para no apilar generaciones de MP3;
    #    la única codificación con pérdida es el AAC final del video.
    src_for_loop = audio_path
    if normalize:
        # Perfil de limpieza: 'ocean' (resalta el mar) | 'auto' (adaptativo) | 'none'.
        af = None
        if clean_profile == "ocean":
            af = build_ocean_filter(config.PRESETS.get("audio_cleanup", {}).get("ocean", {}))
            log.info("Limpieza de audio: perfil 'ocean' (resalta el mar).")
        norm = config.CACHE_DIR / f"{audio_path.stem}_{clean_profile}_clean.wav"
        if force or not norm.exists():
            normalize_audio(audio_path, norm, af=af, source_sample_rate=sr,
                            clean=(clean_profile != "none"), logger=log)
        src_for_loop = norm

    xfade = int((config.PRESETS.get("sleep", {}).get(preset, {}) or {}).get("transition_duration", 8))
    seamless_audio = config.CACHE_DIR / f"{audio_path.stem}_seamless.wav"
    if force or not seamless_audio.exists():
        build_seamless_audio(src_for_loop, seamless_audio, min(xfade, max(1, a_dur / 3)), logger=log)

    # 5) Visual base. Prioridad: footage propio > imagen fija (con micro-
    #    movimiento) > visual procedural.
    if footage:
        _, base_clip = generate_visuals.resolve_visual_source(footage=footage)
    elif image:
        img = Path(image)
        if not img.exists():
            img = config.IMAGES_DIR / Path(image).name
        if not img.exists():
            raise FileNotFoundError(f"No existe la imagen: {image}")
        base_clip = config.CACHE_DIR / f"img_{img.stem}_base.mp4"
        if force or not base_clip.exists():
            sleep_visual.build_from_image(img, base_clip, duration=BASE_CLIP_SECONDS,
                                          logger=log, cache_dir=config.CACHE_DIR)
    else:
        base_clip = config.CACHE_DIR / f"{preset}_base.mp4"
        if force or not base_clip.exists():
            sleep_visual.generate_visual(preset, base_clip, duration=BASE_CLIP_SECONDS, logger=log)

    # 6) Render largo (eficiente): video loop stream-copy + audio loop AAC.
    vp = config.video_preset()

    # Mensaje de entrada (intro): aparece y se desvanece al inicio.
    intro = None
    icfg = config.PRESETS.get("sleep_intro", {}) or {}
    if icfg.get("enabled") and icfg.get("text"):
        png = _intro_text_png(config.CACHE_DIR / "intro_text.png", icfg["text"],
                              size=(vp.get("width", 1920), vp.get("height", 1080)),
                              fontsize=icfg.get("fontsize", 42))
        intro = {"overlay_png": str(png), "start": icfg.get("start", 3),
                 "fade": icfg.get("fade", 1.5), "hold": icfg.get("hold", 11)}

    log.info("Render %s -> %s", format_duration(target), out)
    build_sleep_video(
        base_clip, seamless_audio, out, target,
        width=vp.get("width", 1920), height=vp.get("height", 1080),
        fps=vp.get("fps", 30), preset=vp.get("preset", "medium"),
        crossfade=xfade, audio_volume=1.0,
        audio_bitrate=vp.get("audio_bitrate", "256k"),
        logger=log, cache_dir=config.CACHE_DIR, intro=intro,
    )
    out_dur = get_duration(out)

    # 7) Thumbnail (oscuro, con luna y tipografía mínima).
    thumb = config.THUMBNAILS_DIR / f"{slug}.jpg"
    _dark_thumbnail(thumb, "SONIDOS DEL MAR\nPARA DORMIR",
                    subtitle="5 Horas 55 Minutos" if abs(target - 21300) < 5 else format_duration(target))

    # 8) Metadata.
    metadata = build_metadata("sleep", title, config.default_channel(),
                              story_meta={"genre": "sleep", "age_range": "0-5",
                                          "theme": "relajación"},
                              duration_seconds=target)

    # 9) QC.
    qc = QCResult()
    check_video(qc, out, exp_w=vp.get("width", 1920), exp_h=vp.get("height", 1080),
                exp_fps=vp.get("fps", 30), exp_duration=target, tolerance=5.0)
    check_audio(qc, out, prefix="Audio (en video)")
    check_thumbnail(qc, thumb)
    check_package(qc, metadata)
    print(qc.render())

    # 10) Package + manifest (§20) + description.
    pkg.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, pkg / "video.mp4")
    shutil.copy2(thumb, pkg / "thumbnail.jpg")
    (pkg / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (pkg / "description.txt").write_text(metadata["description"], encoding="utf-8")
    manifest = {
        "project": slug,
        "type": "sleep",
        "preset": preset,
        "duration": format_duration(target),
        "resolution": f"{vp.get('width', 1920)}x{vp.get('height', 1080)}",
        "fps": vp.get("fps", 30),
        "audio_source": _rel_to_base(audio_path),
        "video": "video.mp4",
        "thumbnail": "thumbnail.jpg",
        "output_duration": format_duration(out_dur),
        "output_size": human_size(out.stat().st_size),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "QC_PASSED" if qc.passed else "QC_FAILED",
    }
    (pkg / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 11) Log de producción.
    log.info("PRODUCTION | source_audio=%s | audio_dur=%.1fs | requested=%s | "
             "output_dur=%s | size=%s | render_time=%.1fs | QC=%s",
             audio_path.name, a_dur, format_duration(target), format_duration(out_dur),
             human_size(out.stat().st_size), time.time() - t0, qc.status)
    log.info("Package -> %s", pkg)
    if not qc.passed:
        raise SystemExit("QC FAILED: revisa el detalle arriba.")
    return out


def main():
    ap = argparse.ArgumentParser(description="Sleep Video Factory (video de dormir largo).")
    ap.add_argument("--audio", default=None, help="Audio base (autodetecta si se omite)")
    ap.add_argument("--duration", default=None, help="HH:MM:SS (def 05:55:00)")
    ap.add_argument("--preset", default="ocean_night", help="ocean_night|black_screen|ocean_bubbles")
    ap.add_argument("--output", default=None, help="Ruta del MP4 de salida")
    ap.add_argument("--footage", default=None, help="Usar clip propio en vez del visual procedural")
    ap.add_argument("--image", default=None, help="Usar una imagen fija (con micro-movimiento)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--no-normalize", action="store_true", help="No normalizar el audio")
    ap.add_argument("--clean-profile", default="ocean",
                    choices=["auto", "ocean", "none"],
                    help="Perfil de limpieza de audio (ocean = resalta el mar, por defecto)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        create_sleep_video(audio=args.audio, duration=args.duration, preset=args.preset,
                           output=args.output, footage=args.footage, image=args.image,
                           title=args.title, normalize=not args.no_normalize,
                           clean_profile=args.clean_profile,
                           force=args.force, dry_run=args.dry_run)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
