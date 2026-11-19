"""Build data/processed/*.csv from data/raw (run after download_data.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import build_processed  # noqa: E402

if __name__ == "__main__":
    report = build_processed()
    print("\nProcessed tables:", report or "none (download the raw data first)")
