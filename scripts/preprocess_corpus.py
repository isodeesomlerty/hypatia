from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from research_graph.pipeline import preprocess_corpus  # noqa: E402


def print_progress(event: dict) -> None:
    message = event.get("message", "")
    current = event.get("current")
    total = event.get("total")
    if current is not None and total is not None:
        print(f"[{event.get('stage', 'progress')}] {message} ({current}/{total})")
    else:
        print(f"[{event.get('stage', 'progress')}] {message}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Preprocess a folder of PDFs into Hypatia cache files.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT_DIR / "data" / "raw",
        help="Directory containing source PDFs.",
    )
    args = parser.parse_args()

    summary = preprocess_corpus(args.raw_dir, progress_callback=print_progress)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
