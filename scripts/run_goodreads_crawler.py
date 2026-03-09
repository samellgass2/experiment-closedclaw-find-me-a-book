#!/usr/bin/env python3
"""CLI wrapper for Goodreads crawler."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawler.goodreads_crawler import run_cli


if __name__ == "__main__":
    raise SystemExit(run_cli())
