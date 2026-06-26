from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "frontend" / "index.html"


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
        "demoDataBtn",
        "analyzeBtn",
        "fileInput",
        "resultTitle",
        "saveTaskBtn",
        "taskRows",
    ]:
        assert f'id="{element_id}"' in html
