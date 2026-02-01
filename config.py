"""
config.py — Project-wide configuration for Smart Cloud Optimizer.

Single source of truth for paths, constants, and environment settings.
AWS-specific boto3 client configuration lives in aws_collector/config.py.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import os
from pathlib import Path

# === Paths ===
PROJECT_ROOT: Path = Path(__file__).parent
DATA_DIR: Path = PROJECT_ROOT / "data"
REAL_DATA_DIR: Path = DATA_DIR / "real"
SYNTHETIC_DATA_DIR: Path = DATA_DIR / "synthetic"
DB_PATH: Path = DATA_DIR / "cloud_optimizer.db"

# === Mode ===
DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"

# === AWS ===
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCOUNT_ID: str = os.getenv("AWS_ACCOUNT_ID", "SYNTHETIC-001")

# === Collection Defaults ===
DEFAULT_COLLECTION_MONTHS: int = 12
DEFAULT_SYNTHETIC_DAYS: int = 365

# === AWS API Settings ===
API_TIMEOUT: int = 30
MAX_RETRIES: int = 3
CHUNK_SIZE: int = 100

# === API Keys ===
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# === ML Defaults ===
FORECAST_HORIZON_DAYS: int = 30
MIN_TRAINING_DAYS: int = 30
SEASONALITY_PERIOD: int = 7

# === Optimization ===
DEFAULT_BUDGET_CAP: float = 5000.0
SPOT_RELIABILITY: bool = False

# === Supported Services ===
SUPPORTED_SERVICES: list[str] = [
    "ec2",
    "rds",
    "lambda",
    "s3",
    "ebs",
    "cloudfront",
    "nat_gateway",
    "alb",
    "nlb",
]


def get_data_dir() -> Path:
    """Return synthetic data dir in demo mode, real data dir otherwise."""
    return SYNTHETIC_DATA_DIR if DEMO_MODE else REAL_DATA_DIR


def setup_logging(level: str = "INFO") -> None:
    """Configure project-wide logging.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
