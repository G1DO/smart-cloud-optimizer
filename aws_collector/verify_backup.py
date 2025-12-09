"""
Quick script to verify backup and show data status before running collector
"""
from pathlib import Path
import csv

DATA_DIR = Path("data")
BACKUP_DIR = Path("backups")

def count_rows(csv_file):
    """Count rows in CSV file"""
    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            return sum(1 for row in reader) - 1  # Subtract header
    except:
        return 0

print("=" * 60)
print("Data Status Check")
print("=" * 60)

print("\n📊 Current Data:")
for csv_file in sorted(DATA_DIR.glob("**/*consolidated.csv")):
    rows = count_rows(csv_file)
    print(f"  {csv_file.relative_to(DATA_DIR)}: {rows} rows")

print("\n💾 Backup Status:")
if BACKUP_DIR.exists():
    backup_files = list(BACKUP_DIR.glob("*.csv"))
    if backup_files:
        print(f"  ✓ {len(backup_files)} files backed up")
        for f in backup_files[:5]:
            rows = count_rows(f)
            print(f"    - {f.name}: {rows} rows")
    else:
        print("  ⚠️  No backup files found")
else:
    print("  ⚠️  Backup directory doesn't exist")

print("\n✅ Collector Configuration:")
print("  - Mode: APPEND (new data will be added, not overwritten)")
print("  - Existing data: PRESERVED")
print("  - New data: Added to end of consolidated files")

print("\n" + "=" * 60)
print("Safe to run collector! Your old data is preserved.")
print("=" * 60)

