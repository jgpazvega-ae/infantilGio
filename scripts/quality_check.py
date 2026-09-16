"""
quality_check.py — Control de calidad (Fase 8).

Verifica audio, video, thumbnail y metadata de una producción y reporta
PASS/FAILED con detalle. Puede recibir rutas sueltas o un package.

Uso:
    python scripts/quality_check.py --video video/final/andre.mp4 \
        --thumbnail thumbnails/andre.jpg --metadata content/metadata/andre.json
    python scripts/quality_check.py --package output/packages/andre/
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.ffmpeg_utils import check_ffmpeg  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.qc import (QCResult, check_audio, check_package,  # noqa: E402
                     check_thumbnail, check_video)

log = get_logger("quality_check")


def run_qc(video=None, audio=None, thumbnail=None, metadata=None,
           package=None, exp_duration=None):
    """Ejecuta el QC y devuelve un QCResult."""
    check_ffmpeg()
    vp = config.video_preset()

    if package:
        pkg = Path(package)
        video = video or _first(pkg, ("video.mp4",))
        thumbnail = thumbnail or _first(pkg, ("thumbnail.jpg", "thumbnail.png"))
        mfile = _first(pkg, ("metadata.json",))
        metadata = metadata or (json.loads(Path(mfile).read_text(encoding="utf-8")) if mfile else None)

    result = QCResult()
    if audio:
        check_audio(result, audio)
    if video:
        check_video(result, video, exp_w=vp.get("width", 1920),
                    exp_h=vp.get("height", 1080), exp_fps=vp.get("fps", 30),
                    exp_duration=exp_duration)
    if thumbnail:
        check_thumbnail(result, thumbnail)
    if metadata is not None:
        if isinstance(metadata, (str, Path)):
            metadata = json.loads(Path(metadata).read_text(encoding="utf-8"))
        check_package(result, metadata)
    return result


def _first(folder, names):
    for n in names:
        p = Path(folder) / n
        if p.exists():
            return str(p)
    return None


def main():
    ap = argparse.ArgumentParser(description="Control de calidad de una producción.")
    ap.add_argument("--video", default=None)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--thumbnail", default=None)
    ap.add_argument("--metadata", default=None)
    ap.add_argument("--package", default=None)
    ap.add_argument("--expected-duration", type=float, default=None)
    args = ap.parse_args()
    try:
        result = run_qc(video=args.video, audio=args.audio, thumbnail=args.thumbnail,
                        metadata=args.metadata, package=args.package,
                        exp_duration=args.expected_duration)
        print(result.render())
        sys.exit(0 if result.passed else 2)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
