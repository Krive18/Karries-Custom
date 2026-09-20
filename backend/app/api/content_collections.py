from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.repositories.content_collection_repository import ContentCollectionRepository
from app.schemas.content_collection import (
    ContentCollectionCreateRequest,
    ContentCollectionUpdateRequest,
)
from app.services.content_collection_service import (
    ContentCollectionService,
    ContentCollectionSourceNotFoundError,
    ContentCollectionSourceStateError,
)


router = APIRouter(prefix="/api/content-collections", tags=["content-collections"])


@router.post("")
def create_content_collection(
    payload: ContentCollectionCreateRequest,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(ContentCollectionService(conn).create_from_source(user, payload))
    except ContentCollectionSourceNotFoundError:
        return _not_found("viral analysis job not found")
    except ContentCollectionSourceStateError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("STATE_CONFLICT", f"viral analysis job is {exc.status}"),
        )


@router.get("")
def list_content_collections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, min_length=1, max_length=200),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        ContentCollectionRepository(conn).list_for_user(
            user["tenant_id"],
            user["id"],
            page=page,
            page_size=page_size,
            keyword=keyword,
        )
    )


@router.get("/{collection_id}")
def get_content_collection(
    collection_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    item = ContentCollectionRepository(conn).get_for_user(
        user["tenant_id"], user["id"], collection_id
    )
    return ok(item) if item is not None else _not_found("content collection not found")


@router.patch("/{collection_id}")
def update_content_collection(
    collection_id: int,
    payload: ContentCollectionUpdateRequest,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    item = ContentCollectionRepository(conn).update_for_user(
        user["tenant_id"], user["id"], collection_id, payload
    )
    return ok(item) if item is not None else _not_found("content collection not found")


@router.delete("/{collection_id}")
def delete_content_collection(
    collection_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    deleted = ContentCollectionRepository(conn).delete_for_user(
        int(user["tenant_id"]),
        int(user["id"]),
        collection_id,
    )
    if not deleted:
        return _not_found("content collection not found")
    return ok({"id": collection_id, "deleted": True})


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))
