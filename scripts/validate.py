#!/usr/bin/env python3
"""Schema check for data/{news,idea,oss}/YYYY-MM-DD.json. Exit 1 (and print every problem) on any error.
Usage: python3 scripts/validate.py            # all files
       python3 scripts/validate.py FILE...    # only these files
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TYPES

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
errs = []

def err(f, msg): errs.append(f"{os.path.relpath(f, os.path.dirname(DATA))}: {msg}")

def is_str(v, empty=False): return isinstance(v, str) and (empty or v.strip() != "")
def is_url(v): return isinstance(v, str) and re.match(r"^https?://\S+$", v)
def str_list(v): return isinstance(v, list) and all(is_str(x) for x in v)

def check_item(f, typ, date, it, k, seen):
    p = f"items[{k}]"
    if not isinstance(it, dict): return err(f, f"{p} is not an object")
    for key in ("id", "date", "type", "title", "summary", "tags", "raw_tags", "detail"):
        if key not in it: err(f, f"{p} missing '{key}'")
    iid = it.get("id")
    if not is_str(iid) or not iid.startswith(f"{typ}-{date}-"): err(f, f"{p}.id must start with '{typ}-{date}-' (got {iid!r})")
    elif not re.match(r"^[A-Za-z0-9._-]+$", iid): err(f, f"{p}.id has unsafe characters: {iid!r}")
    elif iid in seen: err(f, f"{p}.id duplicated: {iid}")
    seen.add(iid)
    if it.get("date") != date: err(f, f"{p}.date {it.get('date')!r} != file date {date}")
    if it.get("type") != typ: err(f, f"{p}.type {it.get('type')!r} != {typ}")
    if not is_str(it.get("title")): err(f, f"{p}.title empty")
    if not is_str(it.get("summary")): err(f, f"{p}.summary empty")
    if it.get("url") is not None and not is_url(it.get("url")): err(f, f"{p}.url not http(s): {it.get('url')!r}")
    if not str_list(it.get("tags")) or not it.get("tags"): err(f, f"{p}.tags must be a non-empty list of strings")
    if not str_list(it.get("raw_tags")): err(f, f"{p}.raw_tags must be a list of strings (may be empty)")
    r = it.get("rank")
    if r is not None and (not isinstance(r, int) or isinstance(r, bool) or r < 1): err(f, f"{p}.rank must be int>=1 or null")
    if it.get("score") is not None and not isinstance(it.get("score"), (int, float)): err(f, f"{p}.score must be number or null")
    d = it.get("detail")
    if not isinstance(d, dict): return err(f, f"{p}.detail must be an object")
    if typ == "news":
        if not isinstance(r, int): err(f, f"{p}.rank required for news")
        for key in ("event", "why", "use"):
            if not is_str(d.get(key)): err(f, f"{p}.detail.{key} empty")
        links = d.get("links")
        if not isinstance(links, list) or not all(isinstance(l, dict) and is_str(l.get("name")) and is_url(l.get("url")) for l in links):
            err(f, f"{p}.detail.links must be [{{name,url}}]")
    elif typ == "idea":
        if not isinstance(r, int): err(f, f"{p}.rank required for idea")
        for key in ("difficulty", "potential"):
            v = d.get(key)
            if v is not None and (not isinstance(v, int) or not 1 <= v <= 5): err(f, f"{p}.detail.{key} must be 1-5 or null")
        q = d.get("quotes")
        if not isinstance(q, list) or not all(isinstance(x, dict) and isinstance(x.get("text"), str) and isinstance(x.get("links", []), list) for x in q):
            err(f, f"{p}.detail.quotes must be [{{text,links[{{label,url}}]}}]")
    elif typ == "oss":
        st = d.get("status")
        if st not in ("picked", "candidate"): err(f, f"{p}.detail.status must be 'picked' or 'candidate'")
        if not is_str(d.get("repo")) or not re.match(r"^[\w.-]+/[\w.-]+$", d.get("repo") or ""): err(f, f"{p}.detail.repo must be 'owner/name'")
        if not is_url(it.get("url")): err(f, f"{p}.url (GitHub repo URL) required for oss")
        if st == "picked":
            if not isinstance(r, int): err(f, f"{p}.rank required for a picked oss item")
            if not is_str(d.get("body_md")): err(f, f"{p}.detail.body_md (full Chinese write-up, Markdown) required for picked")
            for key in ("stars", "forks"):
                if d.get(key) is not None and not isinstance(d.get(key), int): err(f, f"{p}.detail.{key} must be int or null")
            if d.get("runners_up") is not None and not str_list(d.get("runners_up")): err(f, f"{p}.detail.runners_up must be list of strings")
            if d.get("homepage") is not None and not is_url(d.get("homepage")): err(f, f"{p}.detail.homepage must be http(s) or null")

def check_x_file(f, base, seen):
    from x_common import load_config
    from import_x import problems_for
    handles = {s["handle"] for s in load_config()["sources"]}
    try: doc = json.load(open(f, encoding="utf-8"))
    except Exception as e: return err(f, f"BAD JSON: {e}")
    if doc.get("schema_version") != 1 or doc.get("type") != "x" or doc.get("date") != base: err(f, "schema_version/type/date header wrong (need 1 / 'x' / file date)")
    if not is_str((doc.get("day") or {}).get("digest")): err(f, "day.digest required")
    items = doc.get("items")
    if not isinstance(items, list) or not items: return err(f, "items must be a non-empty list")
    for k, it in enumerate(items):
        if not isinstance(it, dict): err(f, f"items[{k}] not an object"); continue
        if it.get("id") != f"x-{it.get('post_id')}" or it["id"] in seen: err(f, f"items[{k}].id must be unique 'x-<post_id>'")
        seen.add(it.get("id"))
        if it.get("date") != base: err(f, f"items[{k}].date != file date")
        if it.get("url") != f"https://x.com/{it.get('source')}/status/{it.get('post_id')}": err(f, f"items[{k}].url must be https://x.com/<source>/status/<post_id>")
        if not is_str(it.get("posted_at")): err(f, f"items[{k}].posted_at required")
        for m in problems_for({**it, "created_at": it.get("posted_at")}, handles): err(f, f"items[{k}] {m}")

def check_file(f, seen):
    typ = os.path.basename(os.path.dirname(f)); base = os.path.basename(f)[:-5]
    if typ == "x" and DATE.match(base): return check_x_file(f, base, seen)
    if typ not in TYPES: return err(f, f"unknown channel dir '{typ}'")
    if not DATE.match(base): return err(f, "file name must be YYYY-MM-DD.json")
    try:
        with open(f, encoding="utf-8") as fh: doc = json.load(fh)
    except Exception as e:
        return err(f, f"BAD JSON: {e}")
    if not isinstance(doc, dict): return err(f, "top level must be an object")
    if doc.get("schema_version") != 1: err(f, "schema_version must be 1")
    if doc.get("type") != typ: err(f, f"type {doc.get('type')!r} != directory {typ}")
    if doc.get("date") != base: err(f, f"date {doc.get('date')!r} != file name {base}")
    if not isinstance(doc.get("day", {}), dict): err(f, "day must be an object")
    items = doc.get("items")
    if not isinstance(items, list) or not items: return err(f, "items must be a non-empty list")
    for k, it in enumerate(items): check_item(f, typ, base, it, k, seen)
    day = doc.get("day") or {}
    if typ == "news" and not all(isinstance(h, int) for h in day.get("highlights") or []): err(f, "day.highlights must be ranks (ints)")

def main(argv):
    files = argv or sorted(glob.glob(os.path.join(DATA, "*", "*.json")))
    stray = [f for f in glob.glob(os.path.join(DATA, "**", "*"), recursive=True) if os.path.isfile(f) and not f.endswith(".json") and not f.endswith(".gitkeep")]
    for f in stray: err(f, "unexpected non-JSON file in data/")
    seen = set()
    for f in files: check_file(os.path.abspath(f), seen)
    if errs:
        print(f"[validate] FAILED — {len(errs)} problem(s):", file=sys.stderr)
        for e in errs: print("  - " + e, file=sys.stderr)
        return 1
    print(f"[validate] ok — {len(files)} file(s)")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
