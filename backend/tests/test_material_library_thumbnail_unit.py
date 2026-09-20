import sys
from types import SimpleNamespace

from app.services.material_library_service import MaterialLibraryService


def test_thumbnail_generation_retries_from_ascii_temporary_path(
    monkeypatch,
    tmp_path,
):
    source = tmp_path / "中文视频.mp4"
    source.write_bytes(b"video")
    thumbnail = tmp_path / "cover.jpg"
    opened_paths: list[str] = []

    class FakeCapture:
        def __init__(self, path: str) -> None:
            opened_paths.append(path)
            self.opened = len(opened_paths) > 1

        def isOpened(self) -> bool:
            return self.opened

        def get(self, _property: int) -> int:
            return 1

        def set(self, _property: int, _value: int) -> None:
            return None

        def read(self):
            return True, SimpleNamespace(shape=(100, 160, 3))

        def release(self) -> None:
            return None

    fake_cv2 = SimpleNamespace(
        VideoCapture=FakeCapture,
        CAP_PROP_FRAME_COUNT=1,
        CAP_PROP_FPS=2,
        CAP_PROP_POS_FRAMES=3,
        IMWRITE_JPEG_QUALITY=4,
        INTER_AREA=5,
        resize=lambda frame, _size, interpolation: frame,
        imencode=lambda _extension, _frame, _options: (
            True,
            SimpleNamespace(tobytes=lambda: b"jpeg"),
        ),
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    MaterialLibraryService._generate_video_thumbnail(source, thumbnail)

    assert thumbnail.read_bytes() == b"jpeg"
    assert opened_paths[0] == str(source)
    assert len(opened_paths) == 2
    assert "中文视频" not in opened_paths[1]
