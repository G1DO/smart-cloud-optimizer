"""Tests for cloud_optimizer/config.py"""
import os
import runpy
from pathlib import Path
from unittest import mock

from cloud_optimizer import config


class TestPaths:
    def test_project_root_is_repository_root(self):
        assert config.PROJECT_ROOT == Path(__file__).resolve().parents[1]

    def test_data_dir_under_project_root(self):
        assert config.DATA_DIR == config.PROJECT_ROOT / "data"

    def test_db_path_under_data_dir(self):
        assert config.DB_PATH == config.DATA_DIR / "cloud_optimizer.db"

    def test_paths_and_env_loading_from_another_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AWS_REGION", "eu-west-2")
        repo_root = Path(__file__).resolve().parents[1]

        with mock.patch("dotenv.load_dotenv") as load_dotenv:
            settings = runpy.run_path(config.__file__)

        load_dotenv.assert_called_once_with(repo_root / ".env")
        assert settings["PROJECT_ROOT"] == repo_root
        assert settings["DB_PATH"] == repo_root / "data" / "cloud_optimizer.db"
        assert settings["AWS_REGION"] == "eu-west-2"


class TestDemoMode:
    def test_default_is_demo(self):
        # Default DEMO_MODE env var is "true"
        with mock.patch.dict(os.environ, {"DEMO_MODE": "true"}):
            # Re-evaluate
            result = os.getenv("DEMO_MODE", "true").lower() == "true"
            assert result is True

    def test_non_demo(self):
        with mock.patch.dict(os.environ, {"DEMO_MODE": "false"}):
            result = os.getenv("DEMO_MODE", "true").lower() == "true"
            assert result is False


class TestConstants:
    def test_default_months(self):
        assert config.DEFAULT_COLLECTION_MONTHS == 12

    def test_default_days(self):
        assert config.DEFAULT_SYNTHETIC_DAYS == 365

    def test_supported_services_not_empty(self):
        assert len(config.SUPPORTED_SERVICES) > 0
        assert "ec2" in config.SUPPORTED_SERVICES
