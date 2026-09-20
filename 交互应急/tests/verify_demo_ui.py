from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "frontend" / "index.html"
SERVER_PY = ROOT / "backend" / "server.py"


def read_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def read_server() -> str:
    return SERVER_PY.read_text(encoding="utf-8")


def load_server_module():
    spec = importlib.util.spec_from_file_location("emergency_server", SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sidebar_has_core_business_modules():
    html = read_index()

    for section in ["creation", "clip", "products", "schedule", "settings"]:
        assert f'data-section="{section}"' in html

    for label in ["鐖嗘瑙ｆ瀽", "鏅鸿兘鍒涗綔", "浜у搧鐭ヨ瘑搴?, "瀹氭椂鍙戝竷", "绯荤粺閰嶇疆"]:
        assert label in html


def test_main_has_switchable_sections():
    html = read_index()

    for section in ["creation", "clip", "products", "schedule", "settings"]:
        assert f'id="section-{section}"' in html

    assert "function setActiveSection" in html


def test_product_knowledge_base_has_complete_first_version_flow():
    html = read_index()

    for text in ["涓婁紶浜у搧璧勬枡", "AI 璇嗗埆淇℃伅", "浜哄伐纭淇", "瀵煎叆浜у搧搴?]:
        assert text in html

    for element_id in [
        "productFileInput",
        "recognizeProductBtn",
        "productNameInput",
        "productSellingPointsText",
        "importProductBtn",
        "productLibraryList",
        "useProductForCreationBtn",
    ]:
        assert f'id="{element_id}"' in html

    assert "function recognizeProduct" in html
    assert "function importProduct" in html
    assert "function useProductForCreation" in html


def test_core_creation_controls_remain_available():
    html = read_index()

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
    html = read_index()

    for forbidden in ["婕旂ず妯″紡", "褰撳墠 Demo", "Demo", "娴嬭瘯鏁版嵁", "閮ㄧ讲棰勭暀", "婕旂ず浠诲姟"]:
        assert forbidden not in html


def test_customer_flow_has_required_business_controls():
    html = read_index()

    assert 'id="aiProvider"' in html
    assert "鐐圭粯鐜悆AI鏅鸿兘浣? in html
    assert 'class="ai-agent-card"' in html
    assert 'id="publishContentType"' in html
    assert "鍥炬枃绗旇" in html
    assert 'id="contentDirection"' in html
    assert '<select id="style"' not in html
    assert ">鑷畾涔?" not in html
    assert "灏忕孩涔︾鑽? in html
    assert 'id="publishTime" type="datetime-local"' in html
    assert 'id="clipPublishTime" type="datetime-local"' in html


def test_settings_use_generic_ai_key_and_multi_account_management():
    html = read_index()

    assert 'data-hidden-ai-config="true"' in html
    assert "account-only-grid" in html
    assert "灏忕孩涔﹁处鍙风鐞? in html
    assert "鎵爜鐧诲綍" in html
    assert "璐﹀彿瀹氫綅" in html
    assert 'id="accountRows"' in html
    assert 'id="addAccountBtn"' in html
    assert 'id="accountNameInput"' in html
    assert "妫€鏌ヨ处鍙烽厤缃? in html


def test_creation_flow_can_choose_publish_account():
    html = read_index()

    assert "鍙戝竷璐﹀彿" in html
    assert 'id="publishAccountSelect"' in html
    assert 'id="currentAccountBadge"' in html
    assert "璇烽€夋嫨鍙戝竷璐﹀彿" in html
    assert "syncPublishAccountSelect" in html


def test_backend_exposes_ai_status_and_product_apis_without_secret():
    server = read_server()

    for route in [
        "/api/config/ai-status",
        "/api/products",
        "/api/products/recognize",
        "/api/products/import",
    ]:
        assert route in server

    assert "DEEPSEEK_API_KEY" in server
    assert "sk-" not in server


def test_blank_ai_product_fields_do_not_overwrite_local_fallback():
    server = load_server_module()
    payload = {
        "materials": [
            {
                "id": "file_001",
                "name": "KARRIES-heyi-necklace.jpg",
                "kind": "image",
                "type": "image/jpeg",
                "sizeLabel": "320 KB",
            }
        ]
    }
    ai_result = {
        "basic_info": {
            "product_name": "",
            "brand": "",
            "category": "鍏朵粬",
            "sku": "",
            "spec": "",
            "price": "",
        },
        "content_info": {
            "selling_points": []
        },
    }

    normalized = server.normalize_product_result(ai_result, payload)

    assert normalized["basic_info"]["product_name"] == "KARRIES heyi necklace"
    assert normalized["content_info"]["selling_points"]


def test_backend_serves_frontend_assets():
    server = read_server()

    assert 'path.startswith("/assets/")' in server
    assert "FRONTEND_DIR / relative_asset" in server


def test_secret_key_is_not_hardcoded():
    html = read_index()

    assert 'value="sk-' not in html
    assert 'localStorage.setItem("xhs_workspace_ai_key", "sk-' not in html


def test_karries_visual_language_is_applied_without_reference_fake_data():
    html = read_index()

    assert "KARRIES" in html
    assert "绂句竴鏂? in html
    assert "assets/karries-monogram.png" in html
    assert 'class="brand-avatar"' in html
    assert "--brand-dark: #693913" in html
    assert "--panel: rgba(255, 253, 249" in html
    assert "PROVIDER_KEY_REDACTED" not in html
    assert "璇峰湪瀹為檯椤圭洰涓帴鍏? not in html


def test_ai_empty_state_uses_karries_brand_illustration():
    html = read_index()

    assert "result-empty-card" in html
    assert "assets/karries-angel-mark.png" in html
    assert "寮€澶撮挬瀛? in html
    assert "鍐呭缁撴瀯" in html
    assert "鏍囩绛栫暐" in html
    assert "澶嶇敤鑴氭湰" in html


def test_clip_creation_module_has_video_editing_workflow():
    html = read_index()

    for element_id in [
        "clipProductSelect",
        "clipProductAssetsPreview",
        "loadProductAssetsBtn",
        "autoClipFromProductBtn",
        "clipUploadZone",
        "clipFileInput",
        "generateClipBtn",
        "clipStoryboard",
        "clipScript",
        "addClipTaskBtn",
    ]:
        assert f'id="{element_id}"' in html

    for text in ["AI 鑷姩鍓緫", "浜у搧搴撶礌鏉愭潵婧?, "杞藉叆浜у搧绱犳潗", "涓€閿敓鎴愭柟妗?, "鐢熸垚鍓緫鏂规", "闀滃ご椤哄簭", "鍔犲叆瑙嗛瀹氭椂鍙戝竷"]:
        assert text in html

    assert "function loadSelectedProductAssets" in html
    assert "function renderClipProductSelect" in html
    assert "function generateClipPlan" in html
    assert "function addClipTask" in html


def test_sidebar_navigation_keeps_full_card_components():
    html = read_index()

    assert ".nav-card::before" in html
    assert "grid-template-columns: 30px minmax(0, 1fr)" in html
    assert ".nav-kicker::after" in html
    assert ".nav-card small" in html


def test_product_material_upload_labels_image_video_and_document_types():
    html = read_index()

    assert "function fileKindLabel" in html
    assert "function mediaPreviewSrc" in html
    assert "previewDataUrl" in html
    assert "鍥剧墖璧勬枡" in html
    assert "瑙嗛璧勬枡" in html
    assert "鏂囨。璧勬枡" in html
    assert "data-remove-product-file" in html


def test_backend_preserves_product_asset_preview_fields():
    server = load_server_module()
    payload = {
        "materials": [
            {
                "id": "img_001",
                "name": "product.jpg",
                "kind": "image",
                "type": "image/jpeg",
                "sizeLabel": "120 KB",
                "previewDataUrl": "data:image/jpeg;base64,abc",
                "thumbnailUrl": "",
                "previewUrl": "blob:http://local/product",
            }
        ]
    }

    normalized = server.normalize_product_result({"assets": []}, payload)

    assert normalized["assets"][0]["previewDataUrl"] == "data:image/jpeg;base64,abc"
    assert normalized["assets"][0]["previewUrl"] == "blob:http://local/product"


def test_schedule_tasks_can_adjust_publish_time_inline():
    html = read_index()

    assert "data-time-input" in html
    assert "data-save-time" in html
    assert "淇濆瓨鏃堕棿" in html
    assert "function normalizeDateTimeLocal" in html
