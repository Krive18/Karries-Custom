import json
import time

from app.schemas.product import MaterialPackageCreate, ProductCreate


MATERIAL_PACKAGE_FIELDS = (
    "id",
    "user_id",
    "product_id",
    "package_name",
    "package_type",
    "remark",
    "create_time",
    "update_time",
)


class ProductRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_product(self, user_id: int, payload: ProductCreate) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into product (
                        user_id, product_name, brand_name, category, sku,
                        price_cent, activity_price_cent, status, cover_material_id,
                        parameter_json, selling_point_json, ai_material_json,
                        create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, 1, 0, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        payload.product_name,
                        payload.brand_name,
                        payload.category,
                        payload.sku,
                        payload.price_cent,
                        payload.activity_price_cent,
                        self._dump_json(payload.parameter),
                        self._dump_json(payload.selling_point),
                        self._dump_json(payload.ai_material),
                        now,
                        now,
                    ),
                )
                product_id = int(cursor.lastrowid)
            self.conn.commit()
            return product_id
        except Exception:
            self.conn.rollback()
            raise

    def list_products(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_product_sql()
                + """
                where user_id = %s
                order by id desc
                """,
                (user_id,),
            )
            return [self._row_to_product(row) for row in cursor.fetchall()]

    def get_for_user(self, user_id: int, product_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_product_sql()
                + """
                where user_id = %s and id = %s
                """,
                (user_id, product_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_product(row)

    def create_material_package(
        self,
        user_id: int,
        product_id: int,
        payload: MaterialPackageCreate,
    ) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                self._ensure_product_for_user(cursor, user_id, product_id)
                cursor.execute(
                    """
                    insert into product_material_package (
                        user_id, product_id, package_name, package_type,
                        remark, create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        product_id,
                        payload.package_name,
                        payload.package_type,
                        payload.remark,
                        now,
                        now,
                    ),
                )
                package_id = int(cursor.lastrowid)
            self.conn.commit()
            return package_id
        except Exception:
            self.conn.rollback()
            raise

    def list_material_packages(self, user_id: int, product_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            self._ensure_product_for_user(cursor, user_id, product_id)
            cursor.execute(
                """
                select id, user_id, product_id, package_name, package_type,
                       remark, create_time, update_time
                from product_material_package
                where user_id = %s and product_id = %s
                order by id desc
                """,
                (user_id, product_id),
            )
            return [self._row_to_material_package(row) for row in cursor.fetchall()]

    def get_material_package_for_user(
        self,
        user_id: int,
        product_id: int,
        package_id: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, product_id, package_name, package_type,
                       remark, create_time, update_time
                from product_material_package
                where user_id = %s and product_id = %s and id = %s
                """,
                (user_id, product_id, package_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_material_package(row)

    def _ensure_product_for_user(self, cursor, user_id: int, product_id: int) -> None:
        cursor.execute(
            "select id from product where user_id = %s and id = %s",
            (user_id, product_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("product does not exist")

    def _select_product_sql(self) -> str:
        return """
            select id, user_id, product_name, brand_name, category, sku,
                   price_cent, activity_price_cent, status, cover_material_id,
                   parameter_json, selling_point_json, ai_material_json,
                   create_time, update_time
            from product
            """

    def _row_to_product(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "product_name": row["product_name"],
            "brand_name": row["brand_name"],
            "category": row["category"],
            "sku": row["sku"],
            "price_cent": row["price_cent"],
            "activity_price_cent": row["activity_price_cent"],
            "status": row["status"],
            "cover_material_id": row["cover_material_id"],
            "parameter": self._load_json_dict(row["parameter_json"]),
            "selling_point": self._load_json_dict(row["selling_point_json"]),
            "ai_material": self._load_json_dict(row["ai_material_json"]),
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _row_to_material_package(self, row: dict) -> dict:
        return {field: row[field] for field in MATERIAL_PACKAGE_FIELDS}

    def _dump_json(self, value: dict) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _load_json_dict(self, raw_value: str) -> dict:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}
