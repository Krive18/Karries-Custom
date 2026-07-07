def test_matrix_plan_from_drafts_schema_accepts_schedule_aliases():
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    payload = MatrixPlanFromDraftsCreate(
        plan_name="Reviewed launch plan",
        draft_ids=[21, 22],
        xhs_account_ids=[11],
        schedule_start=1_700_000_000,
        schedule_end=1_700_086_400,
    )

    assert payload.plan_name == "Reviewed launch plan"
    assert payload.draft_ids == [21, 22]
    assert payload.xhs_account_ids == [11]
    assert payload.schedule_start_time == 1_700_000_000
    assert payload.schedule_end_time == 1_700_086_400
    assert payload.min_interval_minutes == 360


class FakeDraftMatrixCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, _params=()):
        normalized = " ".join(sql.lower().split())
        self.conn.statements.append(normalized)
        if normalized.startswith("insert into matrix_publish_plan"):
            self.lastrowid = 88
        elif normalized.startswith("insert into matrix_publish_item"):
            raise RuntimeError("draft item insert failed")

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeDraftMatrixConnection:
    def __init__(self):
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return FakeDraftMatrixCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_create_plan_from_drafts_rolls_back_when_item_insert_fails():
    import pytest

    from app.repositories.matrix_plan_repository import MatrixPlanRepository
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    conn = FakeDraftMatrixConnection()
    payload = MatrixPlanFromDraftsCreate(
        plan_name="Rollback from drafts",
        draft_ids=[31],
        xhs_account_ids=[11],
        schedule_start_time=1_700_000_000,
        schedule_end_time=1_700_086_400,
    )
    drafts = [
        {
            "id": 31,
            "product_id": 7,
            "content_type": "image_text",
            "title": "Reviewed title",
            "body": "Reviewed body",
            "tags": ["#reviewed"],
            "material": {"product_id": 7},
        }
    ]

    with pytest.raises(RuntimeError, match="draft item insert failed"):
        MatrixPlanRepository(conn).create_plan_from_drafts(
            user_id=5,
            payload=payload,
            drafts=drafts,
            draft_schedule=[(11, 31, 1_700_000_000)],
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1
    assert any("insert into matrix_publish_plan" in statement for statement in conn.statements)
    assert any("insert into matrix_publish_item" in statement for statement in conn.statements)
