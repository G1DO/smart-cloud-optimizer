"""
main.py — Entry point for the AWS data collection pipeline.

Run this module to collect 12 months of AWS cost, metrics, pricing,
and inventory data.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sys
import traceback

import config

from .runner import CollectorRunner

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the full collection pipeline.

    Returns:
        Exit code: 0 on success, 1 on failure or cancellation.
    """
    config.setup_logging()

    try:
        logger.info("Starting AWS Data Collector...")
        logger.info("This will collect 12 months of AWS data (cost, metrics, pricing, inventory)")
        logger.info("Press Ctrl+C to cancel\n")

        # Initialize and run collector
        runner = CollectorRunner()
        runner.run(months=12)

        logger.info("\n✅ Collection completed successfully!")
        return 0

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Collection cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Error during collection: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
