"""Database helpers (PostgreSQL + pgvector)."""
from __future__ import annotations

import os

import psycopg2
from pgvector.psycopg2 import register_vector

from .config import Settings

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "schema.sql")


def connect(settings: Settings, vector: bool = True):
    conn = psycopg2.connect(**settings.db_kwargs)
    if vector:
        register_vector(conn)
    return conn


def init_db(settings: Settings) -> None:
    # vector type must exist before register_vector, so connect plain first
    conn = connect(settings, vector=False)
    with conn, conn.cursor() as cur:
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            cur.execute(fh.read())
    conn.close()
