"""
Control de calidad automático.

Verifica audio, video, thumbnail y package. Devuelve un resultado estructurado
con estado global PASS/FAILED y el detalle de cada comprobación.
"""

from pathlib import Path

from core.ffmpeg_utils import get_duration, get_stream, probe


class Check:
    def __init__(self, name, passed, detail=""):
        self.name = name
        self.passed = passed
        self.detail = detail


class QCResult:
    def __init__(self):
        self.checks = []

    def add(self, name, passed, detail=""):
        self.checks.append(Check(name, bool(passed), detail))
        return passed

    @property
    def passed(self):
        return all(c.passed for c in self.checks) and bool(self.checks)

    @property
    def status(self):
        return "PASS" if self.passed else "FAILED"

    def render(self):
        lines = ["QUALITY CHECK"]
        for c in self.checks:
            tag = "PASS" if c.passed else "FAIL"
            extra = f" — {c.detail}" if c.detail else ""
            lines.append(f"[{tag}] {c.name}{extra}")
        lines.append(f"STATUS: {self.status}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "status": self.status,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


def check_audio(result, path, prefix="Audio"):
    """Verifica existencia, legibilidad, duración > 0, sample rate y canales."""
    path = Path(path) if path else None
    if not path or not path.exists():
        result.add(prefix, False, "no existe")
        return
    try:
        stream = get_stream(path, "audio")
        dur = get_duration(path)
    except Exception as exc:  # noqa: BLE001
        result.add(prefix, False, f"no legible: {exc}")
        return
    if stream is None:
        result.add(prefix, False, "sin stream de audio")
        return
    sr = int(stream.get("sample_rate", 0) or 0)
    ch = int(stream.get("channels", 0) or 0)
    ok = dur > 0 and sr > 0 and ch > 0
    result.add(prefix, ok, f"dur={dur:.1f}s sr={sr} ch={ch}")


def check_video(result, path, exp_w=1920, exp_h=1080, exp_fps=30,
                exp_duration=None, tolerance=3.0, prefix="Video"):
    """Verifica MP4 válido, resolución, fps, codec, audio presente y duración."""
    path = Path(path) if path else None
    if not path or not path.exists():
        result.add(prefix, False, "no existe")
        return
    try:
        info = probe(path)
        v = get_stream(path, "video")
        a = get_stream(path, "audio")
        dur = get_duration(path)
    except Exception as exc:  # noqa: BLE001
        result.add(prefix, False, f"no legible: {exc}")
        return
    if v is None:
        result.add(prefix, False, "sin stream de video")
        return

    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    result.add(f"{prefix}: resolución", w == exp_w and h == exp_h, f"{w}x{h}")

    # FPS (avg_frame_rate viene como "30/1")
    fps_raw = v.get("avg_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    result.add(f"{prefix}: fps", abs(fps - exp_fps) < 1.0, f"{fps:.2f}")

    codec = v.get("codec_name", "?")
    result.add(f"{prefix}: codec", codec in ("h264", "hevc", "vp9"), codec)
    result.add(f"{prefix}: audio presente", a is not None,
               a.get("codec_name") if a else "ausente")
    result.add(f"{prefix}: MP4", "mp4" in info.get("format", {}).get("format_name", ""),
               info.get("format", {}).get("format_name", "?"))

    if exp_duration is not None:
        ok = abs(dur - exp_duration) <= tolerance
        result.add(f"{prefix}: duración", ok,
                   f"{dur:.1f}s (esperado ~{exp_duration:.1f}s)")


def check_thumbnail(result, path, exp_w=1280, exp_h=720, prefix="Thumbnail"):
    """Verifica existencia, formato y dimensiones 1280x720."""
    path = Path(path) if path else None
    if not path or not path.exists():
        result.add(prefix, False, "no existe")
        return
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            fmt = im.format
    except Exception as exc:  # noqa: BLE001
        result.add(prefix, False, f"no válido: {exc}")
        return
    result.add(prefix, w == exp_w and h == exp_h, f"{w}x{h} {fmt}")


def check_package(result, metadata):
    """Verifica que la metadata tenga título, descripción y tags."""
    if not metadata:
        result.add("Metadata", False, "ausente")
        return
    result.add("Metadata: título", bool(metadata.get("title")),
               (metadata.get("title") or "")[:40])
    result.add("Metadata: descripción", bool(metadata.get("description")))
    tags = metadata.get("tags") or []
    result.add("Metadata: tags", len(tags) > 0, f"{len(tags)} tags")
