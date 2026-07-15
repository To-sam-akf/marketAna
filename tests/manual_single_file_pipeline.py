"""Compatibility wrapper for the standalone single-file pipeline.

The old database-backed pn04-pn07 runner is intentionally gone.  This entry
point remains for existing developer commands and delegates to the same
reader, cleaner, matcher, rule, and LLM code used by the current pipeline.
"""

from __future__ import annotations

import argparse

from data_proccessing.test_single_file import run_single_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the standalone MarketANA pipeline for one file")
    parser.add_argument("file", help="PDF/HTML/TXT/图片路径")
    parser.add_argument("--output-dir", help="输出目录")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM")
    parser.add_argument("--lexicon", default="data_proccessing/instrument_mapping/artifacts/instrument_lexicon.json")
    args = parser.parse_args()
    run_single_file(
        args.file,
        lexicon_path=args.lexicon,
        output_dir=args.output_dir,
        skip_llm=args.skip_llm,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
