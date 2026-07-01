from app.db.schema import SCHEMA_STATEMENTS


def migrate(conn) -> None:
    with conn.cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
    conn.commit()
