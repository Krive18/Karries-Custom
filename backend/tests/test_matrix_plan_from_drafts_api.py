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
