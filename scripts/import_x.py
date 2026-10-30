#!/usr/bin/env python3
"""Merge a raw collected+analysed X file into data/x/YYYY-MM-DD.json (Asia/Shanghai dates) and update state/x_state.json.

Usage:
  python3 scripts/import_x.py RAW.json          # merge (dedupe by post_id; re-importing a post overwrites it)
  python3 scripts/import_x.py --since           # print {handle: last_seen_post_id} for since_id queries
  python3 scripts/import_x.py --check RAW.json  # validate only, write nothing

RAW.json (produced by scripts/x_prepare.py, then filled in by the agent):
{
 "collected_at": "ISO time",
 "posts": [{"source","post_id","created_at"(ISO, UTC ok),"kind":"post|quote|reply","text","article_title"|null,
            "reply_to":{handle,post_id,url,text}|null, "quoted":{...}|null, "links":[{url,title}],
            "translation_zh", "analysis":{"summary","points"[1-6],"why","tags"[1-4]}}],
 "digests": {"YYYY-MM-DD": {"digest": "当日摘要", "by_source": {"handle": "一句话"}}}
}
Every date that receives a post must have a non-empty digest (in RAW or already in the existing day file).
Exit 1 with a list of problems on any validation error; nothing is written in that case.
"""
import datetime as dt, json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_common import XDATA, STATE, load_config, shanghai_dt, last_seen

KINDS = ("post", "quote", "reply")

def problems_for(p, handles):
    e = []; pid = p.get("post_id", "?")
    def s(k, v): return isinstance(v, str) and v.strip()
    if p.get("source") not in handles: e.append(f"{pid}: source {p.get('source')!r} not in config/x_sources.json")
    if not re.fullmatch(r"\d{5,25}", str(p.get("post_id", ""))): e.append(f"{pid}: post_id must be digits")
    try: shanghai_dt(p["created_at"])
    except Exception: e.append(f"{pid}: created_at missing/invalid ISO time")
    if p.get("kind") not in KINDS: e.append(f"{pid}: kind must be one of {KINDS}")
    if not s("text", p.get("text")) and not s("a", p.get("article_title")): e.append(f"{pid}: text (or article_title) required")
    if not s("t", p.get("translation_zh")): e.append(f"{pid}: translation_zh required")
    a = p.get("analysis") or {}
    if not s("s", a.get("summary")): e.append(f"{pid}: analysis.summary required")
    if not s("w", a.get("why")): e.append(f"{pid}: analysis.why required")
    pts, tags = a.get("points"), a.get("tags")
    if not isinstance(pts, list) or not 1 <= len(pts) <= 6 or not all(s("p", x) for x in pts): e.append(f"{pid}: analysis.points must be 1-6 strings")
    if not isinstance(tags, list) or not 1 <= len(tags) <= 4 or not all(s("g", x) for x in tags): e.append(f"{pid}: analysis.tags must be 1-4 strings")
    for k in ("reply_to", "quoted"):
        r = p.get(k)
        if r is not None and (not isinstance(r, dict) or not re.fullmatch(r"\d+", str(r.get("post_id", "")))): e.append(f"{pid}: {k} must be null or {{handle,post_id,url,text}}")
    if p.get("kind") == "reply" and not p.get("reply_to"): e.append(f"{pid}: kind=reply but reply_to is empty")
    if p.get("kind") == "quote" and not p.get("quoted"): e.append(f"{pid}: kind=quote but quoted is empty")
    return e

def to_item(p):
    t = shanghai_dt(p["created_at"]); h = p["source"]; pid = str(p["post_id"])
    def ref(r):
        if not r: return None
        rh = r.get("handle")
        return {"handle": rh, "post_id": str(r["post_id"]), "url": f"https://x.com/{rh}/status/{r['post_id']}" if rh else f"https://x.com/i/status/{r['post_id']}", "text": r.get("text")}
    return {"id": f"x-{pid}", "date": t.date().isoformat(), "type": "x", "source": h, "post_id": pid,
            "url": f"https://x.com/{h}/status/{pid}", "posted_at": t.isoformat(timespec="minutes"), "kind": p["kind"],
            "text": p.get("text") or "", "article_title": p.get("article_title"), "reply_to": ref(p.get("reply_to")), "quoted": ref(p.get("quoted")),
            "links": [l for l in p.get("links") or [] if isinstance(l, dict) and str(l.get("url", "")).startswith("http")],
            "translation_zh": p["translation_zh"].strip(), "analysis": {k: p["analysis"][k] for k in ("summary", "points", "why", "tags")}}

def write_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh: json.dump(obj, fh, ensure_ascii=False, indent=1); fh.write("\n")
    os.replace(tmp, path)

def main(argv):
    if argv[:1] == ["--since"]:
        print(json.dumps(last_seen(), indent=1)); return 0
    check = argv[:1] == ["--check"]; argv = argv[1:] if check else argv
    if len(argv) != 1: print(__doc__); return 2
    raw = json.load(open(argv[0], encoding="utf-8"))
    handles = {s["handle"] for s in load_config()["sources"]}
    posts = raw.get("posts") or []; digests = raw.get("digests") or {}
    errs = [x for p in posts for x in problems_for(p, handles)]
    if errs:
        print(f"[import_x] FAILED — {len(errs)} problem(s):", file=sys.stderr); [print("  - " + x, file=sys.stderr) for x in errs]; return 1
    items = [to_item(p) for p in posts]
    by_date = {}
    for it in items: by_date.setdefault(it["date"], []).append(it)
    docs = {}
    for d in sorted(set(by_date) | {k for k, v in digests.items() if (v or {}).get("digest")}):
        path = os.path.join(XDATA, f"{d}.json")
        doc = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"schema_version": 1, "type": "x", "date": d, "day": {}, "items": []}
        old = {i["post_id"]: i for i in doc["items"]}
        for it in by_date.get(d, []): old[it["post_id"]] = it
        doc["items"] = sorted(old.values(), key=lambda i: i["posted_at"], reverse=True)
        dg = digests.get(d) or {}
        if dg.get("digest"): doc["day"]["digest"] = dg["digest"].strip()
        if dg.get("by_source"): doc["day"].setdefault("by_source", {}).update({k: v for k, v in dg["by_source"].items() if v})
        doc["day"]["updated_at"] = raw.get("collected_at") or dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
        if not doc["items"]: continue
        if not (doc["day"].get("digest") or "").strip(): errs.append(f"{d}: day digest missing — add digests['{d}'].digest")
        docs[path] = doc
    if errs:
        print(f"[import_x] FAILED — {len(errs)} problem(s):", file=sys.stderr); [print("  - " + x, file=sys.stderr) for x in errs]; return 1
    if check: print(f"[import_x] check ok — {len(items)} post(s), {len(docs)} day file(s)"); return 0
    for path, doc in docs.items(): write_atomic(path, doc)
    ls = last_seen()
    for h, v in (raw.get("fetched_max_id") or {}).items():
        if h in handles and int(v) > int(ls.get(h, "0")): ls[h] = str(v)
    st = {"last_seen_id": ls, "last_import": raw.get("collected_at"), "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    write_atomic(STATE, st)
    per = {}
    for it in items: per[it["source"]] = per.get(it["source"], 0) + 1
    print(f"[import_x] merged {len(items)} post(s) {per} into {len(docs)} day file(s); state -> {os.path.relpath(STATE)}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
