"""Shared helpers for Peter 的每日雷达 (TangWin/daily): unified schema conversion + per-day file IO."""
import json, os, re, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TYPES = ("news", "idea", "oss")
SCHEMA_VERSION = 1

# canonical cross-channel tags (raw tags kept in raw_tags) — same map as the confirmed prototype
TAGMAP = {
    "支付系统": "支付", "支付": "支付", "争议": "有争议", "有争议": "有争议", "争议观点": "有争议", "观点": "有争议",
    "开源项目": "开源", "开源": "开源", "Harness Engineering": "Harness", "Harness": "Harness",
    "开发工具": "开发者工具", "架构": "工程实践", "推理": "模型", "供应链": "安全",
    "Agent/AI编码": "Coding Agent", "支付/计费": "支付", "安全/隐私": "安全", "Mac/桌面工具": "Mac/桌面",
}


def canon(tags):
    out = []
    for t in tags or []:
        c = TAGMAP.get(t, t)
        if c not in out:
            out.append(c)
    return out


def heat_num(h):
    m = re.search(r"HN\s*(\d+)", h or "")
    return int(m.group(1)) if m else None


def day_path(typ, date):
    return os.path.join(DATA, typ, f"{date}.json")


def write_day(typ, date, day, items):
    """Atomically write data/{typ}/{date}.json in the unified per-day format."""
    doc = {"schema_version": SCHEMA_VERSION, "type": typ, "date": date, "day": day, "items": items}
    path = day_path(typ, date)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def news_from_briefing(d):
    """newsBot format (/workspace/briefing/data/DATE.json) -> (day, items)."""
    date = d["date"]
    hl = d.get("highlights") or []
    day = {"window": d.get("window"), "note": d.get("note"), "footer": d.get("footer"), "highlights": hl}
    items = []
    for i, it in enumerate(d["items"], 1):
        links = it.get("links", [])
        items.append({
            "id": f"news-{date}-{i:02d}", "date": date, "type": "news", "rank": i,
            "title": it["title"], "summary": it["summary"],
            "url": links[0]["url"] if links else None,
            "tags": canon(it.get("tags", [])), "raw_tags": it.get("tags", []),
            "score": heat_num(it.get("heat")), "score_label": it.get("heat") or None,
            "detail": {"heat": it.get("heat"), "highlight": i in hl, "event": it.get("event"),
                       "why": it.get("why"), "use": it.get("use"), "links": links}})
    return day, items


def idea_from_radar(d):
    """X产品idea挖掘 format (idea-radar data/DATE.json or idea_parse.load_day output) -> (day, items)."""
    date = d["date"]
    day = {"sample": d.get("sample")}
    items = []
    for k, it in enumerate(d["ideas"], 1):
        r = it.get("rank") or k
        quotes = it.get("quotes") or []
        first = next((l["url"] for q in quotes for l in q.get("links", []) if l.get("url")), None)
        if not first and it.get("sources"):
            s0 = it["sources"][0]
            first = s0.get("url") if isinstance(s0, dict) else (s0 if isinstance(s0, str) and s0.startswith("http") else None)
        det = {k2: it.get(k2) for k2 in ["problem", "target_users", "quotes", "existing", "defects",
                                         "solution", "mvp", "difficulty", "potential"]}
        det["quotes"] = quotes
        if it.get("sources"):
            det["sources"] = it["sources"]
        items.append({
            "id": f"idea-{date}-{r:02d}", "date": date, "type": "idea", "rank": r,
            "title": it["title"], "summary": it.get("solution") or it.get("problem"),
            "url": first, "tags": canon(it.get("tags", [])), "raw_tags": it.get("tags", []),
            "score": it.get("potential"),
            "score_label": f"潜力 {it.get('potential')}/5 · 难度 {it.get('difficulty')}/5",
            "detail": det})
    return day, items
