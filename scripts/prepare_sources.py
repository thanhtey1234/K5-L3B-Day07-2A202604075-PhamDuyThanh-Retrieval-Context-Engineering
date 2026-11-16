"""Download public source artifacts; no API keys or inference calls are used."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from day7_rag.sources import prepare_day6, prepare_wdr

parser = argparse.ArgumentParser()
parser.add_argument("--corpus", choices=["day6", "wdr2023", "all"], default="all")
parser.add_argument("--output", type=Path, default=Path("work/corpora"))
args = parser.parse_args()
for name, function in (("day6", prepare_day6), ("wdr2023", prepare_wdr)):
    if args.corpus in (name, "all"):
        print(name, function(args.output / name))
