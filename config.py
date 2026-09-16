"""
Configuración central del proyecto.

Aquí se definen rutas, parámetros de voz, resolución de salida y demás
ajustes reutilizados por todos los scripts. No se hardcodean rutas
absolutas: todo se calcula relativo a la raíz del proyecto (BASE_DIR).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env (si existe)
load_dotenv()

# ---------------------------------------------------------------------------
# Rutas del proyecto (todas relativas a la raíz)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

STORIES_DIR = BASE_DIR / "stories"            # Textos de los cuentos (.txt)
FOOTAGE_DIR = BASE_DIR / "footage"            # Clips de video base
NARRATION_DIR = BASE_DIR / "audio" / "narration"  # Audio narrado generado
AMBIENT_DIR = BASE_DIR / "audio" / "ambient"      # Sonido ambiental
OUTPUT_DIR = BASE_DIR / "output"              # Videos finales
LOOPS_DIR = OUTPUT_DIR / "loops"              # Loops de footage
THUMBNAILS_DIR = BASE_DIR / "thumbnails"      # Miniaturas
ASSETS_DIR = BASE_DIR / "assets"              # Recursos (fuentes, etc.)
FONTS_DIR = ASSETS_DIR / "fonts"

# Directorios que deben existir siempre
_REQUIRED_DIRS = [
    STORIES_DIR,
    FOOTAGE_DIR,
    NARRATION_DIR,
    AMBIENT_DIR,
    OUTPUT_DIR,
    LOOPS_DIR,
    THUMBNAILS_DIR,
    FONTS_DIR,
]


def ensure_dirs():
    """Crea los directorios del proyecto si no existen."""
    for directory in _REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# ElevenLabs (text-to-speech)
# ---------------------------------------------------------------------------
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# voice_id de la voz narradora. Se puede sobrescribir con la variable de
# entorno ELEVENLABS_VOICE_ID. Por defecto usamos "Sofia - Captivating
# Narration": voz femenina española, cálida, suave y dulce, ideal para
# narración de cuentos antes de dormir.
#
# Alternativas cálidas/suaves en español (cambia DEFAULT_VOICE_ID por una):
#   - Sofia  (femenina, dulce, storytelling) : pN4aFdNIp2mvGfTwy1Oj  [por defecto]
#   - Alma   (femenina, envolvente, wellness) : 8gK5gnQBZnJWm1ta8R8X
#   - Mario C. (masculina, calmada y sabia)   : crXOIS13NaTVLeuWd3Dp
#   - Andre  (masculina, pausada, envolvente) : K7vlllngMGapgRQRDsqK
# Explora más en https://elevenlabs.io/app/voice-library
DEFAULT_VOICE_ID = "pN4aFdNIp2mvGfTwy1Oj"  # Sofia - Captivating Narration
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

# Modelo de TTS. "eleven_multilingual_v2" soporta español con buena calidad.
TTS_MODEL_ID = "eleven_multilingual_v2"
TTS_OUTPUT_FORMAT = "mp3_44100_128"  # 44.1 kHz, 128 kbps

# Ajustes de voz orientados a una narración infantil suave y lenta para dormir.
# - stability alto  -> entonación más estable y calmada
# - similarity_boost alto -> se mantiene fiel al timbre de la voz
# - style bajo -> menos dramatismo, tono más neutro y relajante
# - speed < 1.0 -> ritmo más lento (soportado por el modelo)
VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 0.9,
}

# Límite de caracteres por petición. La API acepta bastante más, pero
# troceamos en fragmentos manejables para textos largos y para poder
# reintentar por partes si algo falla.
TTS_MAX_CHARS = 2500

# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

# Volúmenes de mezcla en el ensamblado de video.
NARRATION_VOLUME = 1.0    # Narración al 100%
AMBIENT_VOLUME = 0.18     # Ambiente al ~18% (entre 15-20%)

# Duración objetivo por defecto para los loops de dormir, en segundos.
# 5 horas y 55 minutos = 21300 s (según la petición del proyecto).
DEFAULT_LOOP_SECONDS = 5 * 3600 + 55 * 60  # 21300

# Sonido ambiental por defecto (el audio del mar aportado en el proyecto).
DEFAULT_AMBIENT_FILE = AMBIENT_DIR / "ambient_mar.mp3"

# Duración del crossfade (en segundos) para hacer loops "perfectos" con xfade.
LOOP_XFADE_SECONDS = 2

# ---------------------------------------------------------------------------
# Miniaturas
# ---------------------------------------------------------------------------
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720

# Fuente para el título de la miniatura. Si no existe el archivo, el script
# cae a la fuente por defecto de Pillow.
THUMB_FONT_PATH = FONTS_DIR / "title.ttf"
THUMB_FONT_SIZE = 90
THUMB_TEXT_COLOR = (255, 255, 255)      # Blanco
THUMB_STROKE_COLOR = (0, 0, 0)          # Contorno negro para legibilidad
THUMB_STROKE_WIDTH = 6
