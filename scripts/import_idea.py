#!/usr/bin/env python3
"""Convert X产品idea挖掘 output into data/idea/DATE.json.

Usage: python3 scripts/import_idea.py 2026-10-23
           # parses /workspace/idea-mining-2026-10-23/top5.json + top5.md (same parser as the old idea-radar build.py)
       python3 scripts/import_idea.py --dir /path/to/idea-mining-2026-10-23
       python3 scripts/import_idea.py --radar-json /workspace/idea-radar/data/2026-10-23.json   # already-normalized file
       python3 scripts/import_idea.py --all-radar            # every /workspace/idea-radar/data/*.json (migration)
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import idea_from_radar, write_day
import idea_parse

def save(d, src):
    if not d.get("ideas"):
        sys.exit(f"[import_idea] {src}: no ideas parsed")
    day, items = idea_from_radar(d)
    out = write_day("idea", d["date"], day, items)
    print(f"[import_idea] {src} -> {out} ({len(items)} ideas)")

ap = argparse.ArgumentParser()
ap.add_argument("date", nargs="?")
ap.add_argument("--dir")
ap.add_argument("--radar-json")
ap.add_argument("--all-radar", action="store_true")
a = ap.parse_args()
if a.all_radar:
    for f in sorted(glob.glob("/workspace/idea-radar/data/????-??-??.json")):
        save(json.load(open(f, encoding="utf-8")), f)
elif a.radar_json:
    save(json.load(open(a.radar_json, encoding="utf-8")), a.radar_json)
else:
    dp = a.dir or (f"/workspace/idea-mining-{a.date}" if a.date else None)
    if not dp: ap.error("give DATE, --dir, --radar-json or --all-radar")
    if not os.path.isdir(dp): sys.exit(f"[import_idea] no such dir {dp}")
    save(idea_parse.load_day(dp.rstrip("/")), dp)
