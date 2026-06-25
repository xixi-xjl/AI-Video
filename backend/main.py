import os
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import unquote

from env_loader import load_project_env
load_project_env()

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from downloader import VideoDownloader
from douyin import DouyinParser, is_douyin_url
from bilibili import BilibiliParser, is_bilibili_url
from kuaishou import KuaishouParser, is_kuaishou_url
from database import init_db, ensure_admin_account


downloader = VideoDownloader()
douyin_parser = DouyinParser(download_dir=downloader.DOWNLOAD_DIR)
bilibili_parser = BilibiliParser(download_dir=downloader.DOWNLOAD_DIR)
kuaishou_parser = KuaishouParser(download_dir=downloader.DOWNLOAD_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_admin_account()
    yield
    download_dir = downloader.DOWNLOAD_DIR
    if os.path.exists(download_dir):
        for f in os.listdir(download_dir):
            try:
                os.remove(os.path.join(download_dir, f))
            except OSError:
                pass


app = FastAPI(
    title="AI多平台视频下载分析平台 API",
    description="基于 yt-dlp 的多平台视频下载与 AI 分析服务，支持 1800+ 平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str = "bestvideo+bestaudio/best"


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "AI多平台视频下载分析平台服务运行中"}


def _parse_by_url(url: str):
    if is_douyin_url(url):
        return douyin_parser.parse(url)
    if is_bilibili_url(url):
        return bilibili_parser.parse(url)
    if is_kuaishou_url(url):
        return kuaishou_parser.parse(url)
    return downloader.parse_video(url)


def _download_by_url(url: str, format_id: str):
    if is_douyin_url(url):
        return douyin_parser.download(url)
    if is_bilibili_url(url):
        return bilibili_parser.download(url, format_id)
    if is_kuaishou_url(url):
        return kuaishou_parser.download(url, format_id)
    return downloader.download_video(url, format_id)


def _direct_url_by_url(url: str, format_id: str):
    if is_bilibili_url(url):
        return bilibili_parser.get_direct_url(url, format_id)
    if is_kuaishou_url(url):
        return kuaishou_parser.get_direct_url(url, format_id)
    return downloader.get_direct_url(url, format_id)


@app.post("/api/parse")
async def parse_video(req: ParseRequest):
    """解析视频信息（抖音/B站/快手走专用模块，其他走 yt-dlp）"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _parse_by_url, req.url)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": f"解析失败: {str(e)}"
        })


@app.post("/api/download")
async def download_video(req: DownloadRequest):
    """服务端下载视频后提供文件下载（抖音/B站/快手走专用模块）"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _download_by_url, req.url, req.format_id)
        filepath = result["filepath"]
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="下载的文件不存在")

        return FileResponse(
            path=filepath,
            filename=result["filename"],
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": f"下载失败: {str(e)}"
        })


@app.post("/api/direct-url")
async def get_direct_url(req: DownloadRequest):
    """获取视频直链"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _direct_url_by_url, req.url, req.format_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": f"获取直链失败: {str(e)}"
        })


def _media_proxy_headers(url: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    }
    lower = url.lower()
    if any(token in lower for token in ("yximgs.com", "kwimgs.com", "kuaishou", "chenzhongtech")):
        headers["Referer"] = "https://www.kuaishou.com/"
    elif "douyin" in lower or "douyinvod" in lower:
        headers["Referer"] = "https://www.douyin.com/"
    else:
        headers["Referer"] = url
    return headers


@app.get("/api/proxy/thumbnail")
async def proxy_thumbnail(url: str = Query(..., description="缩略图URL")):
    """代理获取视频缩略图，绕过防盗链"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=_media_proxy_headers(url))
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        raise HTTPException(status_code=502, detail="缩略图加载失败")


@app.get("/api/proxy/video")
async def proxy_video(request: Request, url: str = Query(..., description="视频直链URL")):
    """代理视频流，绕过 CDN 防盗链，支持 Range 请求"""
    media_url = unquote(url)
    try:
        headers = _media_proxy_headers(media_url)
        range_header = request.headers.get("range")
        if range_header:
            headers["Range"] = range_header

        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(media_url, headers=headers)
            resp.raise_for_status()

            out_headers = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"}
            for key in ("content-range", "content-length", "content-type"):
                if resp.headers.get(key):
                    out_headers[key] = resp.headers[key]

            return StreamingResponse(
                resp.aiter_bytes(chunk_size=64 * 1024),
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "video/mp4"),
                headers=out_headers,
            )
    except Exception:
        raise HTTPException(status_code=502, detail="视频预览加载失败")


# 挂载功能模块路由
from api_summarize import router as summarize_router
from api_auth import router as auth_router
from api_payment import router as payment_router
from api_admin import router as admin_router

app.include_router(summarize_router)
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
