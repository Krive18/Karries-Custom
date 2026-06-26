from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "frontend" / "index.html"
SERVER_PY = ROOT / "backend" / "server.py"


def test_sidebar_has_three_business_modules():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-section="creation"' in html
    assert 'data-section="schedule"' in html
    assert 'data-section="settings"' in html
    assert "智能创作" in html
    assert "定时发布" in html
    assert "系统配置" in html


def test_main_has_three_switchable_sections():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="section-creation"' in html
    assert 'id="section-schedule"' in html
    assert 'id="section-settings"' in html
    assert "function setActiveSection" in html


def test_core_demo_controls_remain_available():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for element_id in [
        "apiKey",
        "analyzeBtn",
        "fileInput",
        "resultTitle",
        "saveTaskBtn",
        "taskRows",
    ]:
        assert f'id="{element_id}"' in html


def test_customer_facing_copy_has_no_internal_demo_language():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for forbidden in ["演示模式", "当前 Demo", "Demo", "测试数据", "部署预留", "演示任务"]:
        assert forbidden not in html


def test_customer_flow_has_required_business_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="aiProvider"' in html
    assert "DeepSeek" in html
    assert "GPT" in html
    assert "豆包" in html
    assert "Gemini" in html
    assert 'id="publishContentType"' in html
    assert "图文笔记" in html
    assert 'id="contentDirection"' in html
    assert '<select id="style"' not in html
    assert ">自定义<" not in html
    assert "小红书种草" in html


def test_settings_use_generic_ai_key_and_multi_account_management():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "AI API KEY" in html
    assert "DeepSeek API Key" not in html
    assert "小红书账号管理" in html
    assert 'id="accountRows"' in html
    assert 'id="addAccountBtn"' in html
    assert 'id="accountNameInput"' in html


def test_creation_flow_can_choose_publish_account():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "发布账号" in html
    assert 'id="publishAccountSelect"' in html
    assert 'id="currentAccountBadge"' in html
    assert "请选择发布账号" in html
    assert "syncPublishAccountSelect" in html


def test_backend_exposes_ai_status_without_secret():
    server = SERVER_PY.read_text(encoding="utf-8")

    assert "/api/config/ai-status" in server
    assert "DEEPSEEK_API_KEY" in server
    assert "sk-" not in server


def test_secret_key_is_not_hardcoded():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'value="sk-' not in html
    assert 'localStorage.setItem("xhs_workspace_ai_key", "sk-' not in html
