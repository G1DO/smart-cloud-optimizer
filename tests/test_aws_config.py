"""Tests for aws_collector/config.py — AWSConfig with mocked boto3."""
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest


class TestAWSConfigInit:
    """Test AWSConfig.__init__ with fully mocked boto3."""

    @patch("aws_collector.config.boto3")
    def test_creates_clients(self, mock_boto3):
        mock_session = MagicMock()
        mock_session.client.return_value = MagicMock()

        # Mock STS get_caller_identity
        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

        # Mock EC2 describe_regions
        ec2_client = MagicMock()
        ec2_client.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "eu-west-1"},
            ]
        }

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        from aws_collector.config import AWSConfig
        cfg = AWSConfig(session=mock_session)

        assert cfg.account_id == "123456789012"
        assert "us-east-1" in cfg.regions
        assert "eu-west-1" in cfg.regions

    @patch("aws_collector.config.boto3")
    def test_regions_fallback_on_error(self, mock_boto3):
        mock_session = MagicMock()

        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "111111111111"}

        ec2_client = MagicMock()
        ec2_client.describe_regions.side_effect = Exception("AccessDenied")

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        from aws_collector.config import AWSConfig
        cfg = AWSConfig(session=mock_session)

        assert cfg.regions == ["us-east-1"]


class TestAWSConfigFromRole:
    """Test AWSConfig.from_role with mocked STS."""

    @patch("aws_collector.config.boto3")
    def test_assumes_role(self, mock_boto3):
        # Mock the module-level boto3.client("sts") call in from_role
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA_TEMP",
                "SecretAccessKey": "secret_temp",
                "SessionToken": "token_temp",
            }
        }
        mock_boto3.client.return_value = mock_sts

        # Mock the Session created with temp creds
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "999999999999"}
        ec2_client = MagicMock()
        ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-west-2"}]}

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        from aws_collector.config import AWSConfig
        cfg = AWSConfig.from_role("arn:aws:iam::999999999999:role/test", external_id="ext123")

        mock_sts.assume_role.assert_called_once()
        call_kwargs = mock_sts.assume_role.call_args
        assert call_kwargs[1]["RoleArn"] == "arn:aws:iam::999999999999:role/test"
        assert call_kwargs[1]["ExternalId"] == "ext123"
        assert cfg.account_id == "999999999999"

    @patch("aws_collector.config.boto3")
    def test_from_role_without_external_id(self, mock_boto3):
        mock_sts = MagicMock()
        mock_sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA_TEMP",
                "SecretAccessKey": "secret_temp",
                "SessionToken": "token_temp",
            }
        }
        mock_boto3.client.return_value = mock_sts

        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "888888888888"}
        ec2_client = MagicMock()
        ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        from aws_collector.config import AWSConfig
        cfg = AWSConfig.from_role("arn:aws:iam::888888888888:role/test")

        call_kwargs = mock_sts.assume_role.call_args[1]
        assert "ExternalId" not in call_kwargs


class TestRegionalClients:
    """Test get_*_client methods."""

    @patch("aws_collector.config.boto3")
    def test_get_rds_client(self, mock_boto3):
        mock_session = MagicMock()
        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "123"}
        ec2_client = MagicMock()
        ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        from aws_collector.config import AWSConfig
        cfg = AWSConfig(session=mock_session)

        cfg.get_rds_client("eu-west-1")
        mock_session.client.assert_any_call("rds", region_name="eu-west-1")

    @patch("aws_collector.config.boto3")
    def test_get_lambda_client(self, mock_boto3):
        mock_session = MagicMock()
        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "123"}
        ec2_client = MagicMock()
        ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        from aws_collector.config import AWSConfig
        cfg = AWSConfig(session=mock_session)

        cfg.get_lambda_client("ap-southeast-1")
        mock_session.client.assert_any_call("lambda", region_name="ap-southeast-1")


class TestSingletonAccessors:
    """Test get_config / init_config module-level functions."""

    @patch("aws_collector.config.boto3")
    def test_init_config_sets_global(self, mock_boto3):
        import aws_collector.config as cfg_mod

        mock_session = MagicMock()
        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": "555"}
        ec2_client = MagicMock()
        ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        def side_effect(service, **kwargs):
            if service == "sts":
                return sts_client
            if service == "ec2":
                return ec2_client
            return MagicMock()

        mock_session.client.side_effect = side_effect

        result = cfg_mod.init_config(session=mock_session)
        assert result.account_id == "555"
        assert cfg_mod._config is result
