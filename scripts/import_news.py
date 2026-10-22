#!/usr/bin/env python3
"""Convert newsBot output into data/news/DATE.json.

Usage: python3 scripts/import_news.py 2026-10-23            # reads /workspace/briefing/data/2026-10-23.json
       python3 scripts/import_news.py --src some/file.json   # any file in the briefing format
       python3 scripts/import_news.py --all                  # every /workspace/briefing/data/*.json
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import news_from_briefing, write_day

SRC_DIR = "/workspace/briefing/data"

def one(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)  # raises on bad JSON -> non-zero exit
    if not d.get("items"):
        sys.exit(f"[import_news] {path}: no items")
    day, items = news_from_briefing(d)
    out = write_day("news", d["date"], day, items)
    print(f"[import_news] {path} -> {out} ({len(items)} items)")

ap = argparse.ArgumentParser()
ap.add_argument("date", nargs="?")
ap.add_argument("--src")
ap.add_argument("--all", action="store_true")
a = ap.parse_args()
if a.all:
    for f in sorted(glob.glob(f"{SRC_DIR}/????-??-??.json")): one(f)
elif a.src: one(a.src)
elif a.date: one(f"{SRC_DIR}/{a.date}.json")
else: ap.error("give DATE, --src FILE or --all")
