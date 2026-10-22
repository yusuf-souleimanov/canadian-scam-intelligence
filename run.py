"""Canadian Payment Scam Intelligence Engine.

    python run.py collect          # download CAFC bulletins -> data/docs/
    python run.py extract          # Claude turns each bulletin into structured intel
    python run.py trends           # print the trend tables from the CAFC dataset
    python run.py brief            # build output/scam-intel-brief-<month>.pdf
    python run.py ask "question"   # cited answer from the knowledge base
    python run.py all              # collect + extract + brief
"""
import sys

import pandas as pd


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd in ("collect", "all"):
        from intel.collect import collect
        print("Collecting CAFC bulletins...")
        collect()
    if cmd in ("extract", "all"):
        from intel.extract import extract_all
        print("Extracting structured intelligence...")
        extract_all()
    if cmd == "trends":
        from intel import trends
        pd.set_option("display.width", 200)
        df = trends.load()
        print(trends.headline_numbers(df))
        tr = trends.typology_trends(df)
        print(f"\n{tr.attrs['window']} vs {tr.attrs['prev_window']}")
        print(tr[["reports", "reports_yoy", "loss", "loss_yoy", "loss_ex_top3_yoy", "median_loss", "robust_growth"]].round(2))
        print("\n", trends.channel_shift(df).round(3))
    if cmd in ("brief", "all"):
        from intel.brief import generate
        print("Building brief...")
        print(f"Saved {generate()}")
    if cmd == "ask":
        from intel.ask import KnowledgeBase
        print(KnowledgeBase().ask(" ".join(argv[2:])))
    if cmd == "help":
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
