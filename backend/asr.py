"""Whisper 语音识别模块：无字幕视频自动转文字"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import yt_dlp

from douyin import DouyinParser, is_douyin_url
from kuaishou import KuaishouParser, is_kuaishou_url
from downloader import VideoDownloader

logger = logging.getLogger("asr")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
ENABLE_WHISPER = os.getenv("ENABLE_WHISPER", "true").lower() in ("1", "true", "yes")
MAX_ASR_SECONDS = int(os.getenv("MAX_ASR_SECONDS", "1800"))

_whisper_model = None


def is_whisper_enabled() -> bool:
    return ENABLE_WHISPER


def get_asr_status() -> dict:
    """返回 Whisper 配置状态（供前端展示）"""
    return {
        "enabled": is_whisper_enabled(),
        "model": WHISPER_MODEL,
        "device": WHISPER_DEVICE,
        "max_seconds": MAX_ASR_SECONDS,
    }


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info("Loading Whisper model %s on %s", WHISPER_MODEL, WHISPER_DEVICE)
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


def _resolve_language(language: str) -> Optional[str]:
    if not language:
        return None
    if language.startswith("zh"):
        return "zh"
    if language.startswith("en"):
        return "en"
    if language.startswith("ja"):
        return "ja"
    if language.startswith("ko"):
        return "ko"
    return language.split("-")[0]


def download_media_for_asr(url: str, work_dir: str) -> str:
    """下载视频/音频到临时目录，供 Whisper 识别。"""
    if is_douyin_url(url):
        parser = DouyinParser(download_dir=work_dir)
        result = parser.download(url, mode="video")
        return result["filepath"]

    if is_kuaishou_url(url):
        parser = KuaishouParser(download_dir=work_dir)
        result = parser.download(url)
        return result["filepath"]

    downloader = VideoDownloader()
    outtmpl = os.path.join(work_dir, "%(id)s.%(ext)s")
    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    if downloader.ffmpeg_path:
        ydl_opts["ffmpeg_location"] = downloader.ffmpeg_path
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        if downloader.has_ffmpeg:
            mp3_path = os.path.splitext(filepath)[0] + ".mp3"
            if os.path.exists(mp3_path):
                return mp3_path
        if os.path.exists(filepath):
            return filepath

    files = sorted(Path(work_dir).glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise ValueError("音频下载失败，未找到媒体文件")
    return str(files[0])


def transcribe_file(filepath: str, language: str = "zh") -> dict:
    """对本地媒体文件执行 Whisper 识别，返回与 SubtitleExtractor 相同结构。"""
    if not os.path.exists(filepath):
        raise ValueError(f"媒体文件不存在: {filepath}")

    model = _get_whisper_model()
    lang = _resolve_language(language)

    segments_iter, info = model.transcribe(
        filepath,
        language=lang,
        vad_filter=True,
        beam_size=5,
    )

    segments = []
    for seg in segments_iter:
        if seg.end > MAX_ASR_SECONDS:
            break
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": text,
        })

    full_text = " ".join(s["text"] for s in segments)
    detected_lang = getattr(info, "language", None) or lang or "zh"

    return {
        "has_subtitle": bool(segments),
        "language": detected_lang,
        "subtitle_type": "whisper",
        "segments": segments,
        "full_text": full_text,
        "source": "whisper",
    }


def transcribe_url(url: str, language: str = "zh") -> dict:
    """下载视频并 Whisper 识别（无字幕时的回退方案）。"""
    if not is_whisper_enabled():
        return {
            "has_subtitle": False,
            "language": "",
            "subtitle_type": "none",
            "segments": [],
            "full_text": "",
        }

    with tempfile.TemporaryDirectory(prefix="video_asr_") as tmp:
        logger.info("Downloading media for ASR: %s", url[:80])
        media_path = download_media_for_asr(url, tmp)
        logger.info("Transcribing with Whisper: %s", media_path)
        return transcribe_file(media_path, language)
