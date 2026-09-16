# 🌙 Canal de Cuentos Infantiles + Loops para Dormir

Pipeline automatizado en Python para generar dos tipos de video para YouTube:

1. **Loops para dormir** — video de paisaje (mar, naturaleza) en bucle de
   1–6 horas con sonido ambiental (por defecto, **5 h 55 min**).
2. **Cuentos narrados** — cuento infantil corto narrado con voz de ElevenLabs
   sobre un fondo de video suave, con ambiente opcional de fondo.

El proyecto automatiza: generación de audio narrado, loop de footage,
ensamblado de video, generación de miniatura y (opcional) subida a YouTube.

---

## 📁 Estructura del proyecto

```
infantilGio/
├── stories/            # Textos de los cuentos (.txt)  → cuento_ejemplo.txt incluido
├── footage/            # Clips de video base (mar, naturaleza)
├── audio/
│   ├── narration/      # Narración generada por ElevenLabs
│   └── ambient/        # Sonido ambiental  → ambient_mar.mp3 incluido
├── output/             # Videos finales (cuentos)
│   └── loops/          # Videos de loop para dormir
├── thumbnails/         # Miniaturas 1280x720
├── assets/fonts/       # Fuente opcional para las miniaturas (title.ttf)
├── scripts/
│   ├── generate_audio.py    # Fase 2 — narración con ElevenLabs
│   ├── loop_footage.py      # Fase 3 — loop de footage (silencioso)
│   ├── make_sleep_loop.py   # Producto 1 — loop de dormir (video + ambiente)
│   ├── assemble_video.py    # Fase 4 — cuento: narración + footage + ambiente
│   ├── generate_thumbnail.py# Fase 5 — miniatura con título
│   ├── upload_youtube.py    # Fase 6 (opcional) — subida a YouTube
│   └── utils.py             # Utilidades compartidas (ffmpeg, duraciones)
├── config.py           # voice_id, rutas, resolución, duración por defecto...
├── requirements.txt
└── .env.example
```

---

## ⚙️ Instalación

### 1. Requisito del sistema: ffmpeg

`ffmpeg` (y `ffprobe`) deben estar instalados en el sistema:

- **Ubuntu/Debian:** `sudo apt update && sudo apt install ffmpeg`
- **macOS (Homebrew):** `brew install ffmpeg`
- **Windows (Chocolatey):** `choco install ffmpeg`
- O desde https://ffmpeg.org/download.html

Verifica con: `ffmpeg -version`

### 2. Entorno virtual e instalación de dependencias

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar la API key de ElevenLabs

```bash
cp .env.example .env
# Edita .env y añade tu clave:
# ELEVENLABS_API_KEY=tu_clave_aqui
```

La clave se obtiene en https://elevenlabs.io/app/settings/api-keys

### 4. (Opcional) Ajustar la voz

En `config.py` puedes cambiar `DEFAULT_VOICE_ID` por el `voice_id` de la voz
que prefieras (voz cálida, ritmo lento, tono suave para narración infantil).
También puedes sobrescribirlo con la variable `ELEVENLABS_VOICE_ID` en `.env`.

---

## 🚀 Uso (en orden de prioridad de construcción)

### 1️⃣ Generar narración (`generate_audio.py`)

```bash
python scripts/generate_audio.py cuento_ejemplo
# o con la ruta completa:
python scripts/generate_audio.py stories/cuento_ejemplo.txt
```

Genera `audio/narration/cuento_ejemplo.mp3`. Los textos largos se dividen
automáticamente en fragmentos y se concatenan.

### 2️⃣ Loop de footage — silencioso (`loop_footage.py`)

```bash
# 5 h 55 min (duración por defecto) a partir de tu clip del mar:
python scripts/loop_footage.py footage/mar.mp4

# Duración concreta + crossfade para un loop perfecto:
python scripts/loop_footage.py footage/mar.mp4 --hours 2 --xfade
```

Genera un mp4 1920x1080 @ 30 fps en `output/loops/`.

### 🌊 Loop para dormir completo — video + ambiente (`make_sleep_loop.py`)

Usa el audio ambiental (por defecto **`ambient_mar.mp3`**, ya incluido) en
bucle junto al footage para producir el video de dormir de **5 h 55 min**:

```bash
python scripts/make_sleep_loop.py --footage footage/mar.mp4
# duración personalizada:
python scripts/make_sleep_loop.py --footage footage/mar.mp4 --hours 3
```

Genera `output/loops/<nombre>_dormir_5h55m00s.mp4`.

### 3️⃣ Ensamblar cuento narrado (`assemble_video.py`)

```bash
# Narración (100%) + footage en loop + ambiente al ~18% de fondo:
python scripts/assemble_video.py cuento_ejemplo --footage footage/mar.mp4

# Sin ambiente de fondo:
python scripts/assemble_video.py cuento_ejemplo --footage footage/mar.mp4 --no-ambient
```

El footage se repite automáticamente hasta cubrir la duración de la narración.
Genera `output/cuento_ejemplo.mp4`.

### 4️⃣ Generar miniatura (`generate_thumbnail.py`)

```bash
# A partir de un frame del video final:
python scripts/generate_thumbnail.py --video output/cuento_ejemplo.mp4 \
    --titulo "La Ballena que Contaba Estrellas"

# A partir de una imagen fija:
python scripts/generate_thumbnail.py --imagen footage/portada.jpg \
    --titulo "La Ballena que Contaba Estrellas" --salida cuento_ejemplo
```

Genera una miniatura 1280x720 en `thumbnails/`. Para una tipografía más
amigable, coloca un `.ttf` en `assets/fonts/title.ttf`.

### 5️⃣ (Opcional) Subir a YouTube (`upload_youtube.py`)

Fase opcional, **no activada por defecto**. Requiere dependencias y
credenciales OAuth adicionales (ver la cabecera del script):

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

python scripts/upload_youtube.py --video output/cuento_ejemplo.mp4 \
    --titulo "La Ballena que Contaba Estrellas" \
    --descripcion "Un cuento suave para dormir." \
    --tags cuentos,dormir,infantil --categoria education --privacidad private
```

---

## 🔧 Configuración (`config.py`)

Parámetros principales que puedes ajustar:

| Parámetro | Descripción | Valor por defecto |
|---|---|---|
| `VOICE_ID` | Voz de ElevenLabs | Rachel (`21m00Tcm4TlvDq8ikWAM`) |
| `TTS_MODEL_ID` | Modelo TTS (multilingüe/español) | `eleven_multilingual_v2` |
| `VOICE_SETTINGS` | Estabilidad, estilo y velocidad (ritmo lento) | `speed=0.9` |
| `VIDEO_WIDTH/HEIGHT/FPS` | Resolución de salida | 1920×1080 @ 30 |
| `NARRATION_VOLUME` | Volumen de la narración | `1.0` |
| `AMBIENT_VOLUME` | Volumen del ambiente de fondo | `0.18` |
| `DEFAULT_LOOP_SECONDS` | Duración de loop por defecto | `21300` (5 h 55 min) |

---

## 📝 Notas

- Todas las rutas son **relativas** al proyecto (no se hardcodean rutas
  absolutas). Los scripts crean las carpetas que falten automáticamente.
- Manejo de errores claro: avisa si falta la API key, si no existe un
  archivo, o si `ffmpeg` no está instalado.
- El código está comentado en español.
- Los archivos pesados generados (`output/`, narraciones, miniaturas) están
  en `.gitignore` para no versionarlos. El `.env` nunca se sube.
