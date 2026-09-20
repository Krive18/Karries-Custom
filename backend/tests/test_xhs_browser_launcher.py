import asyncio
import importlib
from pathlib import Path
import runpy
import sys

from app.integrations.xiaohongshu import _load_xiaohongshu_uploader
from app.services.xhs_account_login_service import friendly_login_error


def test_uploader_packages_import_without_writing_legacy_cookie_directories(
    monkeypatch,
):
    external_root = (
        Path(__file__).resolve().parents[2]
        / "external"
        / "social-auto-upload-xiaohongshu"
    )
    blocked_paths = {
        external_root / "cookies",
        external_root / "cookies" / "xiaohongshu_uploader",
    }
    original_mkdir = Path.mkdir

    def reject_legacy_cookie_directory(path, *args, **kwargs):
        if path in blocked_paths:
            raise OSError(30, "Read-only file system", str(path))
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.syspath_prepend(str(external_root))
    monkeypatch.setattr(Path, "mkdir", reject_legacy_cookie_directory)

    runpy.run_path(str(external_root / "uploader" / "__init__.py"))
    runpy.run_path(
        str(external_root / "uploader" / "xiaohongshu_uploader" / "__init__.py")
    )


def _uploader_module():
    _load_xiaohongshu_uploader()
    return sys.modules["uploader.xiaohongshu_uploader.main"]


def test_browser_resolver_prefers_explicit_executable(monkeypatch, tmp_path):
    browser = tmp_path / "browser.exe"
    browser.write_bytes(b"test")
    monkeypatch.setenv("SAU_BROWSER_EXECUTABLE_PATH", str(browser))

    module = _uploader_module()

    assert module._resolve_browser_executable_path() == str(browser)


def test_browser_launcher_passes_resolved_executable(monkeypatch, tmp_path):
    browser = tmp_path / "browser.exe"
    browser.write_bytes(b"test")
    monkeypatch.setenv("SAU_BROWSER_EXECUTABLE_PATH", str(browser))
    calls = []

    class FakeChromium:
        async def launch(self, **kwargs):
            calls.append(kwargs)
            return "browser"

    class FakePlaywright:
        chromium = FakeChromium()

    module = _uploader_module()
    launched = asyncio.run(module._launch_browser(FakePlaywright(), headless=True))

    assert launched == "browser"
    assert calls == [{"headless": True, "executable_path": str(browser)}]


def test_cookie_check_does_not_mark_creator_page_timeout_as_logged_out(
    monkeypatch, tmp_path
):
    account_file = tmp_path / "storage_state.json"
    account_file.write_text("{}", encoding="utf-8")
    module = _uploader_module()

    class FakeLocator:
        @property
        def first(self):
            return self

        async def count(self):
            return 0

    class FakePage:
        url = "https://creator.xiaohongshu.com/publish/publish?target=video"

        async def goto(self, *_args, **_kwargs):
            raise module.PlaywrightTimeoutError("navigation timeout")

        async def wait_for_timeout(self, _timeout):
            return None

        def locator(self, _selector):
            return FakeLocator()

    class FakeContext:
        async def new_page(self):
            return FakePage()

    class FakeBrowser:
        async def new_context(self, **_kwargs):
            return FakeContext()

        async def close(self):
            return None

    class FakeAsyncPlaywright:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    async def fake_launch(_playwright, *, headless):
        assert headless is True
        return FakeBrowser()

    async def fake_set_init_script(context):
        return context

    monkeypatch.setattr(module, "async_playwright", FakeAsyncPlaywright)
    monkeypatch.setattr(module, "_launch_browser", fake_launch)
    monkeypatch.setattr(module, "set_init_script", fake_set_init_script)

    assert asyncio.run(module.cookie_auth(str(account_file))) is True


def test_browser_startup_error_is_safe_for_frontend():
    error = RuntimeError(
        "BrowserType.launch: Chromium distribution 'chrome' is not found"
    )

    assert friendly_login_error(error) == (
        "无法启动账号授权浏览器，请安装或更新 Chrome、Microsoft Edge 后重试"
    )


def test_external_logger_uses_configured_writable_directory(monkeypatch, tmp_path):
    log_dir = tmp_path / "social-logs"
    monkeypatch.setenv("SAU_LOG_DIR", str(log_dir))
    _load_xiaohongshu_uploader()
    sys.modules.pop("utils.log", None)

    importlib.import_module("utils.log")

    assert log_dir.is_dir()


def test_qr_login_continues_after_login_page_navigation_timeout(monkeypatch, tmp_path):
    module = _uploader_module()
    calls = []
    qrcode_saved = []

    class FakePage:
        url = "https://creator.xiaohongshu.com/login"

        async def goto(self, url, **kwargs):
            calls.append((url, kwargs))
            raise module.PlaywrightTimeoutError("navigation timeout")

    class FakeContext:
        async def new_page(self):
            return FakePage()

        async def close(self):
            return None

    class FakeBrowser:
        async def new_context(self):
            return FakeContext()

        async def close(self):
            return None

    class FakeAsyncPlaywright:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    async def fake_launch(_playwright, *, headless):
        assert headless is True
        return FakeBrowser()

    async def fake_set_init_script(context):
        return context

    async def fake_save_qrcode(_page, account_file, **_kwargs):
        qrcode_saved.append(account_file)
        return {
            "image_path": str(tmp_path / "qr.png"),
            "image_data_url": "data:image/png;base64,cXI=",
        }

    monkeypatch.setattr(module, "async_playwright", FakeAsyncPlaywright)
    monkeypatch.setattr(module, "_launch_browser", fake_launch)
    monkeypatch.setattr(module, "set_init_script", fake_set_init_script)
    monkeypatch.setattr(module, "_save_xhs_qrcode", fake_save_qrcode)

    result = asyncio.run(
        module.xiaohongshu_cookie_gen(
            str(tmp_path / "storage_state.json"),
            max_checks=0,
            headless=True,
        )
    )

    assert result["status"] == "timeout"
    assert qrcode_saved == [str(tmp_path / "storage_state.json")]
    assert calls == [(
        "https://creator.xiaohongshu.com/login",
        {"wait_until": "domcontentloaded", "timeout": 45000},
    )]
