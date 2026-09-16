# 🧸🌙 infantilGio — Fábrica automatizada de contenido infantil para YouTube

Pipeline reproducible en Python que convierte una **idea** en un **paquete listo
para subir** a YouTube, para dos productos principales:

1. 🧸 **Cuentos infantiles narrados** (voz de ElevenLabs sobre footage suave).
2. 🌙 **Videos largos para dormir / relajación** (paisaje + ambiente en bucle,
   hasta **5 h 55 min** y cualquier duración).

Además genera 🎵 contenido ambiental, 🖼️ miniaturas, 📝 metadata de YouTube,
🔍 control de calidad automático y 📦 paquetes finales. La subida automática a
YouTube (Data API v3) queda preparada como fase final.

> Filosofía: **Python orquesta, FFmpeg hace el trabajo pesado.** Modular,
> idempotente, con checkpoints, manifests y regeneración por etapa.

---

## 1. Arquitectura

```
IDEA → CUENTO → GUION → PLAN DE ESCENAS → NARRACIÓN → AMBIENTE →
VISUALES → VIDEO → THUMBNAIL → METADATA → QUALITY CONTROL → PACKAGE → YOUTUBE
```

Tipos de contenido soportados: `STORY`, `SLEEP`, `AMBIENT` (+ futuros).

```
infantilGio/
├── config/                 # voices.yaml, channels.yaml, styles.yaml, presets.yaml
├── content/                # ideas/ stories/ scripts/ scene_plans/ metadata/
├── assets/                 # footage/ music/ ambient/ images/ characters/ fonts/
├── audio/                  # narration/ characters/ ambient/ final/
├── video/                  # scenes/ intermediate/ final/
├── thumbnails/
├── output/                 # stories/ sleep/ packages/
├── logs/  cache/
├── core/                   # librería núcleo (ffmpeg, loops, qc, story, metadata...)
├── scripts/                # CLIs por etapa
├── pipeline.py             # orquestador principal (CLI)
├── config.py               # rutas + carga de .env y config/*.yaml
├── requirements.txt  .env.example  .gitignore
└── tests/
```

Cada producción genera un **manifest.json** y avanza por estados:
`IDEA → SCRIPTED → AUDIO_READY → VISUALS_READY → VIDEO_READY → THUMBNAIL_READY →
QC_PASSED → READY_TO_UPLOAD → UPLOADED`.

---

## 2. Instalación

### 2.1 Requisito del sistema: FFmpeg

`ffmpeg` y `ffprobe` deben estar en el PATH:

- **macOS:** `brew install ffmpeg`
- **Windows:** `choco install ffmpeg` (o https://ffmpeg.org/download.html)
- **Linux:** `sudo apt install ffmpeg`

Verifica con `ffmpeg -version`. El pipeline aborta con instrucciones si falta.

### 2.2 Entorno de Python

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2.3 Variables de entorno (.env)

```bash
cp .env.example .env
# Edita .env:
#   ELEVENLABS_API_KEY=tu_clave
#   ELEVENLABS_VOICE_ID=  (opcional; por defecto usa config/voices.yaml)
```

La API key se lee del entorno y **nunca** se imprime en logs. Las credenciales
de YouTube solo hacen falta en la Fase 10 (subida).

### 2.4 ElevenLabs

La voz del narrador se configura en `config/voices.yaml` (`narrator.voice_id`).
Por defecto: **Sofia** (femenina, cálida y suave). Alternativas comentadas en
ese archivo. Ajustes orientados a narración infantil clara y tranquila.

---

## 3. Uso rápido

### 3.1 Primer cuento

```bash
# (Opcional) Crear un cuento de prueba por plantilla:
python scripts/generate_story.py --template --title "André y el Tren de las Estrellas" \
    --character "André" --theme "amistad" --setting "el valle de los sueños"

# Coloca un clip de fondo en assets/footage/ (p. ej. mar.mp4) y ejecuta:
python pipeline.py story content/stories/andre-y-el-tren-de-las-estrellas.md \
    --footage mar.mp4
```

Resultado: narración → plan de escenas → video → miniatura → metadata → QC →
paquete en `output/packages/<slug>/`.

### 3.2 Primer video para dormir

```bash
python pipeline.py sleep assets/ambient/ambient_mar.mp3 --video mar.mp4 \
    --duration 01:00:00 --title "Sonido del Mar Relajante"
```

### 3.3 Video de 5 h 55 min

```bash
python pipeline.py sleep assets/ambient/ambient_mar.mp3 --video mar.mp4 \
    --duration 05:55:00
```

Duración por defecto (sin `--duration`): **05:55:00**. Se acepta cualquier
duración (`HH:MM:SS`, `2h`, `90m`, segundos). El audio base se analiza
automáticamente; no se asume su duración.

### 3.4 Solo audio ambiental

```bash
python pipeline.py ambient assets/ambient/ambient_mar.mp3 --duration 03:00:00 \
    --title "Sonido del Mar"
```

### 3.5 Etapas sueltas

```bash
python scripts/generate_audio.py content/stories/andre.md            # narración
python scripts/create_loop.py --audio ...mp3 --duration 05:55:00     # loop audio
python scripts/generate_scene_plan.py content/stories/andre.md       # escenas
python scripts/generate_thumbnail.py --video video/final/andre.mp4 --titulo "André"
python scripts/generate_metadata.py --story content/stories/andre.md
python scripts/quality_check.py --package output/packages/andre/
```

Todos los comandos tienen `--help`, `--force` (regenerar) y, donde aplica,
`--dry-run` (mostrar sin crear archivos).

---

## 4. Quality Control

`quality_check.py` (y el paso final del pipeline) verifica:

- **Audio:** existe, legible, duración > 0, sample rate y canales válidos.
- **Video:** MP4 válido, 1920×1080, ~30 fps, codec compatible, audio presente,
  duración esperada (tolerancia configurable).
- **Thumbnail:** existe, 1280×720, formato válido.
- **Package:** metadata con título, descripción y tags.

Salida `STATUS: PASS` / `FAILED` con el detalle de cada comprobación.

---

## 5. Output y paquetes

Cada video final produce:

```
output/packages/<slug>/
├── video.mp4
├── thumbnail.jpg
├── metadata.json
├── description.txt
└── manifest.json
```

Listo para subir manualmente aunque la API de YouTube no esté activada.

---

## 6. Configuración

| Archivo | Contenido |
|---|---|
| `config/voices.yaml` | voz del narrador, personajes, modelo TTS, troceo |
| `config/channels.yaml` | identidad de canal, hashtags, categoría, privacidad |
| `config/styles.yaml` | identidad visual y estilo de miniatura |
| `config/presets.yaml` | formato de video, volúmenes de audio, duración de loop |

Volúmenes por defecto: narración `1.0`, ambiente `0.18`. Formato de salida:
1920×1080, 30 fps, H.264/AAC, MP4.

---

## 7. Rendimiento (videos largos)

Para 5 h 55 min NO se re-codifican horas de video ni se cargan en memoria:

1. El clip base se **normaliza una sola vez** (WxH, fps, GOP corto, opcional
   crossfade para loop perfecto) en `cache/`.
2. El video largo se genera con **`-stream_loop` + `-c:v copy`** (stream-copy,
   rápido) y el audio en bucle se codifica a AAC. Todo en un solo paso de
   FFmpeg. La duración se recorta con `-t` (tolerancia de video ≤ GOP; audio
   exacto).

El loop de audio usa **crossfade** para evitar clicks y aplica un fundido de
salida; la duración final coincide con la solicitada.

---

## 8. Assets, copyright y licencias

Usa únicamente assets **propios, licenciados o generados** con licencia que
permita el uso previsto. El sistema **no** descarga contenido de Internet.
Organiza el material en `assets/` y registra su origen/licencia (por ejemplo,
un `assets/LICENSES.md` con la procedencia de cada clip/música).

---

## 9. Seguridad

`.env` + `.gitignore`, validación de inputs, `subprocess` con listas de
argumentos (sin `shell=True`, evitando inyección), rutas controladas, y la API
key nunca se imprime en logs.

---

## 10. Tests

```bash
python -m pytest -q          # si tienes pytest
python tests/test_core.py    # runner integrado, sin pytest
```

Cubren duración, paths/slug, chunking, manifest, metadata, scene plan, story y
la lógica de QC (sin requerir FFmpeg ni red).

---

## 11. Troubleshooting

| Problema | Causa / solución |
|---|---|
| `FFmpeg no está instalado...` | Instala ffmpeg/ffprobe (ver §2.1). |
| `Falta ELEVENLABS_API_KEY` | Copia `.env.example` a `.env` y añade tu clave. |
| Duración de video ligeramente distinta | El recorte de video por stream-copy se alinea al keyframe (≤ GOP); el audio es exacto. |
| El audio no regenera | Existe y es válido; usa `--force`. |
| `No hay voice_id` | Define `narrator.voice_id` en `config/voices.yaml` o `ELEVENLABS_VOICE_ID`. |

---

## 12. Roadmap

- [x] Fundación: estructura, config, logging, CLI, detección de FFmpeg, errores.
- [x] ElevenLabs: narración con troceo, caché y `--force`.
- [x] Sleep engine: loops de audio/video de duración exacta (5 h 55 min).
- [x] Ensamblado de video de cuentos.
- [x] Story engine: metadata, scene planner, plantilla de cuento.
- [x] Miniaturas, metadata, control de calidad, pipeline maestro, packages.
- [ ] **Fase 10 — YouTube:** subida con Data API v3 + OAuth (`scripts/upload_youtube.py`).
- [ ] Generación automática de visuales (imagen/video) vía proveedor.
- [ ] Voces por personaje y audio ducking dinámico.
- [ ] Dashboard de producción (estados, QC, analytics).

La subida a YouTube se implementará tras validar manualmente todo el flujo.
