"""Database configuration for local development and hosted PostgreSQL."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

cloud_url = os.getenv("DATABASE_URL")

if cloud_url:
    database_url = make_url(cloud_url)
    if database_url.get_backend_name() not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must identify a PostgreSQL database.")
    database_url = database_url.set(drivername="postgresql+psycopg")
else:
    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        database=os.environ["POSTGRES_DB"],
    )

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=3,
    connect_args={"connect_timeout": 15},
)
SessionLocal = sessionmaker(bind=engine)
