"""Configuración de la app, cargada desde variables de entorno (.env)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Agrupa lo que antes eran variables sueltas a nivel de módulo."""

    username: str
    token: str
    root: Path

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @classmethod
    def from_env(cls, root: Path) -> "Config":
        """Carga el .env ubicado en `root` y valida que estén las claves.

        A diferencia del script original, esto NO se ejecuta al importar el
        módulo (evita el `sys.exit` a nivel de import que hacía imposible
        testear o reutilizar el código sin variables de entorno reales).
        Se llama explícitamente desde el entrypoint (`update_stats.py`).
        """
        load_dotenv(root / ".env")

        username = os.getenv("GITHUB_USERNAME")
        token = os.getenv("GITHUB_TOKEN")

        if not username or not token:
            sys.exit("Error: define GITHUB_USERNAME y GITHUB_TOKEN en tu archivo .env")

        return cls(username=username, token=token, root=root)
