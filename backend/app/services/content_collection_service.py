from app.repositories.content_collection_repository import ContentCollectionRepository
from app.repositories.viral_analysis_repository import ViralAnalysisRepository
from app.schemas.content_collection import ContentCollectionCreateRequest


class ContentCollectionSourceNotFoundError(LookupError):
    pass


class ContentCollectionSourceStateError(ValueError):
    def __init__(self, status: str):
        self.status = status
        super().__init__(f"content collection source is {status}")


class ContentCollectionService:
    def __init__(self, conn):
        self.conn = conn
        self.repository = ContentCollectionRepository(conn)

    def create_from_source(
        self,
        user: dict,
        payload: ContentCollectionCreateRequest,
    ) -> dict:
        job = ViralAnalysisRepository(self.conn).get_for_user(
            user["tenant_id"],
            user["id"],
            payload.source_id,
        )
        if job is None:
            raise ContentCollectionSourceNotFoundError
        if job["status"] != "completed" or job["result"] is None:
            raise ContentCollectionSourceStateError(str(job["status"]))
        item, created = self.repository.create_from_viral_analysis(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            job=job,
        )
        return {"item": item, "created": created}
