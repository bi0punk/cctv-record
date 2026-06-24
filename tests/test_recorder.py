import pytest
from unittest.mock import AsyncMock, MagicMock
from app.config import CameraConfig
from app.recorder import CameraRecorder, RecorderManager


def make_mock_process():
    proc = MagicMock()
    proc.returncode = None
    proc.terminate = MagicMock()
    proc.wait = AsyncMock(return_value=0)
    proc.kill = MagicMock()
    return proc


@pytest.fixture(autouse=True)
def mock_ffmpeg(mocker):
    mocker.patch(
        "app.recorder.asyncio.create_subprocess_exec",
        return_value=make_mock_process(),
    )
    mocker.patch("app.recorder.seconds_until_next_hour", return_value=3600)


@pytest.fixture
def camera():
    return CameraConfig(name="TestCam", url="rtsp://example.com/stream", split="none")


@pytest.fixture
def camera_split():
    return CameraConfig(name="DualCam", url="rtsp://example.com/stream2", split="vertical")


@pytest.fixture
def recorder(camera):
    return CameraRecorder(camera)


class TestCameraRecorderInitialState:
    def test_initial_status_is_stopped(self, recorder):
        assert recorder.status == "stopped"

    def test_started_at_is_none(self, recorder):
        assert recorder.started_at is None

    def test_last_file_is_none(self, recorder):
        assert recorder.last_file is None

    def test_error_is_none(self, recorder):
        assert recorder.error is None


@pytest.mark.asyncio
class TestCameraRecorderStartStop:
    async def test_start_changes_status(self, recorder):
        await recorder.start()
        assert recorder.status == "recording"
        assert recorder.started_at is not None
        await recorder.stop()
        assert recorder.status == "stopped"

    async def test_double_start_is_idempotent(self, recorder):
        await recorder.start()
        await recorder.start()
        assert recorder.status == "recording"
        await recorder.stop()

    async def test_stop_when_stopped_does_not_raise(self, recorder):
        await recorder.stop()
        assert recorder.status == "stopped"


@pytest.mark.asyncio
class TestCameraRecorderManager:
    async def test_load_cameras(self):
        mgr = RecorderManager()
        cams = [
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
            CameraConfig(name="Cam2", url="rtsp://cam2", split="vertical"),
        ]
        mgr.load_cameras(cams)
        assert len(mgr.get_all_status()) == 2

    async def test_start_all(self):
        mgr = RecorderManager()
        mgr.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
        ])
        await mgr.start_all()
        assert mgr.started_at is not None
        statuses = mgr.get_all_status()
        assert all(s["status"] == "recording" for s in statuses)
        await mgr.stop_all()
        assert all(s["status"] == "stopped" for s in mgr.get_all_status())

    async def test_stop_all_when_not_started(self):
        mgr = RecorderManager()
        mgr.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
        ])
        await mgr.stop_all()
        assert mgr.system_status()["recording_count"] == 0

    async def test_start_stop_individual(self):
        mgr = RecorderManager()
        mgr.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
            CameraConfig(name="Cam2", url="rtsp://cam2", split="none"),
        ])
        await mgr.start_camera("Cam1")
        status = mgr.get_status("Cam1")
        assert status["status"] == "recording"

        await mgr.stop_camera("Cam1")
        status = mgr.get_status("Cam1")
        assert status["status"] == "stopped"

        await mgr.stop_all()

    async def test_get_status_nonexistent(self):
        mgr = RecorderManager()
        assert mgr.get_status("nonexistent") is None

    async def test_restart_camera(self):
        mgr = RecorderManager()
        mgr.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
        ])
        await mgr.start_camera("Cam1")
        await mgr.restart_camera("Cam1")
        status = mgr.get_status("Cam1")
        assert status["status"] == "recording"
        await mgr.stop_all()


class TestSystemStatus:
    def test_system_status_empty(self):
        mgr = RecorderManager()
        status = mgr.system_status()
        assert status["total_cameras"] == 0
        assert status["recording_count"] == 0
        assert status["error_count"] == 0
        assert status["uptime"] is None


@pytest.mark.asyncio
class TestRecorderWithSplitCameras:
    async def test_split_camera_lifecycle(self, camera_split):
        rec = CameraRecorder(camera_split)
        assert rec.status == "stopped"
        await rec.start()
        assert rec.status == "recording"
        await rec.stop()
        assert rec.status == "stopped"
