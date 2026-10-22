#!/usr/bin/env python3
"""One-off migration (2026-10-22): copy the OSS records converted in the confirmed prototype
(/workspace/daily-hub-prototype/data/items.json) into data/oss/DATE.json. 2 real picks + October
research candidates (status candidate). Nothing is added or rewritten."""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_day
items = json.load(open("/workspace/daily-hub-prototype/data/items.json", encoding="utf-8"))
by = defaultdict(list)
for it in items:
    if it["type"] == "oss": by[it["date"]].append(it)
for date, its in sorted(by.items()):
    its.sort(key=lambda i: (i["rank"] or 99, i["id"]))
    print(write_day("oss", date, {}, its), len(its))
