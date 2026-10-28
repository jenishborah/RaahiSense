"""
VIRA — Database Initialization Script
Initializes the SQLite evidence store, schemas, indexes, and populates
both genuine TIAND observations and synthetic Indian road demonstration scenarios.
"""

import argparse
import logging
import os
import sys

# Add parent directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import DEFAULT_DB_PATH, reset_database
from ingestion import build_and_export_demonstration_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vira_init")


def main():
    parser = argparse.ArgumentParser(description="Initialize VIRA evidence store database.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to SQLite database.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate database.")
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    csv_out = os.path.join(data_dir, "sample_observations.csv")
    json_out = os.path.join(data_dir, "sample_scenarios.json")

    logger.info("Initializing VIRA evidence database at: %s", args.db_path)
    if args.reset:
        logger.info("Resetting existing database...")
        reset_database(args.db_path)

    stats = build_and_export_demonstration_dataset(
        db_path=args.db_path,
        export_csv_path=csv_out,
        export_json_path=json_out,
    )

    logger.info("Database initialization complete!")
    logger.info("Scenes loaded: %d", stats["scenes_count"])
    logger.info("Genuine TIAND records: %d", stats["tiand_records_count"])
    logger.info("Synthetic demo records: %d", stats["synthetic_records_count"])
    logger.info("Total records in store: %d", stats["total_records"])


if __name__ == "__main__":
    main()
