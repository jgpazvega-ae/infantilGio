"""
generate_audio.py — Narración con ElevenLabs (Fase 2).

Lee un cuento (.txt / .md, con o sin front-matter), genera la narración con
ElevenLabs y la guarda en audio/narration/<slug>.mp3.

- Valida API key y voice_id (sin exponer la clave).
- Trocea textos largos y concatena los fragmentos.
- No regenera si el audio ya existe y es válido (usa --force para forzar).
- Registra duración y errores en logs/.

Uso:
    python scripts/generate_audio.py content/stories/andre.txt
    python scripts/generate_audio.py andre --force --voice-id XXXX
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.chunking import split_text  # noqa: E402
from core.ffmpeg_utils import get_duration  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from core.paths import slugify  # noqa: E402
from core.story import parse_story_file  # noqa: E402

log = get_logger("generate_audio")


def _resolve_story(ref):
    """Acepta ruta completa o nombre dentro de content/stories/."""
    ref = Path(ref)
    if ref.exists():
        return ref
    for cand in (config.STORIES_DIR / ref.name,
                 (config.STORIES_DIR / ref.name).with_suffix(".txt"),
                 (config.STORIES_DIR / ref.name).with_suffix(".md")):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No se encontró el cuento: {ref}")


def _voice_settings():
    return (config.VOICES.get("narrator", {}) or {}).get("settings", {})


def _is_valid_audio(path):
    try:
        return path.exists() and get_duration(path) > 0
    except Exception:  # noqa: BLE001
        return False


def generate_audio(story_ref, voice_id=None, force=False, dry_run=False):
    """Genera la narración. Devuelve la ruta del mp3 (o la esperada en dry-run)."""
    ruta = _resolve_story(story_ref)
    meta = parse_story_file(ruta)
    texto = meta["story"]
    if not texto.strip():
        raise ValueError(f"El cuento {ruta} no tiene texto.")

    config.ensure_dirs()
    slug = slugify(meta["title"]) if meta.get("title") else slugify(ruta.stem)
    destino = config.NARRATION_DIR / f"{slug}.mp3"

    max_chars = config.VOICES.get("max_chars_per_request", 2500)
    fragmentos = split_text(texto, max_chars)

    if dry_run:
        log.info("[dry-run] Generaría %s (%d fragmentos, %d caracteres) -> %s",
                 ruta.name, len(fragmentos), len(texto), destino)
        return destino

    # Checkpoint: si la narración ya existe y es válida, NO se regenera (ni se
    # requiere API key). Así se puede rehacer solo una etapa posterior.
    if destino.exists() and _is_valid_audio(destino) and not force:
        log.info("Ya existe y es válido: %s (usa --force para regenerar)", destino)
        return destino

    # A partir de aquí sí hace falta llamar a ElevenLabs.
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError(
            "Falta ELEVENLABS_API_KEY. Copia .env.example a .env y añade tu clave."
        )
    voice_id = voice_id or config.NARRATOR_VOICE_ID
    if not voice_id:
        raise RuntimeError("No hay voice_id (define narrator.voice_id o ELEVENLABS_VOICE_ID).")

    from elevenlabs.client import ElevenLabs  # import perezoso
    cliente = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    settings = _voice_settings()
    model_id = config.VOICES.get("model_id", "eleven_multilingual_v2")
    out_fmt = config.VOICES.get("output_format", "mp3_44100_128")

    log.info("Narración: %s | %d caracteres | %d fragmento(s) | voz=%s",
             ruta.name, len(texto), len(fragmentos), voice_id)

    partes = []
    for i, frag in enumerate(fragmentos, start=1):
        log.info("Fragmento %d/%d (%d caracteres)...", i, len(fragmentos), len(frag))
        try:
            stream = cliente.text_to_speech.convert(
                voice_id=voice_id, model_id=model_id, output_format=out_fmt,
                text=frag, voice_settings=settings or None,
            )
            partes.append(b"".join(stream))
        except Exception as exc:  # noqa: BLE001
            log.error("Fallo en fragmento %d: %s", i, exc)
            raise RuntimeError(f"Error de ElevenLabs en el fragmento {i}: {exc}") from exc

    with open(destino, "wb") as f:
        for p in partes:
            f.write(p)

    dur = get_duration(destino)
    log.info("OK narración -> %s | duración=%.1fs", destino, dur)
    return destino


def main():
    ap = argparse.ArgumentParser(description="Genera narración con ElevenLabs.")
    ap.add_argument("story", help="Ruta o nombre del cuento (content/stories/)")
    ap.add_argument("--voice-id", default=None, help="voice_id (sobrescribe config)")
    ap.add_argument("--force", action="store_true", help="Regenera aunque exista")
    ap.add_argument("--dry-run", action="store_true", help="Muestra sin generar")
    args = ap.parse_args()
    try:
        generate_audio(args.story, voice_id=args.voice_id, force=args.force,
                       dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
