"""
快手视频解析与下载模块
通过移动端分享页获取无水印播放地址
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("kuaishou")

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

PC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.kuaishou.com/",
}

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def is_kuaishou_url(url: str) -> bool:
    domains = ("kuaishou.com", "chenzhongtech.com", "gifshow.com", "ksapisrv.com")
    try:
        host = urlparse(url).netloc.lower()
        return any(d in host for d in domains)
    except Exception:
        return False


class KuaishouParser:
    """快手视频解析器"""

    MOBILE_PAGE = "https://v.m.chenzhongtech.com/fw/photo/{photo_id}"

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = 25.0

    def parse(self, url: str) -> dict:
        photo_id, final_url = self._resolve_photo_id(url)
        item = self._fetch_mobile_item(photo_id)
        return self._build_result(item, photo_id, final_url)

    def download(self, url: str, format_id: str = "best") -> dict:
        photo_id, _ = self._resolve_photo_id(url)
        item = self._fetch_mobile_item(photo_id)
        media_url = self._pick_media_url(item, format_id)
        title = item.get("caption") or f"kuaishou_{photo_id}"
        safe_title = re.sub(r'[\\/*?:"<>|\n\r\t#@]', "_", title).strip("_. ")[:60]
        safe_title = re.sub(r"_+", "_", safe_title) or f"kuaishou_{photo_id}"
        filename = f"{safe_title}.mp4"
        filepath = self.download_dir / filename
        self._download_file(media_url, filepath)
        return {
            "filepath": str(filepath),
            "filename": filename,
            "title": title,
            "ext": "mp4",
        }

    def get_direct_url(self, url: str, format_id: str = "best") -> dict:
        photo_id, _ = self._resolve_photo_id(url)
        item = self._fetch_mobile_item(photo_id)
        media_url = self._pick_media_url(item, format_id)
        return {
            "direct_url": media_url,
            "ext": "mp4",
            "filesize": None,
            "title": item.get("caption") or "video",
        }

    def _extract_url(self, text: str) -> str:
        match = _URL_PATTERN.search(text)
        if not match:
            raise ValueError("未找到有效的快手链接")
        return match.group(0).strip().strip('"').strip("'").rstrip(").,;!?")

    def _resolve_photo_id(self, url: str) -> tuple[str, str]:
        share_url = self._extract_url(url)
        with httpx.Client(headers=PC_HEADERS, follow_redirects=True, timeout=self.timeout) as client:
            resp = client.get(share_url)
            final_url = str(resp.url)

        match = re.search(r"/short-video/([^?/&]+)", final_url)
        if match:
            return match.group(1), final_url

        match = re.search(r"shareObjectId=([^&]+)", final_url)
        if match:
            return match.group(1), final_url

        match = re.search(r"/photo/([^?/&]+)", final_url)
        if match:
            return match.group(1), final_url

        raise ValueError("无法从链接中提取快手视频 ID")

    def _fetch_mobile_item(self, photo_id: str) -> dict:
        page_url = self.MOBILE_PAGE.format(photo_id=photo_id)
        with httpx.Client(headers=MOBILE_HEADERS, follow_redirects=True, timeout=self.timeout) as client:
            resp = client.get(page_url)
            resp.raise_for_status()
            html = resp.text

        cover = (
            self._extract_json_field(html, "coverUrl")
            or self._extract_json_field(html, "cover")
            or self._extract_json_field(html, "poster")
            or self._extract_cover_from_html(html)
        )
        duration_ms = self._extract_json_int(html, "duration") or self._extract_json_int(
            html, "videoDuration"
        )
        item = {
            "photoId": photo_id,
            "caption": self._extract_json_field(html, "caption") or "",
            "userName": self._extract_json_field(html, "userName") or "快手用户",
            "coverUrl": cover or "",
            "mainMvUrl": self._extract_json_field(html, "mainMvUrl") or "",
            "duration": self._normalize_duration(duration_ms),
        }
        mp4_urls = re.findall(r'https://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*', html)
        item["mp4_urls"] = list(dict.fromkeys(mp4_urls))
        if not item["mainMvUrl"] and not item["mp4_urls"]:
            raise ValueError("未找到快手视频播放地址，请稍后重试")
        return item

    @staticmethod
    def _extract_json_field(html: str, field: str) -> Optional[str]:
        match = re.search(rf'"{field}"\s*:\s*"((?:\\.|[^"\\])*)"', html)
        if not match:
            return None
        try:
            return json.loads(f'"{match.group(1)}"')
        except json.JSONDecodeError:
            return match.group(1)

    @staticmethod
    def _extract_json_int(html: str, field: str) -> Optional[int]:
        match = re.search(rf'"{field}"\s*:\s*(\d+)', html)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_cover_from_html(html: str) -> Optional[str]:
        images = re.findall(r"https://[^\"']+\.(?:jpg|jpeg|webp)(?:\?[^\"']*)?", html)
        covers = [
            u
            for u in images
            if "/upic/" in u and "/uhead/" not in u and "_s.jpg" not in u and "_s.webp" not in u
        ]
        return covers[0] if covers else None

    @staticmethod
    def _normalize_duration(value: Optional[int]) -> Optional[int]:
        if not value:
            return None
        if value > 1000:
            return max(1, round(value / 1000))
        return value

    def _pick_media_url(self, item: dict, format_id: str) -> str:
        if format_id and format_id != "best" and format_id in item.get("mp4_urls", []):
            return format_id

        if item.get("mainMvUrl"):
            return item["mainMvUrl"]

        urls = item.get("mp4_urls") or []
        if not urls:
            raise ValueError("未找到可下载的视频地址")

        hd = [u for u in urls if "photo-video" in u or "hd" in u.lower()]
        return hd[0] if hd else urls[0]

    def _build_result(self, item: dict, photo_id: str, final_url: str) -> dict:
        caption = item.get("caption") or f"快手视频_{photo_id}"
        cover = item.get("coverUrl") or ""
        urls = item.get("mp4_urls") or []
        main_url = item.get("mainMvUrl") or (urls[0] if urls else "")

        formats = []
        if main_url:
            formats.append({
                "format_id": "best",
                "ext": "mp4",
                "resolution": "原始",
                "height": 720,
                "filesize": None,
                "filesize_approx": None,
                "vcodec": "h264",
                "acodec": "aac",
                "has_audio": True,
                "label": "无水印 MP4 (推荐)",
                "_direct_url": main_url,
            })

        seen = {main_url}
        for idx, url in enumerate(urls[:5]):
            if url in seen:
                continue
            seen.add(url)
            label = "高清 MP4" if "hd" in url.lower() else f"清晰度 {idx + 1}"
            formats.append({
                "format_id": url,
                "ext": "mp4",
                "resolution": label,
                "height": 720,
                "filesize": None,
                "filesize_approx": None,
                "vcodec": "h264",
                "acodec": "aac",
                "has_audio": True,
                "label": label,
                "_direct_url": url,
            })

        duration = item.get("duration")
        return {
            "id": photo_id,
            "title": caption,
            "thumbnail": cover,
            "preview_url": main_url,
            "duration": duration,
            "duration_string": self._fmt_duration(duration),
            "uploader": item.get("userName") or "快手用户",
            "platform": "快手",
            "view_count": None,
            "upload_date": "",
            "description": caption[:200],
            "formats": formats,
            "subtitles": [],
            "automatic_captions": [],
        }

    def _download_file(self, url: str, filepath: Path):
        headers = {**MOBILE_HEADERS, "Referer": "https://v.m.chenzhongtech.com/"}
        temp = filepath.with_suffix(filepath.suffix + ".part")
        with httpx.Client(headers=headers, follow_redirects=True, timeout=60.0) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with temp.open("wb") as f:
                    for chunk in resp.iter_bytes(64 * 1024):
                        if chunk:
                            f.write(chunk)
        temp.replace(filepath)

    @staticmethod
    def _fmt_duration(seconds: Optional[int]) -> str:
        if not seconds:
            return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
