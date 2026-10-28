"""
VIRA — Synthetic Scenario Generator
Generates synthetic Indian road-user activity demonstration scenarios
(auto-rickshaw cut-in, pedestrian interactions) with explicit provenance labels.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ingestion import generate_synthetic_demonstration_scenes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vira_synthetic_gen")


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    out_file = os.path.join(data_dir, "synthetic_scenarios_generated.json")

    scenes, records = generate_synthetic_demonstration_scenes()
    logger.info("Generated %d synthetic demonstration scenes with %d records.", len(scenes), len(records))

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"scenes": scenes, "records": records}, f, indent=2)

    logger.info("Saved synthetic demonstration records to %s", out_file)


if __name__ == "__main__":
    main()
