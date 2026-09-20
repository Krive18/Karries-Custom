import json


class AdminProductLibraryRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def summary(self, tenant_id: int) -> dict:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select
                    count(*) as product_count,
                    coalesce(sum(case when p.status = 1 then 1 else 0 end), 0)
                        as active_product_count
                from product p
                join app_user u on u.id = p.user_id
                where u.tenant_id = %s and u.user_role = 'customer'
                """,
                (tenant_id,),
            )
            product = cursor.fetchone()
            cursor.execute(
                """
                select
                    count(*) as asset_count,
                    coalesce(sum(case when file_type = 'image' then 1 else 0 end), 0)
                        as image_count,
                    coalesce(sum(case when file_type = 'video' then 1 else 0 end), 0)
                        as video_count,
                    coalesce(sum(case when file_type in ('word', 'excel', 'other') then 1 else 0 end), 0)
                        as document_count,
                    coalesce(sum(file_size), 0) as storage_bytes
                from material_file
                where tenant_id = %s
                """,
                (tenant_id,),
            )
            asset = cursor.fetchone()
            cursor.execute(
                """
                select count(*) as folder_count
                from product_material_folder
                where tenant_id = %s
                """,
                (tenant_id,),
            )
            folder = cursor.fetchone()
        return {
            "product_count": int(product["product_count"] or 0),
            "active_product_count": int(product["active_product_count"] or 0),
            "folder_count": int(folder["folder_count"] or 0),
            "asset_count": int(asset["asset_count"] or 0),
            "image_count": int(asset["image_count"] or 0),
            "video_count": int(asset["video_count"] or 0),
            "document_count": int(asset["document_count"] or 0),
            "storage_bytes": int(asset["storage_bytes"] or 0),
        }

    def list_products(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        employee_id: int | None,
        status: int | None,
        keyword: str,
    ) -> dict:
        where = ["u.tenant_id = %s", "u.user_role = 'customer'"]
        params: list[object] = [tenant_id]
        if employee_id is not None:
            where.append("p.user_id = %s")
            params.append(employee_id)
        if status is not None:
            where.append("p.status = %s")
            params.append(status)
        if keyword:
            where.append(
                "(p.product_name like %s or p.brand_name like %s or p.sku like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like])
        where_sql = " and ".join(where)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from product p
                join app_user u on u.id = p.user_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                select p.id, p.user_id, p.product_name, p.brand_name,
                       p.category, p.sku, p.price_cent,
                       p.activity_price_cent, p.status,
                       p.cover_material_id, p.parameter_json,
                       p.selling_point_json, p.ai_material_json,
                       p.create_time, p.update_time,
                       u.nickname as employee_name,
                       u.login_name as employee_login,
                       (
                           select count(*) from material_file m
                           where m.tenant_id = u.tenant_id
                             and m.product_id = p.id
                       ) as material_count
                from product p
                join app_user u on u.id = p.user_id
                where {where_sql}
                order by p.update_time desc, p.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._product_from_row(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def update_product_status(
        self,
        tenant_id: int,
        product_id: int,
        status: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update product p
                join app_user u on u.id = p.user_id
                set p.status = %s,
                    p.update_time = unix_timestamp()
                where p.id = %s
                  and u.tenant_id = %s
                  and u.user_role = 'customer'
                """,
                (status, product_id, tenant_id),
            )
            if cursor.rowcount != 1:
                self.conn.rollback()
                return None
        self.conn.commit()
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select p.id, p.user_id, p.product_name, p.brand_name,
                       p.category, p.sku, p.price_cent,
                       p.activity_price_cent, p.status,
                       p.cover_material_id, p.parameter_json,
                       p.selling_point_json, p.ai_material_json,
                       p.create_time, p.update_time,
                       u.nickname as employee_name,
                       u.login_name as employee_login,
                       (
                           select count(*) from material_file m
                           where m.tenant_id = u.tenant_id
                             and m.product_id = p.id
                       ) as material_count
                from product p
                join app_user u on u.id = p.user_id
                where p.id = %s and u.tenant_id = %s
                """,
                (product_id, tenant_id),
            )
            row = cursor.fetchone()
        return None if row is None else self._product_from_row(row)

    @staticmethod
    def _load_json(raw_value: str) -> dict:
        try:
            value = json.loads(raw_value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _product_from_row(self, row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "product_name": row["product_name"],
            "brand_name": row["brand_name"],
            "category": row["category"],
            "sku": row["sku"],
            "price_cent": int(row["price_cent"] or 0),
            "activity_price_cent": int(row["activity_price_cent"] or 0),
            "status": int(row["status"]),
            "cover_material_id": int(row["cover_material_id"] or 0),
            "parameter": self._load_json(row["parameter_json"]),
            "selling_point": self._load_json(row["selling_point_json"]),
            "ai_material": self._load_json(row["ai_material_json"]),
            "material_count": int(row["material_count"] or 0),
            "employee_name": row["employee_name"],
            "employee_login": row["employee_login"],
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }
