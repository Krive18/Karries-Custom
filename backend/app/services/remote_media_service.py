from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


class RemoteMediaError(ValueError):
    pass


@dataclass(frozen=True)
class RemoteMedia:
    path: Path
    media_type: str
    mime_type: str
    source_url: str

    def cleanup(self) -> None:
        self.path.unlink(missing_ok=True)


class _MediaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {str(key).lower(): value for key, value in attrs if value}
        if tag.lower() == "meta":
            key = str(values.get("property") or values.get("name") or "").lower()
            if key in {
                "og:video",
                "og:video:url",
                "og:video:secure_url",
                "twitter:player:stream",
            }:
                self.candidates.append(str(values.get("content", "")))
        elif tag.lower() in {"video", "source"}:
            self.candidates.append(str(values.get("src", "")))


class RemoteMediaService:
    _MAX_HTML_BYTES = 2 * 1024 * 1024
    _MAX_MEDIA_BYTES = 60 * 1024 * 1024
    _MAX_REDIRECTS = 5
    _TIMEOUT = (10, 60)
    _URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,video/*,image/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    _MOBILE_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,video/*,image/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, source_url: str) -> RemoteMedia:
        normalized_url = self._extract_source_url(source_url)
        self._validate_public_url(normalized_url)
        page_headers = (
            self._MOBILE_HEADERS if self._is_douyin_url(normalized_url) else self._HEADERS
        )

        with requests.Session() as session:
            response = self._get_with_safe_redirects(
                session,
                normalized_url,
                headers=page_headers,
            )
            content_type = self._content_type(response)
            if content_type.startswith(("video/", "image/")):
                return self._save_media_response(response, content_type)

            if content_type not in {"text/html", "application/xhtml+xml"}:
                response.close()
                raise RemoteMediaError("该链接没有返回可识别的视频内容，请改用本地视频上传")

            page_url = response.url
            page_html = self._read_limited_text(response)
            media_url = ""
            if self._is_douyin_url(page_url):
                media_url = self._extract_douyin_media_url(page_html, page_url)
            if not media_url:
                media_url = self._extract_media_url(page_html, page_url)
            if not media_url:
                raise RemoteMediaError(
                    "该平台未公开可读取的视频地址，请下载原视频后改用本地视频上传"
                )

            media_headers = dict(page_headers)
            media_headers.update(
                {
                    "Referer": page_url,
                    "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                }
            )
            media_response = self._get_with_safe_redirects(
                session,
                media_url,
                headers=media_headers,
            )
            media_type = self._content_type(media_response)
            if not media_type.startswith(("video/", "image/")):
                media_response.close()
                raise RemoteMediaError("视频地址已失效，请重新获取链接或改用本地视频上传")
            return self._save_media_response(media_response, media_type)

    def _get_with_safe_redirects(
        self,
        session: requests.Session,
        source_url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        current_url = source_url
        request_headers = dict(self._HEADERS)
        if headers:
            request_headers.update(headers)
        for _ in range(self._MAX_REDIRECTS + 1):
            self._validate_public_url(current_url)
            try:
                response = session.get(
                    current_url,
                    headers=request_headers,
                    timeout=self._TIMEOUT,
                    stream=True,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise RemoteMediaError("视频链接访问失败，请检查链接后重试") from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location", "").strip()
                response.close()
                if not location:
                    raise RemoteMediaError("视频链接重定向地址无效")
                current_url = urljoin(current_url, location)
                continue

            if response.status_code < 200 or response.status_code >= 300:
                status_code = response.status_code
                response.close()
                raise RemoteMediaError(f"视频链接访问失败（HTTP {status_code}）")
            return response

        raise RemoteMediaError("视频链接重定向次数过多，请改用本地视频上传")

    def _save_media_response(
        self,
        response: requests.Response,
        content_type: str,
    ) -> RemoteMedia:
        resolved_source_url = response.url
        content_length = response.headers.get("Content-Length", "").strip()
        if content_length.isdigit() and int(content_length) > self._MAX_MEDIA_BYTES:
            response.close()
            raise RemoteMediaError("视频文件超过 60MB，请压缩后使用本地视频上传")

        media_type = "video" if content_type.startswith("video/") else "image"
        suffix = self._suffix_for(content_type, response.url)
        temp_file = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="viral-link-",
            suffix=suffix,
            dir=self.storage_dir,
            delete=False,
        )
        path = Path(temp_file.name)
        size = 0
        try:
            with temp_file:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self._MAX_MEDIA_BYTES:
                        raise RemoteMediaError(
                            "视频文件超过 60MB，请压缩后使用本地视频上传"
                        )
                    temp_file.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            response.close()

        if size == 0:
            path.unlink(missing_ok=True)
            raise RemoteMediaError("视频链接返回了空文件，请改用本地视频上传")
        return RemoteMedia(
            path=path,
            media_type=media_type,
            mime_type=content_type,
            source_url=resolved_source_url,
        )

    def _read_limited_text(self, response: requests.Response) -> str:
        content_length = response.headers.get("Content-Length", "").strip()
        if content_length.isdigit() and int(content_length) > self._MAX_HTML_BYTES:
            response.close()
            raise RemoteMediaError("视频页面内容过大，无法安全读取")

        data = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                data.extend(chunk)
                if len(data) > self._MAX_HTML_BYTES:
                    raise RemoteMediaError("视频页面内容过大，无法安全读取")
        finally:
            encoding = response.encoding or "utf-8"
            response.close()
        return bytes(data).decode(encoding, errors="replace")

    def _extract_media_url(self, page_html: str, page_url: str) -> str:
        parser = _MediaHTMLParser()
        parser.feed(page_html)
        candidates = list(parser.candidates)

        patterns = (
            r'"(?:masterUrl|master_url|videoUrl|video_url|playUrl|play_url)"\s*:\s*"([^"]+)"',
            r'"url"\s*:\s*"(https?:[^"]+\.(?:mp4|mov|webm)(?:\?[^"]*)?)"',
            r"(https?://[^\s\"'<>\\]+?\.(?:mp4|mov|webm)(?:\?[^\s\"'<>\\]*)?)",
        )
        for pattern in patterns:
            candidates.extend(
                match.group(1) for match in re.finditer(pattern, page_html, re.IGNORECASE)
            )

        for candidate in candidates:
            normalized = self._decode_embedded_url(candidate)
            if not normalized:
                continue
            resolved = urljoin(page_url, normalized)
            try:
                self._validate_public_url(resolved)
            except RemoteMediaError:
                continue
            return resolved
        return ""

    def _extract_douyin_media_url(self, page_html: str, page_url: str) -> str:
        patterns = (
            r'"play_addr"\s*:\s*\{.*?"url_list"\s*:\s*\[\s*"([^"]+)"',
            r'"play_url"\s*:\s*\{.*?"url_list"\s*:\s*\[\s*"([^"]+)"',
        )
        for pattern in patterns:
            match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            normalized = self._decode_embedded_url(match.group(1))
            resolved = urljoin(page_url, normalized)
            try:
                self._validate_public_url(resolved)
            except RemoteMediaError:
                continue
            return resolved
        return ""

    @classmethod
    def _extract_source_url(cls, source_text: str) -> str:
        normalized = str(source_text or "").strip()
        if not normalized:
            raise RemoteMediaError("请输入视频链接或包含视频链接的分享口令")
        if len(normalized) > 8192:
            raise RemoteMediaError("分享口令内容过长，请仅粘贴视频分享内容")

        match = cls._URL_PATTERN.search(normalized)
        if not match:
            raise RemoteMediaError("未在分享内容中找到有效的视频链接")
        return match.group(0).rstrip("。；，、！？!?,;:）)]}】>")

    @staticmethod
    def _is_douyin_url(source_url: str) -> bool:
        host = (urlparse(source_url).hostname or "").lower().rstrip(".")
        return any(
            host == domain or host.endswith(f".{domain}")
            for domain in ("douyin.com", "iesdouyin.com")
        )

    @staticmethod
    def _decode_embedded_url(value: str) -> str:
        normalized = html.unescape(value.strip())
        normalized = normalized.replace("\\/", "/")
        try:
            normalized = json.loads(f'"{normalized}"')
        except (json.JSONDecodeError, TypeError):
            normalized = re.sub(
                r"\\u([0-9a-fA-F]{4})",
                lambda match: chr(int(match.group(1), 16)),
                normalized,
            )
        return str(normalized).strip()

    @staticmethod
    def _content_type(response: requests.Response) -> str:
        return response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()

    @staticmethod
    def _suffix_for(content_type: str, source_url: str) -> str:
        by_type = {
            "video/mp4": ".mp4",
            "video/quicktime": ".mov",
            "video/webm": ".webm",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        if content_type in by_type:
            return by_type[content_type]
        suffix = Path(urlparse(source_url).path).suffix.lower()
        return suffix if suffix in {".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"} else ".bin"

    @staticmethod
    def _validate_public_url(source_url: str) -> None:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RemoteMediaError("请输入有效的 HTTP 或 HTTPS 视频链接")
        if parsed.username or parsed.password:
            raise RemoteMediaError("视频链接不能包含登录凭据")

        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(
                    parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                )
            }
        except socket.gaierror as exc:
            raise RemoteMediaError("无法解析视频链接域名，请检查链接") from exc

        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise RemoteMediaError("视频链接地址不允许访问")
