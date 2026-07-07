def generate_schedule_times(
    account_ids: list[int],
    schedule_start_time: int,
    schedule_end_time: int,
    items_per_account: int,
    min_interval_minutes: int,
) -> list[tuple[int, int]]:
    if schedule_start_time > schedule_end_time:
        raise ValueError("schedule start must be before end")

    interval_seconds = max(min_interval_minutes * 60, 60)
    schedule: list[tuple[int, int]] = []
    for account_index, account_id in enumerate(account_ids):
        account_start_time = schedule_start_time + account_index * 300
        for item_index in range(items_per_account):
            scheduled_time = account_start_time + item_index * interval_seconds
            schedule.append((account_id, min(scheduled_time, schedule_end_time)))

    return schedule
