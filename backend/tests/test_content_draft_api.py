from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-DRAFT-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="content-draft-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"draft_user_{suffix}",
            "nickname": f"Draft User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_product(mysql_app_client, headers: dict[str, str], suffix: str) -> int:
    response = mysql_app_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_name": f"Karries serum {suffix}",
            "brand_name": "KARRIES",
            "category": "skincare",
            "selling_point": {"points": ["gentle", "daily routine"]},
            "ai_material": {"scene": "morning commute", "audience": "office worker"},
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_xhs_account(mysql_app_client, headers: dict[str, str], suffix: str) -> int:
    response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": f"Draft account {suffix}",
            "profile": {
                "persona": "gentle skincare advisor",
                "target_audience": "office workers",
                "tone": "natural",
                "tag_preferences": "[\"#skincare\", \"#routine\"]",
            },
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_content_draft_generate_schema_defaults_to_reviewable_copy():
    from app.schemas.content_draft import ContentDraftGenerateRequest

    payload = ContentDraftGenerateRequest(product_id=7)

    assert payload.product_id == 7
    assert payload.xhs_account_id == 0
    assert payload.content_direction == "xiaohongshu_seed"
    assert payload.tone == "natural"
    assert payload.extra_requirement == ""


def test_product_copy_service_uses_product_and_account_context():
    from app.schemas.content_draft import ContentDraftGenerateRequest
    from app.services.product_copy_service import generate_product_content_draft

    product = {
        "product_name": "Karries serum",
        "brand_name": "KARRIES",
        "category": "skincare",
        "selling_point": {"points": ["gentle", "daily routine"]},
        "ai_material": {"scene": "morning commute"},
    }
    account = {
        "display_name": "Karries main",
        "profile": {
            "persona": "gentle skincare advisor",
            "target_audience": "office workers",
            "tone": "natural",
            "tag_preferences": "[\"#skincare\", \"#routine\"]",
        },
    }

    draft = generate_product_content_draft(
        product,
        account,
        ContentDraftGenerateRequest(
            product_id=7,
            xhs_account_id=11,
            extra_requirement="mention lightweight texture",
        ),
    )

    assert draft["title"]
    assert "Karries serum" in draft["body"]
    assert "gentle" in draft["body"]
    assert "office workers" in draft["body"]
    assert "lightweight texture" in draft["body"]
    assert "#skincare" in draft["tags"]
    assert draft["material"]["product_id"] == 7
    assert draft["material"]["xhs_account_id"] == 11


def test_generate_product_copy_returns_404_when_product_missing(monkeypatch):
    from app.api import content_drafts as content_drafts_api
    from app.schemas.content_draft import ContentDraftGenerateRequest

    class FakeProductRepository:
        def __init__(self, _conn):
            pass

        def get_for_user(self, _user_id, _product_id):
            return None

    class FakeXHSAccountRepository:
        def __init__(self, _conn):
            pass

        def get_for_user(self, _user_id, _account_id):
            raise AssertionError("account should not be read when product is missing")

    class FakeContentDraftRepository:
        def __init__(self, _conn):
            pass

        def create_draft(self, *_args, **_kwargs):
            raise AssertionError("draft should not be created when product is missing")

    monkeypatch.setattr(content_drafts_api, "ProductRepository", FakeProductRepository)
    monkeypatch.setattr(content_drafts_api, "XHSAccountRepository", FakeXHSAccountRepository)
    monkeypatch.setattr(content_drafts_api, "ContentDraftRepository", FakeContentDraftRepository)

    response = content_drafts_api.generate_product_copy(
        ContentDraftGenerateRequest(product_id=404),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 404
    assert b"NOT_FOUND" in response.body


def test_content_drafts_require_auth(app_client_without_db):
    response = app_client_without_db.get("/api/content-drafts")

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"


def test_generate_list_and_confirm_content_draft(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "flow")
    product_id = create_product(mysql_app_client, headers, "flow")
    account_id = create_xhs_account(mysql_app_client, headers, "flow")

    generate_response = mysql_app_client.post(
        "/api/content-drafts/product-copy",
        headers=headers,
        json={
            "product_id": product_id,
            "xhs_account_id": account_id,
            "extra_requirement": "keep the copy friendly",
        },
    )

    assert generate_response.status_code == 200
    draft = generate_response.json()["data"]
    assert draft["id"] > 0
    assert draft["product_id"] == product_id
    assert draft["xhs_account_id"] == account_id
    assert draft["status"] == "draft"
    assert "Karries serum flow" in draft["body"]
    assert draft["tags"]

    list_response = mysql_app_client.get("/api/content-drafts", headers=headers)

    assert list_response.status_code == 200
    rows = list_response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["id"] == draft["id"]

    update_response = mysql_app_client.patch(
        f"/api/content-drafts/{draft['id']}",
        headers=headers,
        json={
            "title": "Friendly routine note",
            "body": "Final reviewed copy",
            "tags": ["#reviewed", "#skincare"],
            "status": "confirmed",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["status"] == "confirmed"
    assert updated["title"] == "Friendly routine note"
    assert updated["body"] == "Final reviewed copy"
    assert updated["tags"] == ["#reviewed", "#skincare"]


def test_content_drafts_are_user_isolated(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    product_id = create_product(mysql_app_client, owner_headers, "owner")

    generate_response = mysql_app_client.post(
        "/api/content-drafts/product-copy",
        headers=owner_headers,
        json={"product_id": product_id},
    )
    assert generate_response.status_code == 200
    draft_id = generate_response.json()["data"]["id"]

    list_response = mysql_app_client.get("/api/content-drafts", headers=other_headers)
    assert list_response.status_code == 200
    assert list_response.json()["data"] == []

    update_response = mysql_app_client.patch(
        f"/api/content-drafts/{draft_id}",
        headers=other_headers,
        json={"status": "confirmed"},
    )

    assert update_response.status_code == 404
    assert update_response.json()["error"]["code"] == "NOT_FOUND"
