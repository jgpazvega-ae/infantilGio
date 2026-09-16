"""
generate_visuals.py — Preparación de visuales (Fase 5).

Selecciona/prepara la fuente visual para un cuento. La arquitectura acepta
varias fuentes sin acoplarse a un proveedor concreto:

    VISUAL SOURCE
      ├── local footage   (assets/footage/)   [implementado]
      ├── local image     (assets/images/)    [implementado]
      ├── generated image (proveedor futuro)  [interfaz preparada]
      └── generated video (proveedor futuro)  [interfaz preparada]

Para la primera versión resuelve una fuente local (clip o imagen) y la deja
registrada. La generación automática de imagen/video es una mejora futura que
encaja en resolve_visual_source() sin cambiar el resto del pipeline.

Uso:
    python scripts/generate_visuals.py --footage mar.mp4
    python scripts/generate_visuals.py --image portada.jpg
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402

log = get_logger("generate_visuals")


def resolve_visual_source(footage=None, image=None):
    """
    Devuelve (tipo, ruta) de la fuente visual local.
    tipo ∈ {"footage", "image"}. Lanza si no se encuentra.

    Punto de extensión futuro: si se pide una fuente generada, aquí se
    llamaría al proveedor de imagen/video y se devolvería la ruta resultante.
    """
    if footage:
        p = Path(footage)
        if not p.exists():
            p = config.FOOTAGE_DIR / Path(footage).name
        if not p.exists():
            raise FileNotFoundError(f"No existe el footage: {footage}")
        return "footage", p
    if image:
        p = Path(image)
        if not p.exists():
            p = config.IMAGES_DIR / Path(image).name
        if not p.exists():
            raise FileNotFoundError(f"No existe la imagen: {image}")
        return "image", p
    raise ValueError("Indica --footage o --image (o integra un generador futuro).")


def main():
    ap = argparse.ArgumentParser(description="Prepara la fuente visual local.")
    ap.add_argument("--footage", default=None, help="Clip local (assets/footage/)")
    ap.add_argument("--image", default=None, help="Imagen local (assets/images/)")
    args = ap.parse_args()
    try:
        tipo, ruta = resolve_visual_source(args.footage, args.image)
        log.info("Fuente visual resuelta: %s -> %s", tipo, ruta)
    except Exception as exc:  # noqa: BLE001
        log.error("ERROR: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
