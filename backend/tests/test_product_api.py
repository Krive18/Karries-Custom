import pytest

from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import UserRepository
from app.schemas.product import MaterialPackageCreate


class FakeProductCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.lower().split())
        self.conn.statements.append(normalized)
        self._row = None
        if normalized.startswith("select id from product where"):
            self._row = {"id": params[1]} if self.conn.product_exists else None
        elif normalized.startswith("insert into product_material_package"):
            self.lastrowid = 99

    def fetchone(self):
        return self._row


class FakeProductConnection:
    def __init__(self, product_exists=True):
        self.product_exists = product_exists
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return FakeProductCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-PRODUCT-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="product-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"product_user_{suffix}",
            "nickname": f"Product User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_product_json_fields_roundtrip_in_repository():
    conn = FakeProductConnection()
    row = {
        "id": 7,
        "user_id": 12,
        "product_name": "精华液",
        "brand_name": "KARRIES",
        "category": "护肤",
        "sku": "SKU-7",
        "price_cent": 12900,
        "activity_price_cent": 9900,
        "status": 1,
        "cover_material_id": 0,
        "parameter_json": '{"功效": "补水", "容量": "30ml"}',
        "selling_point_json": '{"主卖点": ["温和", "清爽"]}',
        "ai_material_json": '{"人群": "敏感肌"}',
        "create_time": 1710000000,
        "update_time": 1710000001,
    }

    product = ProductRepository(conn)._row_to_product(row)

    assert product["parameter"] == {"功效": "补水", "容量": "30ml"}
    assert product["selling_point"] == {"主卖点": ["温和", "清爽"]}
    assert product["ai_material"] == {"人群": "敏感肌"}
    assert "parameter_json" not in product
    assert "selling_point_json" not in product
    assert "ai_material_json" not in product


def test_create_material_package_rolls_back_when_product_missing():
    conn = FakeProductConnection(product_exists=False)

    with pytest.raises(ValueError, match="product does not exist"):
        ProductRepository(conn).create_material_package(
            12,
            404,
            MaterialPackageCreate(package_name="主图素材"),
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1
    assert any("select id from product where" in statement for statement in conn.statements)
    assert not any("insert into product_material_package" in statement for statement in conn.statements)


def test_create_product_and_list(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "create")
    payload = {
        "product_name": "KARRIES 精华液",
        "brand_name": "KARRIES",
        "category": "护肤",
        "sku": "KRS-001",
        "price_cent": 12900,
        "activity_price_cent": 9900,
        "parameter": {"容量": "30ml", "适用肤质": "敏感肌"},
        "selling_point": {"卖点": ["温和", "清爽不黏"]},
        "ai_material": {"场景": "夏季通勤"},
    }

    response = mysql_app_client.post("/api/products", headers=headers, json=payload)

    assert response.status_code == 200
    created = response.json()["data"]
    assert created["id"] > 0
    assert created["product_name"] == "KARRIES 精华液"
    assert created["brand_name"] == "KARRIES"
    assert created["category"] == "护肤"
    assert created["sku"] == "KRS-001"
    assert created["price_cent"] == 12900
    assert created["activity_price_cent"] == 9900
    assert created["parameter"] == {"容量": "30ml", "适用肤质": "敏感肌"}
    assert created["selling_point"] == {"卖点": ["温和", "清爽不黏"]}
    assert created["ai_material"] == {"场景": "夏季通勤"}

    list_response = mysql_app_client.get("/api/products", headers=headers)

    assert list_response.status_code == 200
    products = list_response.json()["data"]
    assert len(products) == 1
    assert products[0]["id"] == created["id"]
    assert products[0]["parameter"] == payload["parameter"]
    assert products[0]["selling_point"] == payload["selling_point"]
    assert products[0]["ai_material"] == payload["ai_material"]


def test_products_are_user_isolated(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    create_response = mysql_app_client.post(
        "/api/products",
        headers=owner_headers,
        json={"product_name": "Owner product"},
    )
    assert create_response.status_code == 200
    product_id = create_response.json()["data"]["id"]

    list_response = mysql_app_client.get("/api/products", headers=other_headers)

    assert list_response.status_code == 200
    assert list_response.json()["data"] == []

    get_response = mysql_app_client.get(f"/api/products/{product_id}", headers=other_headers)

    assert get_response.status_code == 404
    payload = get_response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_create_and_list_material_package(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "package")
    create_product_response = mysql_app_client.post(
        "/api/products",
        headers=headers,
        json={"product_name": "Package product"},
    )
    assert create_product_response.status_code == 200
    product_id = create_product_response.json()["data"]["id"]

    create_package_response = mysql_app_client.post(
        f"/api/products/{product_id}/material-packages",
        headers=headers,
        json={
            "package_name": "主图素材",
            "package_type": "image",
            "remark": "首批素材",
        },
    )

    assert create_package_response.status_code == 200
    created = create_package_response.json()["data"]
    assert created["id"] > 0
    assert created["product_id"] == product_id
    assert created["package_name"] == "主图素材"
    assert created["package_type"] == "image"
    assert created["remark"] == "首批素材"

    list_response = mysql_app_client.get(
        f"/api/products/{product_id}/material-packages",
        headers=headers,
    )

    assert list_response.status_code == 200
    packages = list_response.json()["data"]
    assert len(packages) == 1
    assert packages[0]["id"] == created["id"]
    assert packages[0]["package_name"] == "主图素材"


def test_material_package_rejects_cross_user_product(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "package-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "package-other")
    create_product_response = mysql_app_client.post(
        "/api/products",
        headers=owner_headers,
        json={"product_name": "Owner package product"},
    )
    assert create_product_response.status_code == 200
    product_id = create_product_response.json()["data"]["id"]

    response = mysql_app_client.post(
        f"/api/products/{product_id}/material-packages",
        headers=other_headers,
        json={"package_name": "should fail"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_products_require_auth(app_client_without_db):
    response = app_client_without_db.get("/api/products")

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"
