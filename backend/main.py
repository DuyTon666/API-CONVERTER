from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from core import config  # noqa: F401 — side effect: inject 2.pipeline vào sys.path + init_emitter, phải chạy trước khi routers import từ pipeline

from routers import health, modules, docs, error_codes

app = FastAPI(title="API Converter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(modules.router)
app.include_router(docs.router)
app.include_router(error_codes.router)