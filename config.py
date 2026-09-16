"""
Configuración central de infantilGio.

Carga variables de entorno (.env) y los archivos YAML de config/, y expone
las rutas del proyecto (todas relativas a BASE_DIR, sin rutas absolutas
hardcodeadas). Nunca imprime ni expone la API key.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Rutas base del proyecto
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"

CONTENT_DIR = BASE_DIR / "content"
IDEAS_DIR = CONTENT_DIR / "ideas"
STORIES_DIR = CONTENT_DIR / "stories"
SCRIPTS_CONTENT_DIR = CONTENT_DIR / "scripts"
SCENE_PLANS_DIR = CONTENT_DIR / "scene_plans"
METADATA_DIR = CONTENT_DIR / "metadata"

ASSETS_DIR = BASE_DIR / "assets"
FOOTAGE_DIR = ASSETS_DIR / "footage"
MUSIC_DIR = ASSETS_DIR / "music"
ASSETS_AMBIENT_DIR = ASSETS_DIR / "ambient"
IMAGES_DIR = ASSETS_DIR / "images"
CHARACTERS_ASSETS_DIR = ASSETS_DIR / "characters"
FONTS_DIR = ASSETS_DIR / "fonts"

AUDIO_DIR = BASE_DIR / "audio"
NARRATION_DIR = AUDIO_DIR / "narration"
AUDIO_CHARACTERS_DIR = AUDIO_DIR / "characters"
AUDIO_AMBIENT_DIR = AUDIO_DIR / "ambient"
AUDIO_FINAL_DIR = AUDIO_DIR / "final"

VIDEO_DIR = BASE_DIR / "video"
VIDEO_SCENES_DIR = VIDEO_DIR / "scenes"
VIDEO_INTERMEDIATE_DIR = VIDEO_DIR / "intermediate"
VIDEO_FINAL_DIR = VIDEO_DIR / "final"

THUMBNAILS_DIR = BASE_DIR / "thumbnails"

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_STORIES_DIR = OUTPUT_DIR / "stories"
OUTPUT_SLEEP_DIR = OUTPUT_DIR / "sleep"
PACKAGES_DIR = OUTPUT_DIR / "packages"

LOGS_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"

_ALL_DIRS = [
    IDEAS_DIR, STORIES_DIR, SCRIPTS_CONTENT_DIR, SCENE_PLANS_DIR, METADATA_DIR,
    FOOTAGE_DIR, MUSIC_DIR, ASSETS_AMBIENT_DIR, IMAGES_DIR,
    CHARACTERS_ASSETS_DIR, FONTS_DIR,
    NARRATION_DIR, AUDIO_CHARACTERS_DIR, AUDIO_AMBIENT_DIR, AUDIO_FINAL_DIR,
    VIDEO_SCENES_DIR, VIDEO_INTERMEDIATE_DIR, VIDEO_FINAL_DIR,
    THUMBNAILS_DIR,
    OUTPUT_STORIES_DIR, OUTPUT_SLEEP_DIR, PACKAGES_DIR,
    LOGS_DIR, CACHE_DIR,
]


def ensure_dirs():
    """Crea todos los directorios del proyecto si no existen (idempotente)."""
    for directory in _ALL_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Carga de YAML
# ---------------------------------------------------------------------------
def _load_yaml(name):
    ruta = CONFIG_DIR / name
    if not ruta.exists():
        return {}
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


VOICES = _load_yaml("voices.yaml")
CHANNELS = _load_yaml("channels.yaml")
STYLES = _load_yaml("styles.yaml")
PRESETS = _load_yaml("presets.yaml")

# ---------------------------------------------------------------------------
# Secretos (desde entorno; NUNCA se imprimen)
# ---------------------------------------------------------------------------
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# voice_id efectivo: la variable de entorno tiene prioridad sobre voices.yaml.
_env_voice = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
NARRATOR_VOICE_ID = _env_voice or VOICES.get("narrator", {}).get("voice_id", "")


# ---------------------------------------------------------------------------
# Accesos rápidos a presets (con valores por defecto seguros)
# ---------------------------------------------------------------------------
def video_preset():
    return PRESETS.get("video", {})


def audio_preset():
    return PRESETS.get("audio", {})


def loop_preset():
    return PRESETS.get("loop", {})


def thumbnail_style():
    return STYLES.get("thumbnail", {})


def default_channel():
    key = CHANNELS.get("default_channel")
    return CHANNELS.get("channels", {}).get(key, {})
