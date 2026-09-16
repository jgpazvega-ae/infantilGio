"""
sleep_visual.py — Motor de visual nocturno procedural para videos de dormir.

Genera un clip base corto (por defecto 30 s) con movimiento mínimo e
hipnótico, pantalla oscura y ambiente nocturno, a partir de un preset de
config/presets.yaml (sleep.*). El clip se hace luego "loopeable" y se repite
de forma eficiente en create_sleep_video.py (no se renderizan 5h55 de píxeles
nuevos).

Presets soportados: ocean_night, black_screen, ocean_bubbles.
Arquitectura preparada para: rain_dark, forest_dark, stars_dark, cloud_dark.

Uso directo (para pruebas del visual):
    python scripts/sleep_visual.py --preset ocean_night --duration 20 \
        --output video/intermediate/ocean_night_base.mp4
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.ffmpeg_utils import check_ffmpeg, run_ffmpeg  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402

log = get_logger("sleep_visual")

# Presets con soporte visual real hoy.
IMPLEMENTED = {"ocean_night", "black_screen", "ocean_bubbles"}


def _preset(name):
    presets = (config.PRESETS.get("sleep", {}) or {})
    if name not in presets:
        raise ValueError(f"Preset desconocido: {name}. Disponibles: "
                         f"{sorted(k for k in presets if not k.startswith('_'))}")
    if name not in IMPLEMENTED:
        raise ValueError(f"Preset '{name}' aún no tiene motor visual implementado.")
    return presets[name]


def _make_moon_png(dst, size=280):
    """Crea un resplandor lunar suave (PNG RGBA) con Pillow (una sola vez)."""
    from PIL import Image
    dst = Path(dst)
    if dst.exists():
        return dst
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    cx = cy = size / 2
    r = size / 2
    for y in range(size):
        for x in range(size):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / r
            if d >= 1:
                continue
            # Núcleo brillante que decae suavemente hacia el borde.
            a = max(0.0, 1.0 - d) ** 2.4
            val = int(255 * a)
            px[x, y] = (245, 245, 220, int(200 * a))  # blanco cálido tenue
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "PNG")
    return dst


def build_from_image(image, out, duration=30, size=None, fps=None,
                     motion="water", zoom_amp=0.035, horizon=0.45,
                     logger=None, cache_dir=None):
    """
    Crea un clip base a partir de una imagen fija con MOVIMIENTO MÍNIMO.

    motion="water" (por defecto): el cielo y la luna quedan QUIETOS y solo la
      zona del mar ondula/brilla, mediante un desplazamiento de agua sutil
      (filtro displace con mapas animados), enmascarado por debajo del
      horizonte. Da sensación de mar vivo sin animación agresiva.
    motion="zoom": un zoom sinusoidal muy lento (la escena entera "respira").

    `horizon` es la fracción de altura donde empieza el mar (0=arriba, 1=abajo).
    Devuelve out.
    """
    check_ffmpeg()
    logger = logger or log
    vp = config.video_preset()
    w = size[0] if size else vp.get("width", 1920)
    h = size[1] if size else vp.get("height", 1080)
    fps = fps or vp.get("fps", 30)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if motion == "zoom":
        frames = max(1, int(round(duration * fps)))
        cw, ch = int(w * 1.2), int(h * 1.2)
        vf = (
            f"scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},"
            f"zoompan=z='1.06+{zoom_amp}*sin(on*2*PI/{frames})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps},"
            f"format=yuv420p"
        )
        run_ffmpeg([
            "-loop", "1", "-i", str(image), "-vf", vf, "-t", str(duration),
            "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-g", str(fps * 2), out,
        ], logger=logger)
        return out

    # --- motion == "water": desplazamiento de agua bajo el horizonte ---
    y0 = int(h * horizon)          # inicio del mar
    span = max(1, h - y0)          # alto de la zona de mar
    mask = f"clip((Y-{y0})/{span}\\,0\\,1)"   # 0 en el cielo, 1 abajo
    # Mapas de desplazamiento animados (128 = sin desplazar; ±px suave).
    xexpr = (f"128 + 9*sin(Y/10 + T*1.2)*{mask} + 5*sin(X/48 + T*0.7)*{mask}")
    yexpr = (f"128 + 6*sin(X/18 - T*1.0)*{mask}")
    graph = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},format=rgb24[bg];\n"
        f"color=c=black:s={w}x{h}:r={fps},"
        f"geq=lum='{xexpr}':cb=128:cr=128,format=gray[xm];\n"
        f"color=c=black:s={w}x{h}:r={fps},"
        f"geq=lum='{yexpr}':cb=128:cr=128,format=gray[ym];\n"
        f"[bg][xm][ym]displace=edge=smear,format=yuv420p[v]"
    )
    cache_dir = Path(cache_dir) if cache_dir else out.parent
    cache_dir.mkdir(parents=True, exist_ok=True)
    script = cache_dir / f"_water_{out.stem}.txt"
    script.write_text(graph, encoding="utf-8")
    run_ffmpeg([
        "-loop", "1", "-t", str(duration), "-i", str(image),
        "-filter_complex_script", str(script), "-map", "[v]",
        "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-g", str(fps * 2), out,
    ], logger=logger)
    return out


def generate_visual(preset_name, out, duration=30, size=None, fps=None,
                    logger=None):
    """Genera el clip base procedural del preset. Devuelve la ruta out."""
    check_ffmpeg()
    logger = logger or log
    p = _preset(preset_name)
    vp = config.video_preset()
    w = (size or (vp.get("width", 1920), vp.get("height", 1080)))[0] if size else vp.get("width", 1920)
    h = size[1] if size else vp.get("height", 1080)
    fps = fps or vp.get("fps", 30)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # ---- black_screen: pantalla casi negra, estática ----
    if preset_name == "black_screen":
        run_ffmpeg([
            "-f", "lavfi", "-i", f"color=c=0x010204:s={w}x{h}:r={fps}:d={duration}",
            "-t", str(duration), "-c:v", "libx264", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-g", str(fps * 2), out,
        ], logger=logger)
        return out

    # ---- ocean_night / ocean_bubbles: campo oscuro animado + luna + grano ----
    b = p.get("brightness", 0.08)
    s = p.get("saturation", 0.35)
    c = p.get("contrast", 0.85)
    speed = p.get("motion_speed", 0.10) * 0.02          # muy lento
    grain = round((p.get("particle_density", 0.05)
                   + p.get("bubble_density", 0.08)) * 12, 2)  # partículas sutiles

    # Campo "agua" oscuro: gradiente vertical de azules casi negros, animado.
    grad = (f"gradients=s={w}x{h}:c0=0x00030a:c1=0x06101f:c2=0x0a1a33:"
            f"c3=0x01050d:x0=0:y0={h}:x1={w}:y1=0:d={duration}:speed={speed}:"
            f"n=4:r={fps}")

    chain = (f"[0:v]eq=brightness={b}:saturation={s}:contrast={c},"
             f"gblur=sigma=6,vignette=PI/4.5")
    if grain > 0:
        chain += f",noise=alls={grain}:allf=t+u"
    chain += "[w]"

    inputs = ["-f", "lavfi", "-i", grad]
    if p.get("moon", False):
        moon = _make_moon_png(config.CACHE_DIR / "moon.png")
        inputs += ["-loop", "1", "-i", str(moon)]
        filtro = (f"{chain};[1:v]format=rgba,gblur=sigma=6[m];"
                  f"[w][m]overlay=x={int(w * 0.60)}:y={int(h * 0.10)}:"
                  f"format=auto,format=yuv420p[v]")
    else:
        filtro = f"{chain},format=yuv420p[v]"

    run_ffmpeg([
        *inputs, "-filter_complex", filtro, "-map", "[v]", "-t", str(duration),
        "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-g", str(fps * 2), out,
    ], logger=logger)
    return out


def main():
    ap = argparse.ArgumentParser(description="Genera un visual nocturno procedural.")
    ap.add_argument("--preset", default="ocean_night")
    ap.add_argument("--duration", type=float, default=30)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    try:
        generate_visual(args.preset, args.output, duration=args.duration)
        log.info("OK visual -> %s", args.output)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
