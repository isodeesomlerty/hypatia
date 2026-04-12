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


def _pair_label(event: dict) -> str | None:
    paper_a_title = event.get("paper_a_title")
    paper_b_title = event.get("paper_b_title")
    if paper_a_title and paper_b_title:
        return f'"{paper_a_title}" vs "{paper_b_title}"'
    pair_key = event.get("pair_key")
    if pair_key:
        return str(pair_key)
    return None


def print_progress(event: dict) -> None:
    stage = event.get("stage", "progress")
    message = event.get("message", "")
    current = event.get("current")
    total = event.get("total")
    prefix = f"[{stage}]"

    if stage == "pairwise_start":
        fresh_pairs = event.get("fresh_pairs_total", total or 0)
        cached_pairs = event.get("cached_pairs_skipped", 0)
        candidate_pairs = event.get("candidate_pairs_total", fresh_pairs + cached_pairs)
        workers = event.get("pairwise_workers")
        worker_text = f", workers={workers}" if workers is not None else ""
        print(
            f"{prefix} {fresh_pairs} fresh pairwise comparisons queued; "
            f"{cached_pairs} already cached and skipped "
            f"({candidate_pairs} candidate pairs total{worker_text})."
        )
        return

    if stage in {"pairwise_progress", "pairwise_retry_progress"}:
        pair_label = _pair_label(event) or "unknown pair"
        phase = event.get("pair_phase", "fresh")
        outcome = event.get("pair_outcome", "completed")
        relationship_count = event.get("relationship_count")
        count_text = (
            f"{relationship_count} relationship(s)"
            if relationship_count is not None
            else "unknown relationship count"
        )
        if current is not None and total is not None:
            progress_text = f"{current}/{total}"
        else:
            progress_text = "?"
        if phase == "retry":
            attempt = event.get("retry_attempt")
            max_attempts = event.get("retry_max_attempts")
            attempt_text = (
                f" on retry pass {attempt}/{max_attempts}"
                if attempt is not None and max_attempts is not None
                else ""
            )
        else:
            attempt_text = ""
        if outcome == "failed":
            error_text = event.get("error", "").strip()
            debug_path = event.get("debug_path", "").strip()
            suffix = f" error={error_text}" if error_text else ""
            if debug_path:
                suffix += f" debug={debug_path}"
            print(
                f"{prefix} {phase} {progress_text}: failed {pair_label}{attempt_text}.{suffix}"
            )
        else:
            print(
                f"{prefix} {phase} {progress_text}: completed {pair_label}{attempt_text} "
                f"-> {count_text}."
            )
        return

    if stage == "pairwise_retry_start":
        retry_pairs = event.get("retry_pairs_total", total or 0)
        attempt = event.get("retry_attempt")
        max_attempts = event.get("retry_max_attempts")
        attempt_text = (
            f" (pass {attempt}/{max_attempts})"
            if attempt is not None and max_attempts is not None
            else ""
        )
        print(
            f"{prefix} Retrying {retry_pairs} failed pairwise comparison(s) serially{attempt_text}."
        )
        return

    if stage == "pairwise_complete":
        candidate_pairs = event.get("candidate_pairs_total", total or 0)
        cached_pairs = event.get("cached_pairs_skipped", 0)
        fresh_pairs = event.get("fresh_pairs_total", 0)
        successful_pairs = event.get("successful_pairs_count", 0)
        failed_pairs = event.get("failed_pairs_count", 0)
        if event.get("skipped_all_cached"):
            print(
                f"{prefix} All {candidate_pairs} candidate paper comparisons were already cached; "
                "skipping fresh pairwise analysis."
            )
            return
        print(
            f"{prefix} Pairwise work finished: {successful_pairs}/{fresh_pairs} fresh comparisons "
            f"succeeded, {failed_pairs} failed, and {cached_pairs} were skipped from cache "
            f"({candidate_pairs} candidate pairs total)."
        )
        return

    if current is not None and total is not None:
        print(f"{prefix} {message} ({current}/{total})")
    else:
        print(f"{prefix} {message}")


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
