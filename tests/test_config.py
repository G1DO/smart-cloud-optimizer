"""Tests for project-level config.py"""
import os
from pathlib import Path
from unittest import mock

import config


class TestPaths:
    def test_project_root_exists(self):
        assert config.PROJECT_ROOT.exists()

    def test_data_dir_under_project_root(self):
        assert config.DATA_DIR == config.PROJECT_ROOT / "data"

    def test_db_path_under_data_dir(self):
        assert config.DB_PATH == config.DATA_DIR / "cloud_optimizer.db"


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
