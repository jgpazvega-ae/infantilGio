"""
Tests básicos de infantilGio.

Ejecutar con:  python -m pytest -q
           o:  python tests/test_core.py   (runner integrado, sin pytest)

Cubren: duración, paths/slug, chunking, manifest, metadata, scene plan,
story y lógica de QC. No requieren ffmpeg ni red.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.chunking import split_text
from core.ffmpeg_utils import (format_duration, format_duration_compact,
                               parse_duration)
from core.manifest import Manifest, ProductionState
from core.metadata import build_metadata
from core.paths import slugify
from core.qc import QCResult
from core.scene_plan import build_scene_plan
from core.story import (estimate_duration_minutes, generate_story_from_params,
                        parse_story_file)


def test_parse_duration():
    assert parse_duration("05:55:00") == 21300
    assert parse_duration("01:00:00") == 3600
    assert parse_duration("90m") == 5400
    assert parse_duration("30s") == 30
    assert parse_duration("2h") == 7200
    assert parse_duration("300") == 300
    assert parse_duration(120) == 120


def test_format_duration():
    assert format_duration(21300) == "05:55:00"
    assert format_duration(3661) == "01:01:01"
    assert format_duration_compact(21300) == "5h55m00s"


def test_slugify():
    assert slugify("André y el Tren de las Estrellas") == "andre-y-el-tren-de-las-estrellas"
    assert slugify("  ¡Hola, Mundo!  ") == "hola-mundo"
    assert slugify("") == "sin-titulo"


def test_split_text_short():
    assert split_text("Hola mundo.", 2500) == ["Hola mundo."]
    assert split_text("", 2500) == []


def test_split_text_long_respects_limit():
    texto = ("Frase de prueba. " * 400).strip()
    chunks = split_text(texto, 500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # No debe partir palabras: cada chunk empieza/termina en carácter no vacío.
    assert all(c == c.strip() for c in chunks)


def test_split_text_paragraph_boundaries():
    texto = "Parrafo uno.\n\nParrafo dos.\n\nParrafo tres."
    chunks = split_text(texto, 20)
    assert len(chunks) == 3


def test_manifest_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "manifest.json"
        m = Manifest.create(path, "andre", "story")
        m.set_artifact("video", "video.mp4")
        m.advance_state(ProductionState.VIDEO_READY)
        m.set_quality("PASS")
        m.advance_state(ProductionState.QC_PASSED)
        m.save()
        loaded = Manifest.load(path)
        assert loaded.get_artifact("video") == "video.mp4"
        assert loaded.data["quality_check"] == "PASS"
        assert loaded.data["state"] == ProductionState.QC_PASSED


def test_manifest_state_monotonic():
    with tempfile.TemporaryDirectory() as d:
        m = Manifest.create(Path(d) / "m.json", "x", "sleep")
        m.advance_state(ProductionState.VIDEO_READY)
        m.advance_state(ProductionState.IDEA)  # no debe retroceder
        assert m.data["state"] == ProductionState.VIDEO_READY


def test_metadata_no_spam_and_tags():
    channel = {"category": "education", "language": "es-MX",
               "default_hashtags": ["#cuentos"], "signature": "Suscríbete"}
    story_meta = {"story": "Había una vez una ballena azul en el mar tranquilo.",
                  "genre": "bedtime", "theme": "calma", "age_range": "2-5"}
    meta = build_metadata("story", "La Ballena Azul", channel, story_meta=story_meta,
                          duration_seconds=480)
    assert "Cuento para Dormir" in meta["title"]
    assert len(meta["title"]) <= 100
    assert meta["tags"], "debe haber tags"
    assert meta["language"] == "es-MX"
    assert "Edad recomendada" in meta["description"]


def test_scene_plan():
    story_meta = {"story": "Parrafo uno con contenido.\n\nParrafo dos mas largo aun."}
    plan = build_scene_plan(story_meta, narration_seconds=100)
    assert len(plan["scenes"]) == 2
    # Los tiempos deben ser crecientes y cubrir la duración.
    assert plan["scenes"][0]["start"] == 0
    assert abs(plan["scenes"][-1]["end"] - 100) < 1


def test_story_template_and_parse():
    meta = generate_story_from_params("Cuento Test", character="Luna", theme="calma")
    assert meta["title"] == "Cuento Test"
    assert "Luna" in meta["story"]
    assert meta["target_duration_minutes"] > 0

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.md"
        p.write_text("---\ntitle: Mi Cuento\ngenre: adventure\n---\n\nHabía una vez.",
                     encoding="utf-8")
        parsed = parse_story_file(p)
        assert parsed["title"] == "Mi Cuento"
        assert parsed["genre"] == "adventure"
        assert parsed["story"] == "Había una vez."


def test_estimate_duration():
    assert estimate_duration_minutes("palabra " * 130) == 1.0
    assert estimate_duration_minutes("") == 0.0


def test_qc_result_logic():
    r = QCResult()
    r.add("Audio", True, "ok")
    r.add("Video", True)
    assert r.passed and r.status == "PASS"
    r.add("Thumbnail", False, "falta")
    assert not r.passed and r.status == "FAILED"
    assert "FAIL" in r.render()


# --- Runner integrado (sin pytest) ---------------------------------------
def _run_all():
    funcs = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fallos = 0
    for f in funcs:
        try:
            f()
            print(f"[PASS] {f.__name__}")
        except Exception as exc:  # noqa: BLE001
            fallos += 1
            print(f"[FAIL] {f.__name__}: {exc}")
    print(f"\n{len(funcs) - fallos}/{len(funcs)} tests OK")
    return fallos


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
