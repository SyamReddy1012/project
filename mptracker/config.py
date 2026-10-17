"""Configuration loaded from environment variables / .env (no secrets in code)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    model_name: str
    detector_backend: str
    cosine_threshold: float
    frame_skip: int
    min_face_px: int = 28

    @property
    def db_kwargs(self) -> dict:
        return {
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "host": self.db_host,
            "port": self.db_port,
        }


def get_settings() -> Settings:
    _load_dotenv()
    env = os.environ.get
    db_url = env("DATABASE_URL", "").strip()
    if db_url:
        import urllib.parse
        p = urllib.parse.urlparse(db_url)
        db_name = p.path.lstrip("/") or env("DB_NAME", "FACEPROJECT")
        db_user = p.username or env("DB_USER", "postgres")
        db_password = p.password or env("DB_PASSWORD", "")
        db_host = p.hostname or env("DB_HOST", "localhost")
        db_port = p.port or int(env("DB_PORT", "5432"))
    else:
        db_name = env("DB_NAME", "FACEPROJECT")
        db_user = env("DB_USER", "postgres")
        db_password = env("DB_PASSWORD", "")
        db_host = env("DB_HOST", "localhost")
        db_port = int(env("DB_PORT", "5432"))

    return Settings(
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
        model_name=env("FACE_MODEL", "ArcFace"),
        detector_backend=env("FACE_DETECTOR", "retinaface"),
        cosine_threshold=float(env("COSINE_THRESHOLD", "0.60")),
        frame_skip=int(env("FRAME_SKIP", "3")),
    )
