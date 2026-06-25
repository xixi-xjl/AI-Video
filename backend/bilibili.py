"""
B 站视频解析与下载模块
基于 B 站公开 API + WBI 签名，绕过 yt-dlp 412 拦截
"""

import hashlib
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx

logger = logging.getLogger("bilibili")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://www.bilibili.com",
}

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

QUALITY_MAP = {
    120: ("4K", 2160),
    116: ("1080P60", 1080),
    112: ("1080P+", 1080),
    80: ("1080P", 1080),
    64: ("720P", 720),
    32: ("480P", 480),
    16: ("360P", 360),
}

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def is_bilibili_url(url: str) -> bool:
    """判断是否为 B 站链接"""
    domains = ("bilibili.com", "b23.tv")
    try:
        host = urlparse(url).netloc.lower()
        return any(d in host for d in domains)
    except Exception:
        return False


class BilibiliParser:
    """B 站视频解析器"""

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = 20.0
        self._wbi_keys: tuple[str, str] | None = None
        self._wbi_expire_at = 0.0

    def parse(self, url: str) -> dict:
        share_url = self._extract_url(url)
        resolved = self._resolve_short_url(share_url)
        bvid = self._parse_bvid(resolved)
        if not bvid:
            raise ValueError("无法从链接中提取 BV 号")

        view = self._fetch_view(bvid)
        cid = view.get("cid")
        if not cid:
            raise ValueError("无法获取视频分 P 信息")

        title = view.get("title") or f"bilibili_{bvid}"
        duration = view.get("duration") or 0
        owner = view.get("owner") or {}
        stat = view.get("stat") or {}

        formats = []
        for qn, (label, height) in QUALITY_MAP.items():
            formats.append({
                "format_id": str(qn),
                "ext": "mp4",
                "resolution": f"{height}p",
                "height": height,
                "filesize": None,
                "filesize_approx": None,
                "vcodec": "avc",
                "acodec": "aac",
                "has_audio": True,
                "label": f"{label} MP4",
                "_bvid": bvid,
                "_cid": cid,
            })

        return {
            "id": bvid,
            "title": title,
            "thumbnail": view.get("pic", ""),
            "duration": duration,
            "duration_string": self._fmt_duration(duration),
            "uploader": owner.get("name", "B站UP主"),
            "platform": "Bilibili",
            "view_count": stat.get("view"),
            "upload_date": "",
            "description": (view.get("desc") or title)[:200],
            "formats": formats,
            "subtitles": [],
            "automatic_captions": [],
            "_bvid": bvid,
            "_cid": cid,
        }

    def download(self, url: str, format_id: str = "80") -> dict:
        share_url = self._extract_url(url)
        resolved = self._resolve_short_url(share_url)
        bvid = self._parse_bvid(resolved)
        if not bvid:
            raise ValueError("无法从链接中提取 BV 号")

        view = self._fetch_view(bvid)
        cid = view.get("cid")
        title = view.get("title") or f"bilibili_{bvid}"
        qn = int(format_id) if str(format_id).isdigit() else 80

        play_data = self._fetch_playurl(bvid, cid, qn)
        safe_title = re.sub(r'[\\/*?:"<>|\n\r\t#@]', "_", title).strip("_. ")[:60]
        safe_title = re.sub(r"_+", "_", safe_title) or f"bilibili_{bvid}"
        filename = f"{safe_title}.mp4"
        filepath = self.download_dir / filename

        if play_data.get("durl"):
            self._download_file(play_data["durl"][0]["url"], filepath, referer=f"https://www.bilibili.com/video/{bvid}")
        elif play_data.get("dash"):
            self._download_dash(play_data["dash"], filepath, referer=f"https://www.bilibili.com/video/{bvid}")
        else:
            raise ValueError("未找到可下载的视频流")

        return {
            "filepath": str(filepath),
            "filename": filename,
            "title": title,
            "ext": "mp4",
        }

    def get_direct_url(self, url: str, format_id: str = "80") -> dict:
        share_url = self._extract_url(url)
        resolved = self._resolve_short_url(share_url)
        bvid = self._parse_bvid(resolved)
        if not bvid:
            raise ValueError("无法从链接中提取 BV 号")

        view = self._fetch_view(bvid)
        cid = view.get("cid")
        qn = int(format_id) if str(format_id).isdigit() else 80
        play_data = self._fetch_playurl(bvid, cid, qn)

        if play_data.get("durl"):
            direct_url = play_data["durl"][0]["url"]
            size = play_data["durl"][0].get("size")
        elif play_data.get("dash"):
            video_streams = play_data["dash"].get("video") or []
            if not video_streams:
                raise ValueError("未找到视频流")
            direct_url = video_streams[0]["baseUrl"]
            size = video_streams[0].get("size")
        else:
            raise ValueError("未找到可下载的视频流")

        return {
            "direct_url": direct_url,
            "ext": "mp4",
            "filesize": size,
            "title": view.get("title", "video"),
        }

    def _extract_url(self, text: str) -> str:
        match = _URL_PATTERN.search(text)
        if not match:
            raise ValueError("未找到有效的 B 站链接")
        return match.group(0).strip().strip('"').strip("'").rstrip(").,;!?")

    def _resolve_short_url(self, url: str) -> str:
        if "b23.tv" not in url:
            return url
        headers = {**DEFAULT_HEADERS, "Referer": "https://www.bilibili.com/"}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=self.timeout) as client:
            resp = client.get(url)
            return str(resp.url)

    @staticmethod
    def _parse_bvid(url: str) -> Optional[str]:
        match = re.search(r"(BV[a-zA-Z0-9]+)", url, re.IGNORECASE)
        return match.group(1) if match else None

    def _headers_for(self, bvid: str) -> dict:
        return {**DEFAULT_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}"}

    def _fetch_view(self, bvid: str) -> dict:
        headers = self._headers_for(bvid)
        with httpx.Client(headers=headers, timeout=self.timeout) as client:
            resp = client.get(
                "https://api.bilibili.com/x/web-interface/view",
                params={"bvid": bvid},
            )
            resp.raise_for_status()
            payload = resp.json()
        if payload.get("code") != 0:
            raise ValueError(payload.get("message") or "获取视频信息失败")
        data = payload.get("data")
        if not data:
            raise ValueError("视频不存在或无法访问")
        return data

    def _get_wbi_keys(self) -> tuple[str, str]:
        if self._wbi_keys and time.time() < self._wbi_expire_at:
            return self._wbi_keys

        headers = {**DEFAULT_HEADERS, "Referer": "https://www.bilibili.com/"}
        with httpx.Client(headers=headers, timeout=self.timeout) as client:
            resp = client.get("https://api.bilibili.com/x/web-interface/nav")
            resp.raise_for_status()
            payload = resp.json()

        wbi_img = payload.get("data", {}).get("wbi_img", {})
        img_url = wbi_img.get("img_url", "")
        sub_url = wbi_img.get("sub_url", "")
        if not img_url or not sub_url:
            raise ValueError("无法获取 B 站 WBI 密钥")

        img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
        sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
        self._wbi_keys = (img_key, sub_key)
        self._wbi_expire_at = time.time() + 3600
        return self._wbi_keys

    @staticmethod
    def _enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
        mixin_key = "".join((img_key + sub_key)[i] for i in MIXIN_KEY_ENC_TAB)[:32]
        signed = dict(params)
        signed["wts"] = int(time.time())
        signed = {k: signed[k] for k in sorted(signed)}
        signed = {
            k: "".join(ch for ch in str(signed[k]) if ch not in "!'()*")
            for k in signed
        }
        query = urlencode(signed)
        signed["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
        return signed

    def _fetch_playurl(self, bvid: str, cid: int, qn: int) -> dict:
        headers = self._headers_for(bvid)
        legacy_params = {
            "bvid": bvid,
            "cid": cid,
            "qn": qn,
            "fnval": 16,
            "fnver": 0,
            "fourk": 1,
            "otype": "json",
        }
        with httpx.Client(headers=headers, timeout=self.timeout) as client:
            resp = client.get(
                "https://api.bilibili.com/x/player/playurl",
                params=legacy_params,
            )
            resp.raise_for_status()
            payload = resp.json()

        if payload.get("code") == 0:
            data = payload.get("data") or {}
            if data.get("dash") or data.get("durl"):
                return data

        img_key, sub_key = self._get_wbi_keys()
        params = self._enc_wbi(
            {
                "bvid": bvid,
                "cid": cid,
                "qn": qn,
                "fnval": 4048,
                "fnver": 0,
                "fourk": 1,
            },
            img_key,
            sub_key,
        )
        with httpx.Client(headers=headers, timeout=self.timeout) as client:
            resp = client.get("https://api.bilibili.com/x/player/wbi/v2", params=params)
            resp.raise_for_status()
            payload = resp.json()

        if payload.get("code") != 0:
            raise ValueError(payload.get("message") or "获取播放地址失败")

        data = payload.get("data") or {}
        if data.get("dash") or data.get("durl"):
            return data
        raise ValueError("未找到播放地址")

    def _download_file(self, url: str, filepath: Path, referer: str):
        headers = {**DEFAULT_HEADERS, "Referer": referer}
        temp_path = filepath.with_suffix(filepath.suffix + ".part")
        with httpx.Client(headers=headers, follow_redirects=True, timeout=60.0) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with temp_path.open("wb") as f:
                    for chunk in resp.iter_bytes(64 * 1024):
                        if chunk:
                            f.write(chunk)
        temp_path.replace(filepath)

    def _download_dash(self, dash: dict, filepath: Path, referer: str):
        video_streams = dash.get("video") or []
        audio_streams = dash.get("audio") or []
        if not video_streams:
            raise ValueError("未找到视频流")

        video_path = filepath.with_suffix(".video.m4s")
        audio_path = filepath.with_suffix(".audio.m4s")
        try:
            self._download_file(video_streams[0]["baseUrl"], video_path, referer)
            if audio_streams:
                self._download_file(audio_streams[0]["baseUrl"], audio_path, referer)
                self._merge_av(video_path, audio_path, filepath)
            else:
                video_path.replace(filepath)
        finally:
            for p in (video_path, audio_path):
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    def _merge_av(self, video_path: Path, audio_path: Path, output_path: Path):
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            raise ValueError("需要 ffmpeg 合并音视频，请安装 ffmpeg 或 static-ffmpeg")

        cmd = [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"音视频合并失败: {result.stderr[-200:]}")

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        import shutil
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        try:
            import static_ffmpeg
            paths = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            return paths[0]
        except Exception:
            return None

    @staticmethod
    def _fmt_duration(seconds: Optional[int]) -> str:
        if not seconds:
            return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
