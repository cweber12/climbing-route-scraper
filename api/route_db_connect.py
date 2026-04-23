# route_db_connect.py
# ---------------------------------------------------------------------------
# Module to handle database connection using environment variables.
# Supports Neon (and any managed PostgreSQL provider) via DATABASE_URL,
# or individual DB_* env vars for local development.
# ---------------------------------------------------------------------------

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Return a psycopg2 connection with RealDictCursor as the default cursor factory."""
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            conn = psycopg2.connect(
                database_url,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        else:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                dbname=os.getenv("DB_NAME", "routes_db"),
                port=int(os.getenv("DB_PORT", 5432)),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        conn.autocommit = False
        print("Connected to PostgreSQL successfully.")
        return conn
    except Exception as e:
        print("Failed to connect to PostgreSQL:", e)
        raise

