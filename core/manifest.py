"""
Manifest de producción y estados.

Cada producción (cuento o video de dormir) tiene un manifest.json que registra
sus artefactos, su estado y el resultado del control de calidad. Esto habilita
reproducibilidad, checkpoints y la regeneración de una sola etapa.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class ProductionState:
    """Estados posibles de una producción (para un futuro dashboard)."""

    IDEA = "IDEA"
    SCRIPTED = "SCRIPTED"
    AUDIO_READY = "AUDIO_READY"
    VISUALS_READY = "VISUALS_READY"
    VIDEO_READY = "VIDEO_READY"
    THUMBNAIL_READY = "THUMBNAIL_READY"
    QC_PASSED = "QC_PASSED"
    READY_TO_UPLOAD = "READY_TO_UPLOAD"
    UPLOADED = "UPLOADED"

    ORDER = [
        IDEA, SCRIPTED, AUDIO_READY, VISUALS_READY, VIDEO_READY,
        THUMBNAIL_READY, QC_PASSED, READY_TO_UPLOAD, UPLOADED,
    ]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class Manifest:
    """Envoltura sencilla sobre el manifest.json de una producción."""

    def __init__(self, path, data=None):
        self.path = Path(path)
        self.data = data or {}

    # -- creación / carga ---------------------------------------------------
    @classmethod
    def create(cls, path, project, content_type):
        data = {
            "project": project,
            "content_type": content_type,          # story | sleep | ambient
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "state": ProductionState.IDEA,
            "artifacts": {},                        # nombre -> ruta relativa
            "info": {},                             # duraciones, etc.
            "quality_check": None,                  # "PASS" | "FAILED" | None
        }
        return cls(path, data)

    @classmethod
    def load(cls, path):
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            return cls(path, json.load(f))

    @classmethod
    def load_or_create(cls, path, project, content_type):
        path = Path(path)
        if path.exists():
            return cls.load(path)
        return cls.create(path, project, content_type)

    # -- mutaciones ---------------------------------------------------------
    def set_artifact(self, name, ruta):
        self.data.setdefault("artifacts", {})[name] = str(ruta)

    def get_artifact(self, name):
        return self.data.get("artifacts", {}).get(name)

    def set_info(self, clave, valor):
        self.data.setdefault("info", {})[clave] = valor

    def set_state(self, state):
        self.data["state"] = state

    def advance_state(self, state):
        """Avanza el estado solo si el nuevo es posterior al actual."""
        orden = ProductionState.ORDER
        actual = self.data.get("state", ProductionState.IDEA)
        if orden.index(state) > orden.index(actual):
            self.data["state"] = state

    def set_quality(self, resultado):
        self.data["quality_check"] = resultado

    # -- persistencia -------------------------------------------------------
    def save(self):
        self.data["updated_at"] = _now_iso()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        return self.path
