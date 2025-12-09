"""
Main entry point for AWS Collector
Run this to start collecting AWS data for the last 5 months
"""
import sys
from .collector_runner import CollectorRunner


def main():
    """Main function to run the collector"""
    try:
        print("Starting AWS Data Collector...")
        print("This will collect 5 months of AWS data (cost, metrics, pricing, inventory)")
        print("Press Ctrl+C to cancel\n")
        
        # Initialize and run collector
        runner = CollectorRunner()
        runner.run(months=5)
        
        print("\n✅ Collection completed successfully!")
        return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Collection cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error during collection: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
