"""
Fase 2 — Generación de narración con ElevenLabs.

Toma un cuento en texto (.txt) de la carpeta stories/, lo convierte a voz
con ElevenLabs usando el voice_id configurado en config.py, y guarda el
resultado como .mp3 en audio/narration/ con el mismo nombre base.

Uso:
    python scripts/generate_audio.py stories/mi_cuento.txt
    python scripts/generate_audio.py mi_cuento          # busca en stories/
    python scripts/generate_audio.py mi_cuento --voice-id <VOICE_ID>

Los textos largos se dividen automáticamente en fragmentos para respetar el
límite de caracteres de la API; los fragmentos se concatenan en un único mp3.
"""

import argparse
import re
import sys
from pathlib import Path

# Permite ejecutar el script directamente (python scripts/generate_audio.py)
# añadiendo la raíz del proyecto al path para importar config.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def dividir_en_fragmentos(texto, max_chars):
    """
    Divide el texto en fragmentos de como máximo `max_chars` caracteres,
    intentando cortar en límites naturales (párrafos y frases) para no partir
    palabras ni frases a la mitad.
    """
    texto = texto.strip()
    if len(texto) <= max_chars:
        return [texto]

    # Primero por párrafos, luego por frases si un párrafo es muy largo.
    unidades = re.split(r"\n\s*\n", texto)
    fragmentos = []
    actual = ""

    def emitir():
        nonlocal actual
        if actual.strip():
            fragmentos.append(actual.strip())
        actual = ""

    for unidad in unidades:
        unidad = unidad.strip()
        if not unidad:
            continue
        # Si la unidad por sí sola supera el límite, la partimos por frases.
        if len(unidad) > max_chars:
            frases = re.split(r"(?<=[.!?…])\s+", unidad)
            for frase in frases:
                if len(actual) + len(frase) + 1 > max_chars:
                    emitir()
                # Frase individual descomunal: cortar en seco por longitud.
                while len(frase) > max_chars:
                    fragmentos.append(frase[:max_chars])
                    frase = frase[max_chars:]
                actual = (actual + " " + frase).strip() if actual else frase
        else:
            if len(actual) + len(unidad) + 2 > max_chars:
                emitir()
            actual = (actual + "\n\n" + unidad).strip() if actual else unidad

    emitir()
    return fragmentos


def _construir_voice_settings():
    """
    Construye el objeto VoiceSettings del SDK a partir de config.VOICE_SETTINGS,
    ignorando de forma segura los campos que la versión instalada no soporte
    (por ejemplo `speed` en versiones antiguas).
    """
    from elevenlabs import VoiceSettings

    campos = dict(config.VOICE_SETTINGS)
    try:
        return VoiceSettings(**campos)
    except TypeError:
        # Reintenta sin las claves no soportadas por esta versión del SDK.
        campos.pop("speed", None)
        campos.pop("use_speaker_boost", None)
        campos.pop("style", None)
        return VoiceSettings(**campos)


def generar_audio(ruta_txt, voice_id=None):
    """
    Genera el mp3 de narración para un archivo de texto dado.

    Devuelve la ruta del mp3 generado. Lanza excepciones claras si falta la
    API key, el archivo de texto o si la API falla.
    """
    # 1. Validar credenciales
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError(
            "Falta ELEVENLABS_API_KEY. Copia .env.example a .env y añade tu "
            "clave de API de ElevenLabs."
        )

    # 2. Resolver la ruta del texto (acepta ruta completa o solo el nombre)
    ruta_txt = Path(ruta_txt)
    if not ruta_txt.exists():
        candidato = config.STORIES_DIR / ruta_txt.name
        if candidato.suffix == "":
            candidato = candidato.with_suffix(".txt")
        if candidato.exists():
            ruta_txt = candidato
        else:
            raise FileNotFoundError(
                f"No se encontró el cuento: {ruta_txt} (ni en {config.STORIES_DIR})"
            )

    texto = ruta_txt.read_text(encoding="utf-8").strip()
    if not texto:
        raise ValueError(f"El archivo {ruta_txt} está vacío.")

    voice_id = voice_id or config.VOICE_ID

    # 3. Preparar cliente y ajustes
    from elevenlabs.client import ElevenLabs

    cliente = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    voice_settings = _construir_voice_settings()

    fragmentos = dividir_en_fragmentos(texto, config.TTS_MAX_CHARS)
    print(
        f"Cuento: {ruta_txt.name} | {len(texto)} caracteres | "
        f"{len(fragmentos)} fragmento(s) | voz: {voice_id}"
    )

    # 4. Convertir cada fragmento y acumular los bytes de audio
    partes_audio = []
    for i, fragmento in enumerate(fragmentos, start=1):
        print(f"  → Generando fragmento {i}/{len(fragmentos)} "
              f"({len(fragmento)} caracteres)...")
        try:
            audio_stream = cliente.text_to_speech.convert(
                voice_id=voice_id,
                model_id=config.TTS_MODEL_ID,
                output_format=config.TTS_OUTPUT_FORMAT,
                text=fragmento,
                voice_settings=voice_settings,
            )
            partes_audio.append(b"".join(audio_stream))
        except Exception as exc:  # noqa: BLE001 - queremos un mensaje claro
            raise RuntimeError(
                f"Error al generar el fragmento {i} con ElevenLabs: {exc}"
            ) from exc

    # 5. Guardar el mp3 final (concatenación de fragmentos)
    config.ensure_dirs()
    destino = config.NARRATION_DIR / (ruta_txt.stem + ".mp3")
    with open(destino, "wb") as f:
        for parte in partes_audio:
            f.write(parte)

    print(f"OK: narración guardada en {destino}")
    return destino


def main():
    parser = argparse.ArgumentParser(
        description="Genera narración mp3 con ElevenLabs a partir de un .txt"
    )
    parser.add_argument(
        "texto",
        help="Ruta al .txt (o nombre del cuento dentro de stories/)",
    )
    parser.add_argument(
        "--voice-id",
        default=None,
        help="voice_id de ElevenLabs a usar (sobrescribe config.py)",
    )
    args = parser.parse_args()

    try:
        generar_audio(args.texto, voice_id=args.voice_id)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
