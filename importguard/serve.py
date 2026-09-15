"""Serve the built frontend and API from one process."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from importguard.api import app as api

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
