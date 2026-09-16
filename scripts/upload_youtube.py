"""
Fase 6 (OPCIONAL) — Subida automática a YouTube.

Sube un video a YouTube con metadata (título, descripción, tags, categoría)
usando la YouTube Data API v3 y autenticación OAuth 2.0.

Esta fase es opcional y NO está activada por defecto. Requiere dependencias
adicionales que no están en requirements.txt para no obligar a instalarlas
si no se automatiza la subida:

    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

Y credenciales OAuth de un proyecto de Google Cloud con la YouTube Data API
habilitada:
  1. Crea un proyecto en https://console.cloud.google.com/
  2. Habilita "YouTube Data API v3".
  3. Crea credenciales OAuth 2.0 de tipo "Aplicación de escritorio".
  4. Descarga el JSON y guárdalo como client_secret.json en la raíz.

La primera ejecución abrirá el navegador para autorizar y guardará el token
en token.json para reutilizarlo.

Uso:
    python scripts/upload_youtube.py --video output/mi_cuento.mp4 \
        --titulo "El Barquito Dormilón" \
        --descripcion "Un cuento suave para dormir." \
        --tags cuentos,dormir,infantil \
        --categoria education \
        --privacidad private
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

# Ámbito mínimo necesario para subir videos.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Mapa de nombres amigables a IDs de categoría de YouTube.
CATEGORIAS = {
    "education": "27",
    "entertainment": "24",
    "people": "22",
    "music": "10",
}

CLIENT_SECRET_FILE = config.BASE_DIR / "client_secret.json"
TOKEN_FILE = config.BASE_DIR / "token.json"


def _autenticar():
    """Realiza el flujo OAuth y devuelve un cliente de la API de YouTube."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Faltan dependencias para la subida a YouTube. Instala:\n"
            "  pip install google-api-python-client google-auth-oauthlib "
            "google-auth-httplib2"
        ) from exc

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"No se encontró {CLIENT_SECRET_FILE}. Descarga tus "
                    "credenciales OAuth de Google Cloud (ver cabecera del script)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def subir(video, titulo, descripcion="", tags=None, categoria="education",
          privacidad="private"):
    """Sube un video a YouTube. Devuelve el ID del video subido."""
    from googleapiclient.http import MediaFileUpload

    ruta = Path(video)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el video: {ruta}")

    categoria_id = CATEGORIAS.get(categoria.lower(), "27")
    youtube = _autenticar()

    cuerpo = {
        "snippet": {
            "title": titulo,
            "description": descripcion,
            "tags": tags or [],
            "categoryId": categoria_id,
        },
        "status": {
            "privacyStatus": privacidad,       # private | unlisted | public
            "selfDeclaredMadeForKids": True,   # contenido infantil
        },
    }

    media = MediaFileUpload(str(ruta), chunksize=-1, resumable=True)
    peticion = youtube.videos().insert(
        part="snippet,status", body=cuerpo, media_body=media
    )

    print(f"Subiendo {ruta.name} a YouTube...")
    respuesta = None
    while respuesta is None:
        estado, respuesta = peticion.next_chunk()
        if estado:
            print(f"  progreso: {int(estado.progress() * 100)}%")

    video_id = respuesta["id"]
    print(f"OK: video subido -> https://youtu.be/{video_id}")
    return video_id


def main():
    parser = argparse.ArgumentParser(description="Sube un video a YouTube (opcional).")
    parser.add_argument("--video", required=True, help="Ruta del mp4 a subir")
    parser.add_argument("--titulo", required=True, help="Título del video")
    parser.add_argument("--descripcion", default="", help="Descripción")
    parser.add_argument("--tags", default="", help="Tags separados por comas")
    parser.add_argument(
        "--categoria",
        default="education",
        choices=list(CATEGORIAS.keys()),
        help="Categoría de YouTube",
    )
    parser.add_argument(
        "--privacidad",
        default="private",
        choices=["private", "unlisted", "public"],
        help="Estado de privacidad",
    )
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    try:
        subir(
            args.video,
            titulo=args.titulo,
            descripcion=args.descripcion,
            tags=tags,
            categoria=args.categoria,
            privacidad=args.privacidad,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
