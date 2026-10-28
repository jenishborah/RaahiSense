"""
VIRA — Dataset Import Utility
CLI utility to import custom CSV observations or re-import TIAND genuine records.
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import DEFAULT_DB_PATH
from ingestion import extract_genuine_tiand_observations, ingest_user_csv, upsert_scene, insert_evidence_records_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vira_import")


def main():
    parser = argparse.ArgumentParser(description="Import datasets into VIRA evidence store.")
    parser.add_argument("--csv", help="Path to custom CSV file with road-user observations.")
    parser.add_argument("--tiand", action="store_true", help="Import genuine TIAND multimodal records.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Target SQLite database.")
    args = parser.parse_args()

    if args.csv:
        logger.info("Importing CSV file: %s", args.csv)
        count, msg = ingest_user_csv(args.csv, db_path=args.db_path)
        logger.info(msg)

    if args.tiand:
        logger.info("Extracting genuine TIAND multimodal observations...")
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        scene_meta, records = extract_genuine_tiand_observations(repo_root=repo_root)
        upsert_scene(scene_meta, db_path=args.db_path)
        inserted = insert_evidence_records_batch(records, db_path=args.db_path)
        logger.info("Inserted %d genuine TIAND observations.", inserted)


if __name__ == "__main__":
    main()
