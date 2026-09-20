import time
from typing import Iterable


class MaterialLibraryNotFoundError(LookupError):
    pass


class MaterialLibraryConflictError(ValueError):
    pass


class MaterialLibraryRepository:
    DEFAULT_PROJECT_GROUP_NAME = "默认项目组"

    def __init__(self, conn) -> None:
        self.conn = conn

    def ensure_default_project_group(self, tenant_id: int, user_id: int) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert ignore into material_project_group (
                        tenant_id, group_name, created_by_user_id,
                        create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        self.DEFAULT_PROJECT_GROUP_NAME,
                        user_id,
                        now,
                        now,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        group = self._get_project_group_by_name(
            tenant_id,
            self.DEFAULT_PROJECT_GROUP_NAME,
        )
        if group is None:
            raise RuntimeError("default material project group was not found")
        return group

    def list_project_groups(self, tenant_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select project_group.id, project_group.tenant_id,
                       project_group.group_name,
                       project_group.created_by_user_id,
                       project_group.create_time,
                       greatest(
                           project_group.update_time,
                           coalesce(group_activity.latest_asset_update_time, 0)
                       ) as update_time,
                       (
                           select count(*)
                           from product_material_folder folder
                           where folder.tenant_id = project_group.tenant_id
                             and folder.project_group_id = project_group.id
                       ) as folder_count,
                       (
                           select count(*)
                           from material_file asset
                           join product_material_folder folder
                             on folder.tenant_id = asset.tenant_id
                            and folder.id = asset.folder_id
                           where asset.tenant_id = project_group.tenant_id
                             and folder.project_group_id = project_group.id
                       ) as asset_count
                from material_project_group project_group
                left join (
                    select folder.tenant_id, folder.project_group_id,
                           max(asset.update_time) as latest_asset_update_time
                    from product_material_folder folder
                    join material_file asset
                      on asset.tenant_id = folder.tenant_id
                     and asset.folder_id = folder.id
                    group by folder.tenant_id, folder.project_group_id
                ) group_activity
                  on group_activity.tenant_id = project_group.tenant_id
                 and group_activity.project_group_id = project_group.id
                where project_group.tenant_id = %s
                order by update_time desc, project_group.id desc
                """,
                (tenant_id,),
            )
            return [self._project_group_from_row(row) for row in cursor.fetchall()]

    def create_project_group(
        self,
        tenant_id: int,
        user_id: int,
        group_name: str,
    ) -> dict:
        clean_name = self._clean_project_group_name(group_name)
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into material_project_group (
                        tenant_id, group_name, created_by_user_id,
                        create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s)
                    """,
                    (tenant_id, clean_name, user_id, now, now),
                )
                project_group_id = int(cursor.lastrowid)
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            if self._is_duplicate_entry(exc):
                raise ValueError("project group name already exists") from exc
            raise
        group = self.get_project_group(tenant_id, project_group_id)
        if group is None:
            raise RuntimeError("created material project group was not found")
        return group

    def rename_project_group(
        self,
        tenant_id: int,
        project_group_id: int,
        group_name: str,
    ) -> dict:
        clean_name = self._clean_project_group_name(group_name)
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update material_project_group
                    set group_name = %s, update_time = %s
                    where tenant_id = %s and id = %s
                    """,
                    (clean_name, now, tenant_id, project_group_id),
                )
                if cursor.rowcount != 1:
                    raise MaterialLibraryNotFoundError(
                        "material project group not found"
                    )
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            if self._is_duplicate_entry(exc):
                raise ValueError("project group name already exists") from exc
            raise
        group = self.get_project_group(tenant_id, project_group_id)
        if group is None:
            raise MaterialLibraryNotFoundError("material project group not found")
        return group

    def delete_empty_project_group(
        self,
        tenant_id: int,
        project_group_id: int,
    ) -> None:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id
                    from material_project_group
                    where tenant_id = %s and id = %s
                    for update
                    """,
                    (tenant_id, project_group_id),
                )
                if cursor.fetchone() is None:
                    raise MaterialLibraryNotFoundError(
                        "material project group not found"
                    )
                cursor.execute(
                    """
                    select exists(
                        select 1
                        from product_material_folder
                        where tenant_id = %s and project_group_id = %s
                    ) as has_folders
                    """,
                    (tenant_id, project_group_id),
                )
                if cursor.fetchone()["has_folders"]:
                    raise MaterialLibraryConflictError(
                        "project group must be empty before deletion"
                    )
                cursor.execute(
                    """
                    delete from material_project_group
                    where tenant_id = %s and id = %s
                    """,
                    (tenant_id, project_group_id),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def get_project_group(
        self,
        tenant_id: int,
        project_group_id: int,
    ) -> dict | None:
        if project_group_id <= 0:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select project_group.id, project_group.tenant_id,
                       project_group.group_name,
                       project_group.created_by_user_id,
                       project_group.create_time, project_group.update_time,
                       (
                           select count(*)
                           from product_material_folder folder
                           where folder.tenant_id = project_group.tenant_id
                             and folder.project_group_id = project_group.id
                       ) as folder_count,
                       (
                           select count(*)
                           from material_file asset
                           join product_material_folder folder
                             on folder.tenant_id = asset.tenant_id
                            and folder.id = asset.folder_id
                           where asset.tenant_id = project_group.tenant_id
                             and folder.project_group_id = project_group.id
                       ) as asset_count
                from material_project_group project_group
                where project_group.tenant_id = %s and project_group.id = %s
                """,
                (tenant_id, project_group_id),
            )
            row = cursor.fetchone()
        return self._project_group_from_row(row) if row is not None else None

    def resolve_project_group_id(
        self,
        tenant_id: int,
        user_id: int,
        requested_group_id: int,
        folder_id: int,
    ) -> int:
        if folder_id > 0:
            folder = self.get_folder(tenant_id, folder_id)
            if folder is None:
                raise MaterialLibraryNotFoundError("material folder not found")
            folder_group_id = int(folder["project_group_id"])
            if requested_group_id == 0:
                return folder_group_id
            if requested_group_id != folder_group_id:
                raise MaterialLibraryNotFoundError("material folder not found")
        if requested_group_id > 0:
            if self.get_project_group(tenant_id, requested_group_id) is None:
                raise MaterialLibraryNotFoundError(
                    "material project group not found"
                )
            return requested_group_id
        return int(self.ensure_default_project_group(tenant_id, user_id)["id"])

    def create_folder(
        self,
        tenant_id: int,
        user_id: int,
        project_group_id: int,
        parent_id: int,
        folder_name: str,
    ) -> dict:
        clean_name = self._clean_folder_name(folder_name)
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                self._ensure_project_group(cursor, tenant_id, project_group_id)
                self._ensure_folder(
                    cursor,
                    tenant_id,
                    parent_id,
                    project_group_id=project_group_id,
                )
                cursor.execute(
                    """
                    insert into product_material_folder (
                        tenant_id, project_group_id, parent_id, folder_name,
                        created_by_user_id, create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        project_group_id,
                        parent_id,
                        clean_name,
                        user_id,
                        now,
                        now,
                    ),
                )
                folder_id = int(cursor.lastrowid)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        folder = self.get_folder(tenant_id, folder_id)
        if folder is None:
            raise RuntimeError("created material folder was not found")
        return folder

    def list_items(
        self,
        tenant_id: int,
        project_group_id: int,
        folder_id: int,
        keyword: str = "",
        file_type: str = "",
        recursive: bool = False,
    ) -> dict:
        if self.get_project_group(tenant_id, project_group_id) is None:
            raise MaterialLibraryNotFoundError("material project group not found")
        if folder_id > 0:
            folder = self.get_folder(tenant_id, folder_id)
            if folder is None or int(folder["project_group_id"]) != project_group_id:
                raise MaterialLibraryNotFoundError("material folder not found")

        clean_keyword = keyword.strip()
        keyword_like = f"%{clean_keyword}%"
        folder_params: list[object] = [tenant_id, project_group_id, folder_id]
        folder_where = (
            "tenant_id = %s and project_group_id = %s and parent_id = %s"
        )
        if clean_keyword:
            folder_where += " and folder_name like %s"
            folder_params.append(keyword_like)

        asset_params: list[object] = [tenant_id, folder_id]
        asset_where = "tenant_id = %s and folder_id = %s"
        if folder_id == 0:
            asset_where += " and 1 = 0"
        if clean_keyword:
            asset_where += " and file_name like %s"
            asset_params.append(keyword_like)
        if file_type:
            asset_where += " and file_type = %s"
            asset_params.append(file_type)

        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                with recursive listed_folder_tree (root_id, descendant_id) as (
                    select id, id
                    from product_material_folder
                    where {folder_where}
                    union all
                    select tree.root_id, child.id
                    from listed_folder_tree tree
                    join product_material_folder child
                      on child.tenant_id = %s
                     and child.project_group_id = %s
                     and child.parent_id = tree.descendant_id
                )
                select folder.id, folder.tenant_id, folder.project_group_id,
                       folder.parent_id,
                       folder.folder_name, folder.created_by_user_id,
                       folder.create_time, folder.update_time,
                       greatest(
                           folder.update_time,
                           coalesce((
                               select max(asset.update_time)
                               from listed_folder_tree tree
                               join material_file asset
                                 on asset.tenant_id = folder.tenant_id
                                and asset.folder_id = tree.descendant_id
                               where tree.root_id = folder.id
                           ), 0)
                       ) as activity_time,
                       (
                           select count(*)
                           from product_material_folder as child
                            where child.tenant_id = folder.tenant_id
                              and child.project_group_id = folder.project_group_id
                              and child.parent_id = folder.id
                       ) as child_folder_count,
                       (
                           select count(*)
                           from material_file as asset
                           where asset.tenant_id = folder.tenant_id
                             and asset.folder_id = folder.id
                       ) as asset_count
                from product_material_folder as folder
                where folder.id in (select root_id from listed_folder_tree)
                order by folder.folder_name asc, folder.id asc
                """,
                tuple([*folder_params, tenant_id, project_group_id]),
            )
            folders = [self._folder_from_row(row) for row in cursor.fetchall()]
            if recursive and folder_id > 0:
                recursive_asset_where = """
                    tenant_id = %s
                    and folder_id in (select id from descendant_folder)
                """
                recursive_asset_params: list[object] = [
                    tenant_id,
                    project_group_id,
                    folder_id,
                    tenant_id,
                    project_group_id,
                    tenant_id,
                ]
                if clean_keyword:
                    recursive_asset_where += " and file_name like %s"
                    recursive_asset_params.append(keyword_like)
                if file_type:
                    recursive_asset_where += " and file_type = %s"
                    recursive_asset_params.append(file_type)
                cursor.execute(
                    f"""
                    with recursive descendant_folder as (
                        select id
                        from product_material_folder
                        where tenant_id = %s
                          and project_group_id = %s
                          and id = %s
                        union all
                        select child.id
                        from product_material_folder child
                        join descendant_folder parent on child.parent_id = parent.id
                        where child.tenant_id = %s
                          and child.project_group_id = %s
                    )
                    {self._asset_select_sql()}
                    where {recursive_asset_where}
                    order by update_time desc, id desc
                    """,
                    tuple(recursive_asset_params),
                )
            elif recursive:
                recursive_asset_where = """
                    tenant_id = %s
                    and folder_id in (
                        select id
                        from product_material_folder
                        where tenant_id = %s and project_group_id = %s
                    )
                """
                recursive_asset_params = [
                    tenant_id,
                    tenant_id,
                    project_group_id,
                ]
                if clean_keyword:
                    recursive_asset_where += " and file_name like %s"
                    recursive_asset_params.append(keyword_like)
                if file_type:
                    recursive_asset_where += " and file_type = %s"
                    recursive_asset_params.append(file_type)
                cursor.execute(
                    f"""
                    {self._asset_select_sql()}
                    where {recursive_asset_where}
                    order by update_time desc, id desc
                    """,
                    tuple(recursive_asset_params),
                )
            else:
                cursor.execute(
                    f"""
                    {self._asset_select_sql()}
                    where {asset_where}
                    order by update_time desc, id desc
                    """,
                    tuple(asset_params),
                )
            assets = [self._asset_from_row(row) for row in cursor.fetchall()]

        return {
            "current_folder": self.get_folder(tenant_id, folder_id)
            if folder_id > 0
            else None,
            "project_group_id": project_group_id,
            "breadcrumbs": self.get_breadcrumbs(
                tenant_id,
                folder_id,
                project_group_id,
            ),
            "folders": folders,
            "assets": assets,
        }

    def get_breadcrumbs(
        self,
        tenant_id: int,
        folder_id: int,
        project_group_id: int,
    ) -> list[dict]:
        breadcrumbs: list[dict] = []
        current_id = folder_id
        visited: set[int] = set()
        while current_id > 0 and current_id not in visited and len(visited) < 50:
            visited.add(current_id)
            folder = self.get_folder(tenant_id, current_id)
            if (
                folder is None
                or int(folder["project_group_id"]) != project_group_id
            ):
                raise MaterialLibraryNotFoundError("material folder not found")
            breadcrumbs.append(
                {
                    "id": folder["id"],
                    "project_group_id": folder["project_group_id"],
                    "parent_id": folder["parent_id"],
                    "folder_name": folder["folder_name"],
                }
            )
            current_id = int(folder["parent_id"])
        breadcrumbs.reverse()
        return breadcrumbs

    def get_folder(self, tenant_id: int, folder_id: int) -> dict | None:
        if folder_id <= 0:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, project_group_id, parent_id, folder_name,
                       created_by_user_id, create_time, update_time
                from product_material_folder
                where tenant_id = %s and id = %s
                """,
                (tenant_id, folder_id),
            )
            row = cursor.fetchone()
        return self._folder_from_row(row) if row is not None else None

    def rename_folder(
        self,
        tenant_id: int,
        folder_id: int,
        folder_name: str,
    ) -> dict:
        clean_name = self._clean_folder_name(folder_name)
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update product_material_folder
                    set folder_name = %s, update_time = %s
                    where tenant_id = %s and id = %s
                    """,
                    (clean_name, now, tenant_id, folder_id),
                )
                if cursor.rowcount != 1:
                    raise MaterialLibraryNotFoundError("material folder not found")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        folder = self.get_folder(tenant_id, folder_id)
        if folder is None:
            raise MaterialLibraryNotFoundError("material folder not found")
        return folder

    def delete_empty_folder(self, tenant_id: int, folder_id: int) -> None:
        if folder_id <= 0:
            raise MaterialLibraryConflictError("root folder cannot be deleted")
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, project_group_id
                    from product_material_folder
                    where tenant_id = %s and id = %s
                    for update
                    """,
                    (tenant_id, folder_id),
                )
                folder = cursor.fetchone()
                if folder is None:
                    raise MaterialLibraryNotFoundError("material folder not found")
                project_group_id = int(folder["project_group_id"])
                cursor.execute(
                    """
                    select
                        exists(
                            select 1 from product_material_folder
                            where tenant_id = %s
                              and project_group_id = %s
                              and parent_id = %s
                        ) as has_folders,
                        exists(
                            select 1 from material_file
                            where tenant_id = %s and folder_id = %s
                        ) as has_assets
                    """,
                    (
                        tenant_id,
                        project_group_id,
                        folder_id,
                        tenant_id,
                        folder_id,
                    ),
                )
                state = cursor.fetchone()
                if state["has_folders"] or state["has_assets"]:
                    raise MaterialLibraryConflictError(
                        "folder must be empty before deletion"
                    )
                cursor.execute(
                    """
                    delete from product_material_folder
                    where tenant_id = %s and id = %s
                    """,
                    (tenant_id, folder_id),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def create_asset(
        self,
        tenant_id: int,
        user_id: int,
        folder_id: int,
        stored: dict,
    ) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                self._ensure_folder(cursor, tenant_id, folder_id)
                cursor.execute(
                    """
                    insert into material_file (
                        tenant_id, user_id, folder_id, product_id, package_id,
                        file_name, file_type, file_path, mime_type, file_size,
                        create_time, update_time
                    )
                    values (%s, %s, %s, 0, 0, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        user_id,
                        folder_id,
                        stored["file_name"],
                        stored["file_type"],
                        stored["storage_path"],
                        stored["mime_type"],
                        stored["file_size"],
                        now,
                        now,
                    ),
                )
                asset_id = int(cursor.lastrowid)
                self._touch_folder_activity(cursor, tenant_id, folder_id, now)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        asset = self.get_asset(tenant_id, asset_id)
        if asset is None:
            raise RuntimeError("created material asset was not found")
        return asset

    def get_asset(self, tenant_id: int, asset_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._asset_select_sql()
                + " where tenant_id = %s and id = %s",
                (tenant_id, asset_id),
            )
            row = cursor.fetchone()
        return self._asset_from_row(row) if row is not None else None

    def get_assets(self, tenant_id: int, asset_ids: Iterable[int]) -> list[dict]:
        normalized_ids = list(dict.fromkeys(int(asset_id) for asset_id in asset_ids))
        if not normalized_ids:
            return []
        placeholders = ", ".join(["%s"] * len(normalized_ids))
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._asset_select_sql()
                + f" where tenant_id = %s and id in ({placeholders})",
                (tenant_id, *normalized_ids),
            )
            rows = {
                int(row["id"]): self._asset_from_row(row)
                for row in cursor.fetchall()
            }
        return [rows[asset_id] for asset_id in normalized_ids if asset_id in rows]

    def get_storage_bytes(self, tenant_id: int) -> int:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select coalesce(sum(file_size), 0) as used_bytes
                from material_file
                where tenant_id = %s
                """,
                (tenant_id,),
            )
            row = cursor.fetchone()
        return int(row["used_bytes"] or 0)

    def update_asset(
        self,
        tenant_id: int,
        asset_id: int,
        folder_id: int | None = None,
        file_name: str | None = None,
    ) -> dict:
        updates: list[str] = []
        params: list[object] = []
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                if self.get_asset(tenant_id, asset_id) is None:
                    raise MaterialLibraryNotFoundError("material asset not found")
                if folder_id is not None:
                    self._ensure_folder(cursor, tenant_id, folder_id)
                    updates.append("folder_id = %s")
                    params.append(folder_id)
                if file_name is not None:
                    clean_name = self._clean_file_name(file_name)
                    updates.append("file_name = %s")
                    params.append(clean_name)
                if updates:
                    updates.append("update_time = %s")
                    params.append(now)
                    cursor.execute(
                        f"""
                        update material_file
                        set {", ".join(updates)}
                        where tenant_id = %s and id = %s
                        """,
                        (*params, tenant_id, asset_id),
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        asset = self.get_asset(tenant_id, asset_id)
        if asset is None:
            raise MaterialLibraryNotFoundError("material asset not found")
        return asset

    def delete_asset(self, tenant_id: int, asset_id: int) -> dict:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    self._asset_select_sql()
                    + " where tenant_id = %s and id = %s for update",
                    (tenant_id, asset_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise MaterialLibraryNotFoundError("material asset not found")
                asset = self._asset_from_row(row)
                cursor.execute(
                    "delete from material_file where tenant_id = %s and id = %s",
                    (tenant_id, asset_id),
                )
            self.conn.commit()
            return asset
        except Exception:
            self.conn.rollback()
            raise

    def _ensure_project_group(
        self,
        cursor,
        tenant_id: int,
        project_group_id: int,
    ) -> None:
        cursor.execute(
            """
            select id
            from material_project_group
            where tenant_id = %s and id = %s
            for update
            """,
            (tenant_id, project_group_id),
        )
        if cursor.fetchone() is None:
            raise MaterialLibraryNotFoundError("material project group not found")

    def _ensure_folder(
        self,
        cursor,
        tenant_id: int,
        folder_id: int,
        project_group_id: int | None = None,
    ) -> None:
        if folder_id == 0:
            return
        cursor.execute(
            """
            select id, project_group_id
            from product_material_folder
            where tenant_id = %s and id = %s
            """,
            (tenant_id, folder_id),
        )
        folder = cursor.fetchone()
        if folder is None or (
            project_group_id is not None
            and int(folder["project_group_id"]) != project_group_id
        ):
            raise MaterialLibraryNotFoundError("material folder not found")

    def _touch_folder_activity(
        self,
        cursor,
        tenant_id: int,
        folder_id: int,
        update_time: int,
    ) -> None:
        """Bubble an asset upload time to its folder tree and project group."""
        current_folder_id = folder_id
        project_group_id = 0
        visited: set[int] = set()
        while current_folder_id > 0 and current_folder_id not in visited:
            visited.add(current_folder_id)
            cursor.execute(
                """
                select parent_id, project_group_id
                from product_material_folder
                where tenant_id = %s and id = %s
                """,
                (tenant_id, current_folder_id),
            )
            folder = cursor.fetchone()
            if folder is None:
                raise MaterialLibraryNotFoundError("material folder not found")
            folder_project_group_id = int(folder["project_group_id"])
            if project_group_id and folder_project_group_id != project_group_id:
                raise MaterialLibraryNotFoundError("material folder tree is invalid")
            project_group_id = folder_project_group_id
            cursor.execute(
                """
                update product_material_folder
                set update_time = %s
                where tenant_id = %s and id = %s
                """,
                (update_time, tenant_id, current_folder_id),
            )
            current_folder_id = int(folder["parent_id"])

        if project_group_id > 0:
            cursor.execute(
                """
                update material_project_group
                set update_time = %s
                where tenant_id = %s and id = %s
                """,
                (update_time, tenant_id, project_group_id),
            )

    def _asset_select_sql(self) -> str:
        return """
            select id, tenant_id, user_id, folder_id, product_id, package_id,
                   file_name, file_type, file_path, mime_type, file_size,
                   create_time, update_time
            from material_file
        """

    def _folder_from_row(self, row: dict) -> dict:
        result = {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "project_group_id": int(row["project_group_id"]),
            "parent_id": int(row["parent_id"]),
            "folder_name": row["folder_name"],
            "created_by_user_id": int(row["created_by_user_id"]),
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }
        if "child_folder_count" in row:
            result["child_folder_count"] = int(row["child_folder_count"])
        if "asset_count" in row:
            result["asset_count"] = int(row["asset_count"])
        if "activity_time" in row:
            result["activity_time"] = int(row["activity_time"])
        return result

    def _project_group_from_row(self, row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "group_name": row["group_name"],
            "created_by_user_id": int(row["created_by_user_id"]),
            "folder_count": int(row["folder_count"]),
            "asset_count": int(row["asset_count"]),
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }

    def _get_project_group_by_name(
        self,
        tenant_id: int,
        group_name: str,
    ) -> dict | None:
        return next(
            (
                group
                for group in self.list_project_groups(tenant_id)
                if group["group_name"] == group_name
            ),
            None,
        )

    def _asset_from_row(self, row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "user_id": int(row["user_id"]),
            "folder_id": int(row["folder_id"]),
            "product_id": int(row["product_id"]),
            "package_id": int(row["package_id"]),
            "file_name": row["file_name"],
            "file_type": row["file_type"],
            "file_path": row["file_path"],
            "mime_type": row["mime_type"],
            "file_size": int(row["file_size"]),
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }

    def _clean_folder_name(self, value: str) -> str:
        name = value.strip()
        if not name or name in {".", ".."}:
            raise ValueError("folder name is invalid")
        if any(character in name for character in ('/', '\\', '\x00')):
            raise ValueError("folder name contains unsupported characters")
        return name

    def _clean_project_group_name(self, value: str) -> str:
        name = value.strip()
        if not name or name in {".", ".."} or len(name) > 80:
            raise ValueError("project group name is invalid")
        if any(character in name for character in ('/', '\\', '\x00')):
            raise ValueError("project group name contains unsupported characters")
        return name

    @staticmethod
    def _is_duplicate_entry(exc: Exception) -> bool:
        return bool(exc.args) and exc.args[0] == 1062

    def _clean_file_name(self, value: str) -> str:
        name = value.strip()
        if not name or any(character in name for character in ('/', '\\', '\x00')):
            raise ValueError("file name is invalid")
        return name
