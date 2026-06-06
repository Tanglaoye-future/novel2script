"""FastAPI 入口：暴露剧本转换 HTTP API。

启动方式：
    uvicorn backend.api.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Novel2Script API",
    version="0.1.0",
    description="将小说转换为结构化 YAML 剧本的 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe，CI / 部署平台用。"""
    return HealthResponse(status="ok", service="novel2script", version=app.version)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"message": "Novel2Script API. See /docs for OpenAPI spec."}
