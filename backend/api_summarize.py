"""AI 视频总结相关 API 路由（独立模块，通过 include_router 挂载）"""

import asyncio
import json
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from auth import get_current_user, get_optional_user
from database import (
    FREE_DAILY_SUMMARY_LIMIT,
    check_summary_permission,
    get_summary_by_url,
    get_user_summaries,
    increment_summary_count,
    save_summary,
)
from summarizer import CONTENT_SCENARIOS, _format_timed_subtitle
from asr import is_whisper_enabled, transcribe_url

router = APIRouter(prefix="/api", tags=["AI 总结"])


class SummarizeRequest(BaseModel):
    url: str
    language: str = "zh"
    video_title: str = ""


class ChatRequest(BaseModel):
    url: str
    question: str
    subtitle_text: str = ""
    video_title: str = ""


class GenerateContentRequest(BaseModel):
    url: str
    scenario: str
    subtitle_text: str
    video_title: str = ""
    language: str = "zh"


class SubtitleRequest(BaseModel):
    url: str
    language: str = "zh"


async def _resolve_subtitle_data(url: str, language: str = "zh") -> dict:
    """提取字幕，无字幕时 Whisper 回退。"""
    loop = asyncio.get_event_loop()
    extractor = _get_extractor()
    subtitle_data = await loop.run_in_executor(None, extractor.extract_subtitles_only, url)

    if not subtitle_data["has_subtitle"] and is_whisper_enabled():
        subtitle_data = await loop.run_in_executor(None, transcribe_url, url, language)

    return subtitle_data


def _check_summary_permission(user: dict | None):
    if not user:
        return False, 0, "请先登录后使用 AI 总结功能"

    allowed, remaining = check_summary_permission(user["id"])
    if not allowed:
        return False, 0, f"今日免费 AI 总结次数已用完（每日 {FREE_DAILY_SUMMARY_LIMIT} 次），开通 VIP 可无限使用"

    return True, remaining, None


def _get_summarizer():
    from summarizer import VideoSummarizer
    if not hasattr(_get_summarizer, "_instance"):
        try:
            _get_summarizer._instance = VideoSummarizer()
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
    return _get_summarizer._instance


def _get_extractor():
    from summarizer import SubtitleExtractor
    if not hasattr(_get_extractor, "_instance"):
        _get_extractor._instance = SubtitleExtractor()
    return _get_extractor._instance


def _subtitle_for_llm(subtitle_data: dict) -> str:
    segments = subtitle_data.get("segments") or []
    if segments:
        return _format_timed_subtitle(segments)
    return subtitle_data.get("full_text", "")


@router.get("/asr/status")
async def asr_status():
    """Whisper 语音识别配置状态"""
    from asr import get_asr_status
    return {"success": True, "data": get_asr_status()}


@router.post("/subtitles")
async def fetch_subtitles(req: SubtitleRequest, user: dict = Depends(get_current_user)):
    """获取视频字幕（含 Whisper 语音识别回退），供问答/创作前置使用。"""
    subtitle_data = await _resolve_subtitle_data(req.url, req.language)
    if not subtitle_data["has_subtitle"]:
        err = subtitle_data.get("error") or "无法获取字幕，Whisper 识别失败或未启用"
        raise HTTPException(status_code=400, detail=err)
    return {"success": True, "data": subtitle_data}


@router.get("/summaries")
async def list_summaries(user: dict = Depends(get_current_user)):
    """当前用户的 AI 总结历史"""
    items = get_user_summaries(user["id"])
    return {"success": True, "data": items}


@router.get("/summaries/cached")
async def get_cached_summary(
    url: str = Query(..., description="视频 URL"),
    user: dict = Depends(get_current_user),
):
    """获取某视频的历史总结（用于快速恢复）"""
    record = get_summary_by_url(user["id"], url)
    if not record:
        return {"success": True, "data": None}
    subtitle = {}
    if record.get("subtitle_json"):
        try:
            subtitle = json.loads(record["subtitle_json"])
        except json.JSONDecodeError:
            pass
    return {
        "success": True,
        "data": {
            "summary_text": record["summary_text"],
            "mindmap_md": record.get("mindmap_md") or "",
            "subtitle": subtitle,
            "video_title": record.get("video_title") or "",
            "updated_at": record.get("updated_at"),
        },
    }


@router.post("/summarize", response_class=EventSourceResponse)
async def summarize_video(req: SummarizeRequest, user: dict | None = Depends(get_optional_user)) -> AsyncIterable[ServerSentEvent]:
    allowed, remaining, message = _check_summary_permission(user)
    if not allowed:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": message, "need_login": user is None, "need_vip": user is not None}, ensure_ascii=False),
            event="error",
        )
        return

    try:
        loop = asyncio.get_event_loop()
        extractor = _get_extractor()
        subtitle_data = await loop.run_in_executor(None, extractor.extract_subtitles_only, req.url)

        if not subtitle_data["has_subtitle"] and is_whisper_enabled():
            yield ServerSentEvent(
                raw_data=json.dumps({
                    "message": "未检测到字幕，正在使用 Whisper 语音识别（首次加载模型可能较慢）...",
                    "stage": "download",
                }, ensure_ascii=False),
                event="asr",
            )
            subtitle_data = await loop.run_in_executor(None, transcribe_url, req.url, req.language)

        yield ServerSentEvent(
            raw_data=json.dumps(subtitle_data, ensure_ascii=False),
            event="subtitle",
        )

        if not subtitle_data["has_subtitle"]:
            err = subtitle_data.get("error") or "该视频没有可用的字幕，且 Whisper 识别未成功。请确认已安装 ffmpeg 或检查视频时长是否超过限制。"
            yield ServerSentEvent(
                raw_data=json.dumps({"message": err}, ensure_ascii=False),
                event="error",
            )
            return

        llm_text = _subtitle_for_llm(subtitle_data)
        summarizer = _get_summarizer()
        title = req.video_title or ""

        summary_parts = []
        for token in summarizer.summarize_stream(llm_text, req.language, title):
            summary_parts.append(token)
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="summary")

        summary_full = "".join(summary_parts)
        mindmap_md = await loop.run_in_executor(
            None, summarizer.generate_mindmap, llm_text, req.language, title
        )

        yield ServerSentEvent(
            raw_data=json.dumps({"markdown": mindmap_md}, ensure_ascii=False),
            event="mindmap",
        )

        remaining = increment_summary_count(user["id"])
        save_summary(
            user_id=user["id"],
            video_url=req.url,
            video_title=title,
            summary_text=summary_full,
            mindmap_md=mindmap_md,
            subtitle_json=json.dumps(subtitle_data, ensure_ascii=False),
        )

        quota_info = {"remaining": remaining, "limit": FREE_DAILY_SUMMARY_LIMIT}
        yield ServerSentEvent(
            raw_data=json.dumps(quota_info, ensure_ascii=False),
            event="quota",
        )
        yield ServerSentEvent(raw_data="[DONE]", event="done")

    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"总结失败: {str(e)}"}, ensure_ascii=False),
            event="error",
        )


@router.post("/chat", response_class=EventSourceResponse)
async def chat_with_video(req: ChatRequest, user: dict = Depends(get_current_user)) -> AsyncIterable[ServerSentEvent]:
    """AI 视频问答（需登录）"""
    try:
        if req.subtitle_text.strip():
            subtitle_text = req.subtitle_text
        else:
            loop = asyncio.get_event_loop()
            extractor = _get_extractor()
            subtitle_data = await loop.run_in_executor(None, extractor.extract_subtitles_only, req.url)

            if not subtitle_data["has_subtitle"] and is_whisper_enabled():
                yield ServerSentEvent(
                    raw_data=json.dumps({
                        "message": "未检测到字幕，正在使用 Whisper 语音识别，请稍候...",
                    }, ensure_ascii=False),
                    event="asr",
                )
                subtitle_data = await loop.run_in_executor(None, transcribe_url, req.url, "zh")

            if not subtitle_data["has_subtitle"]:
                err = subtitle_data.get("error") or "无法获取视频文字内容，请确认 ENABLE_WHISPER=true 并重试"
                yield ServerSentEvent(
                    raw_data=json.dumps({"message": err}, ensure_ascii=False),
                    event="error",
                )
                return

            subtitle_text = _subtitle_for_llm(subtitle_data)
            yield ServerSentEvent(
                raw_data=json.dumps(subtitle_data, ensure_ascii=False),
                event="subtitle_ready",
            )

        summarizer = _get_summarizer()
        for token in summarizer.chat_stream(subtitle_text, req.question, req.video_title or ""):
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="answer")

        yield ServerSentEvent(raw_data="[DONE]", event="done")

    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"回答失败: {str(e)}"}, ensure_ascii=False),
            event="error",
        )


@router.get("/content/scenarios")
async def list_content_scenarios():
    """可用的 AI 内容创作场景"""
    return {
        "success": True,
        "data": [
            {"key": k, "label": v["label"]}
            for k, v in CONTENT_SCENARIOS.items()
        ],
    }


@router.post("/generate-content", response_class=EventSourceResponse)
async def generate_content(req: GenerateContentRequest, user: dict = Depends(get_current_user)) -> AsyncIterable[ServerSentEvent]:
    """
    AI 内容二次创作（SSE 流式）
    场景：study_notes / xiaohongshu / wechat_article / flashcards
    """
    if req.scenario not in CONTENT_SCENARIOS:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"不支持的场景: {req.scenario}"}, ensure_ascii=False),
            event="error",
        )
        return

    if not req.subtitle_text.strip():
        yield ServerSentEvent(
            raw_data=json.dumps({"message": "请先生成视频总结以获取字幕内容"}, ensure_ascii=False),
            event="error",
        )
        return

    try:
        summarizer = _get_summarizer()
        for token in summarizer.generate_content_stream(
            req.scenario, req.subtitle_text, req.video_title or "", req.language
        ):
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="content")

        yield ServerSentEvent(raw_data="[DONE]", event="done")
    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": f"生成失败: {str(e)}"}, ensure_ascii=False),
            event="error",
        )
