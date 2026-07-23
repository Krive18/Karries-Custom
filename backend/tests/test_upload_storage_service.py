import io

import pytest

from app.services.upload_storage_service import UploadStorageError, UploadStorageService


JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-data"
PNG = b"\x89PNG\r\n\x1a\n" + b"png-data"
MP4 = b"\x00\x00\x00\x18ftypisom" + b"mp4-data"
MOV = b"\x00\x00\x00\x18ftypqt  " + b"mov-data"


def test_save_uses_server_name_and_sanitized_display_name(tmp_path):
    service = UploadStorageService(tmp_path)

    stored = service.save(
        stream=io.BytesIO(JPEG),
        original_name="../../product\x00-photo.jpg",
        declared_mime_type="image/jpeg",
        tenant_id=7,
        job_id=9,
    )

    assert stored.file_type == "image"
    assert stored.mime_type == "image/jpeg"
    assert stored.file_name == "product-photo.jpg"
    assert stored.storage_path.endswith(".jpg")
    assert (tmp_path / stored.storage_path).resolve().is_relative_to(tmp_path.resolve())
    assert (tmp_path / stored.storage_path).is_file()


@pytest.mark.parametrize(
    ("payload", "declared_mime_type"),
    [(b"MZ\x00\x00not-media", "image/jpeg"), (PNG, "video/mp4")],
)
def test_save_rejects_spoofed_or_unsupported_upload_and_cleans_part_files(
    tmp_path, payload, declared_mime_type
):
    service = UploadStorageService(tmp_path)

    with pytest.raises(UploadStorageError, match="unsupported|does not match|extension"):
        service.save(
            stream=io.BytesIO(payload),
            original_name="fake.mp4",
            declared_mime_type=declared_mime_type,
            tenant_id=1,
            job_id=2,
        )

    assert list(tmp_path.rglob("*.part")) == []
    assert list(tmp_path.rglob("*.mp4")) == []


def test_save_enforces_size_limit_in_chunks_and_cleans_temp_file(tmp_path):
    service = UploadStorageService(tmp_path, max_bytes=8, chunk_size=4)

    with pytest.raises(UploadStorageError, match="too large"):
        service.save(
            stream=io.BytesIO(MP4),
            original_name="large.mp4",
            declared_mime_type="video/mp4",
            tenant_id=1,
            job_id=2,
        )

    assert list(tmp_path.rglob("*.part")) == []


def test_save_accepts_iso_bmff_mp4_header(tmp_path):
    stored = UploadStorageService(tmp_path).save(
        stream=io.BytesIO(MOV),
        original_name="reference.mov",
        declared_mime_type="video/quicktime",
        tenant_id=11,
        job_id=12,
    )

    assert stored.file_type == "video"
    assert stored.mime_type == "video/quicktime"
    assert stored.file_name == "reference.mov"


def test_save_rejects_quicktime_claim_for_mp4_signature(tmp_path):
    with pytest.raises(UploadStorageError, match="does not match"):
        UploadStorageService(tmp_path).save(
            stream=io.BytesIO(MP4),
            original_name="reference.mov",
            declared_mime_type="video/quicktime",
            tenant_id=11,
            job_id=12,
        )


def test_save_rejects_executable_extension_even_when_bytes_and_mime_are_jpeg(tmp_path):
    with pytest.raises(UploadStorageError, match="extension"):
        UploadStorageService(tmp_path).save(
            stream=io.BytesIO(JPEG),
            original_name="photo.exe",
            declared_mime_type="image/jpeg",
            tenant_id=11,
            job_id=12,
        )


def test_save_keeps_valid_extension_when_display_name_is_truncated(tmp_path):
    stored = UploadStorageService(tmp_path).save(
        stream=io.BytesIO(JPEG),
        original_name=("a" * 300) + ".jpg",
        declared_mime_type="image/jpeg",
        tenant_id=11,
        job_id=12,
    )

    assert len(stored.file_name) == 255
    assert stored.file_name.endswith(".jpg")
