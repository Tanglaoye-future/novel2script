"""/convert 路由：HTTP 转换入口。

POST /convert
  body: ConvertRequest
  resp: ConvertResponse
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.llm import LLMError, get_provider
from backend.core.pipeline import ConvertOptions, convert_novel
from backend.core.validator import auto_repair, validate_screenplay

log = logging.getLogger(__name__)

router = APIRouter(tags=["convert"])


class ConvertRequest(BaseModel):
    text: str = Field(..., min_length=1, description="小说原文，至少 1 字符")
    title: str = Field(..., min_length=1, description="剧本标题")
    source_novel: str = Field(..., min_length=1, description="原著名")
    source_author: str | None = None
    genre: str | None = None
    logline: str | None = None
    tone: str | None = None
    language: str = "zh-CN"
    provider: str | None = Field(default=None, description="LLM Provider，默认按环境变量")


class ConvertResponse(BaseModel):
    screenplay: dict
    validation: dict
    """validation: {ok: bool, errors: [str], warnings: [str]}"""


@router.post("/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest) -> ConvertResponse:
    try:
        provider = get_provider(req.provider)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    options = ConvertOptions(
        title=req.title,
        source_novel=req.source_novel,
        source_author=req.source_author,
        genre=req.genre,
        logline=req.logline,
        tone=req.tone,
        language=req.language,
    )

    try:
        screenplay = convert_novel(req.text, options, provider=provider)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败：{exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 跑一遍 auto_repair + 校验，把结果一并返回给前端
    screenplay = auto_repair(screenplay)
    report = validate_screenplay(screenplay)

    return ConvertResponse(
        screenplay=screenplay,
        validation={
            "ok": report.ok,
            "errors": report.errors,
            "warnings": report.warnings,
        },
    )
