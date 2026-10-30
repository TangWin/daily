#!/usr/bin/env python3
"""Turn saved X tool results (get_posts_by_ids / get_users_posts JSON, as written by CallDynamicTool write_to_file)
into a skeleton raw file for scripts/import_x.py. The agent then fills translation_zh + analysis + digest.

Usage: python3 scripts/x_prepare.py OUT.json RESULT_FILE [RESULT_FILE...]
- keeps only authors listed in config/x_sources.json
- skips pure reposts (retweeted) and posts already present in data/x/ (or <= state last_seen_id)
- drops low-value replies (x_common.low_value_reply: reply, <40 chars after removing @mentions/links, no link/media/quote)
- uses note_tweet.text (long posts) when present, expands t.co links from entities.urls
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x_common import load_config, known_ids, load_json_any, shanghai_date, low_value_reply

def clean_ref(t):
    t = re.sub(r"https://t\.co/\w+", "", html.unescape(t)); t = re.sub(r"^(@\w+\s+)+", "", t.strip()).strip()
    return t[:600] + ("…" if len(t) > 600 else "")

def main(out, files):
    cfg = load_config(); by_id = {s["user_id"]: s["handle"] for s in cfg["sources"]}
    have = known_ids()
    posts, users, inc = {}, {}, {}
    for f in files:
        d = load_json_any(f)
        for u in d.get("includes", {}).get("users", []): users[u["id"]] = u["username"]
        for t in d.get("includes", {}).get("tweets", []) + d.get("includes", {}).get("posts", []): inc[t["id"]] = t
        for t in d.get("data", []) if isinstance(d.get("data"), list) else [d.get("data")]:
            if t: posts[t["id"]] = {**posts.get(t["id"], {}), **t}
    out_posts, fetched, dropped = [], {}, []
    for pid, t in sorted(posts.items(), key=lambda kv: int(kv[0])):
        h = by_id.get(t.get("author_id"))
        if not h: continue
        if int(pid) > int(fetched.get(h, "0")): fetched[h] = pid
        if pid in have: continue
        refs = {r["type"]: r["id"] for r in t.get("referenced_tweets", [])}
        if "retweeted" in refs: continue
        text = (t.get("note_tweet") or {}).get("text") or t["text"]
        ents = (t.get("note_tweet") or {}).get("entities") or t.get("entities") or {}
        links = []
        for u in ents.get("urls", []):
            exp = u.get("expanded_url") or u.get("url")
            if re.match(r"^https?://(twitter|x)\.com/\w+/status/", exp or "") and ("quoted" in refs): text = text.replace(u["url"], "").strip(); continue
            if "/photo/" in (exp or "") or "/video/" in (exp or ""): text = text.replace(u["url"], "").strip(); continue
            text = text.replace(u["url"], exp)
            links.append({"url": exp, "title": u.get("title")})
        text = re.sub(r"\s*https://t\.co/\w+$", "", text).strip()
        def ref(kind):
            rid = refs.get(kind)
            if not rid: return None
            r = inc.get(rid, {}); rh = users.get(r.get("author_id")) or (users.get(t.get("in_reply_to_user_id")) if kind == "replied_to" else None)
            return {"handle": rh, "post_id": rid, "url": f"https://x.com/{rh or 'i'}/status/{rid}" if rh else f"https://x.com/i/status/{rid}",
                    "text": clean_ref((r.get("note_tweet") or {}).get("text") or r.get("text") or "") or None}
        kind = "reply" if "replied_to" in refs else "quote" if "quoted" in refs else "post"
        if kind == "reply":  # drop leading @mentions of the reply chain from the display text
            text = re.sub(r"^(@\w+\s+)+", "", text).strip()
        text = html.unescape(text)
        art = (t.get("article") or {}).get("title")
        if art and re.fullmatch(r"https://x\.com/i/article/\d+", text): text = ""
        if not art and not re.search(r"[A-Za-z0-9\u4e00-\u9fff]{2}", re.sub(r"https?://\S+", "", text)): continue  # emoji/link-only, nothing to analyse
        if low_value_reply(kind, text, links, refs.get("quoted"), bool((t.get("attachments") or {}).get("media_keys"))):
            dropped.append(pid); continue
        out_posts.append({"source": h, "post_id": pid, "created_at": t["created_at"], "date": shanghai_date(t["created_at"]),
                          "kind": kind, "text": text, "article_title": art, "reply_to": ref("replied_to"), "quoted": ref("quoted"),
                          "links": links, "translation_zh": "", "analysis": {"summary": "", "points": [], "why": "", "tags": []}})
    dates = sorted({p["date"] for p in out_posts})
    json.dump({"collected_at": None, "fetched_max_id": fetched, "posts": out_posts, "digests": {d: {"digest": "", "by_source": {}} for d in dates}}, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"[x_prepare] dropped {len(dropped)} low-value short repl(ies)")
    print(f"[x_prepare] {len(out_posts)} new post(s) -> {out}; dates: {', '.join(dates) or '-'}")

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    main(sys.argv[1], sys.argv[2:])
