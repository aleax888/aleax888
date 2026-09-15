"""Application configuration, loaded from environment variables (.env)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Groups what used to be loose module-level variables."""

    username: str
    token: str
    root: Path

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def templates_dir(self) -> Path:
        return self.root / "stats" / "templates"

    @classmethod
    def from_env(cls, root: Path) -> "Config":
        """Loads the .env file located in `root` and validates that the keys exist.

        Unlike the original script, this does NOT run on module import (it avoids
        the `sys.exit` at import time that made it impossible to test or reuse the
        code without real environment variables). It is called explicitly from the
        entrypoint (`update_stats.py`).
        """
        load_dotenv(root / ".env")

        username = os.getenv("GITHUB_USERNAME")
        token = os.getenv("GITHUB_TOKEN")

        if not username or not token:
            sys.exit("Error: define GITHUB_USERNAME and GITHUB_TOKEN in your .env file")

        return cls(username=username, token=token, root=root)
