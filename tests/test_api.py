import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import CameraConfig
from app.recorder import manager


def make_mock_process():
    proc = MagicMock()
    proc.returncode = None
    proc.terminate = MagicMock()
    proc.wait = AsyncMock(return_value=0)
    proc.kill = MagicMock()
    return proc


@pytest.fixture(autouse=True)
def mock_ffmpeg(mocker):
    async def _mock_subprocess(*args, **kwargs):
        return make_mock_process()
    mocker.patch(
        "app.recorder.asyncio.create_subprocess_exec",
        _mock_subprocess,
    )
    mocker.patch("app.recorder.seconds_until_next_hour", return_value=3600)


@pytest.fixture(autouse=True)
def reset_manager():
    manager.load_cameras([])
    yield
    manager.load_cameras([])


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestAPIEndpoints:
    async def test_dashboard_returns_html(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    async def test_recordings_page_returns_html(self, client):
        resp = await client.get("/recordings")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    async def test_api_cameras_empty(self, client):
        resp = await client.get("/api/cameras")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_api_status_empty(self, client):
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cameras"] == 0

    async def test_api_cameras_with_data(self, client):
        manager.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
        ])
        resp = await client.get("/api/cameras")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Cam1"
        assert data[0]["status"] == "stopped"

    async def test_start_stop_all(self, client):
        manager.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
            CameraConfig(name="Cam2", url="rtsp://cam2", split="none"),
        ])

        resp = await client.post("/api/start")
        assert resp.status_code == 200

        status = (await client.get("/api/status")).json()
        assert status["recording_count"] == 2

        resp = await client.post("/api/stop")
        assert resp.status_code == 200

        status = (await client.get("/api/status")).json()
        assert status["recording_count"] == 0

    async def test_individual_camera_control(self, client):
        manager.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
        ])

        resp = await client.post("/api/camera/Cam1/start")
        assert resp.status_code == 200
        assert (await client.get("/api/status")).json()["recording_count"] == 1

        resp = await client.post("/api/camera/Cam1/stop")
        assert resp.status_code == 200
        assert (await client.get("/api/status")).json()["recording_count"] == 0

    async def test_restart_camera(self, client):
        manager.load_cameras([
            CameraConfig(name="Cam1", url="rtsp://cam1", split="none"),
        ])
        resp = await client.post("/api/camera/Cam1/restart")
        assert resp.status_code == 200

    async def test_nonexistent_camera_start(self, client):
        resp = await client.post("/api/camera/Nope/start")
        assert resp.status_code == 404

    async def test_nonexistent_camera_stop(self, client):
        resp = await client.post("/api/camera/Nope/stop")
        assert resp.status_code == 404

    async def test_recordings_tree_empty(self, client, tmp_path):
        from app.config import settings
        settings.recordings_dir = tmp_path
        resp = await client.get("/api/recordings/tree")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_stream_recording_path_traversal_blocked(self, client):
        resp = await client.get("/api/recordings/stream", params={"path": "../../etc/passwd"})
        assert resp.status_code == 403

    async def test_stream_recording_not_found(self, client, tmp_path):
        from app.config import settings
        settings.recordings_dir = tmp_path
        resp = await client.get("/api/recordings/stream", params={"path": "nonexistent.mp4"})
        assert resp.status_code == 404
