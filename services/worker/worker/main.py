from __future__ import annotations

import argparse
import json


SUPPORTED_JOB_TYPES = [
    "batch_ingestion",
    "paper_ingestion",
    "pairwise_comparison",
    "graph_rebuild",
    "replication_run",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Hypatia worker service placeholder.")
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the current worker responsibilities as JSON.",
    )
    args = parser.parse_args()

    if args.describe:
        print(
            json.dumps(
                {
                    "service": "hypatia-worker",
                    "job_types": SUPPORTED_JOB_TYPES,
                    "notes": "This service will execute background ingestion, pairwise comparison, graph rebuild, and replication tasks.",
                },
                indent=2,
            )
        )
        return

    print("Hypatia worker scaffold is ready. Run with --describe for current responsibilities.")


if __name__ == "__main__":
    main()
