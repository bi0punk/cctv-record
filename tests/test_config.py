import json
import pytest
from app.config import load_settings, CameraConfig, Settings


class TestCameraConfig:
    def test_valid_config(self):
        cam = CameraConfig(name="Test", url="rtsp://example.com/stream", split="none")
        assert cam.name == "Test"
        assert cam.split == "none"

    def test_default_split(self):
        cam = CameraConfig(name="Test", url="rtsp://example.com/stream")
        assert cam.split == "none"

    def test_invalid_split_raises(self):
        with pytest.raises(Exception):
            CameraConfig(name="Test", url="rtsp://example.com/stream", split="invalid")


class TestLoadSettings:
    def test_empty_cameras(self, monkeypatch):
        monkeypatch.setenv("CAMERAS_JSON", "[]")
        s = load_settings()
        assert s.cameras == []

    def test_single_camera(self, monkeypatch):
        cameras = [{"name": "Cam1", "url": "rtsp://cam", "split": "none"}]
        monkeypatch.setenv("CAMERAS_JSON", json.dumps(cameras))
        s = load_settings()
        assert len(s.cameras) == 1
        assert s.cameras[0].name == "Cam1"

    def test_invalid_json_raises(self, monkeypatch):
        monkeypatch.setenv("CAMERAS_JSON", "not-json")
        with pytest.raises(ValueError, match="not valid JSON"):
            load_settings()

    def test_non_array_raises(self, monkeypatch):
        monkeypatch.setenv("CAMERAS_JSON", '{"key": "value"}')
        with pytest.raises(ValueError, match="must be a JSON array"):
            load_settings()

    def test_custom_recordings_dir(self, monkeypatch):
        monkeypatch.setenv("CAMERAS_JSON", "[]")
        monkeypatch.setenv("RECORDINGS_DIR", "/custom/path")
        s = load_settings()
        assert str(s.recordings_dir) == "/custom/path"

    def test_default_values(self, monkeypatch):
        monkeypatch.setenv("CAMERAS_JSON", "[]")
        s = load_settings()
        assert s.host == "0.0.0.0"
        assert s.port == 8000
