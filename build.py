#!/usr/bin/env python3
"""Build Peter 的每日雷达 (https://tangwin.github.io/daily/) into docs/.

Reads data/{news,idea,oss}/YYYY-MM-DD.json (see SCHEMA.md), writes static HTML for every page
(content works without JS; assets/app.js only adds filtering, search, theme and card toggling),
RSS feeds per channel, sitemap.xml, search index. Output is deterministic for the same data + date.

Usage: python3 build.py [--today YYYY-MM-DD] [--out docs]
"""
import argparse, datetime as dt, glob, html, json, os, re, shutil, sys
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "/daily/"
SITE = "https://tangwin.github.io"
SITE_URL = SITE + BASE
BRAND = "Peter 的每日雷达"
TZ = dt.timezone(dt.timedelta(hours=8))
CH = {
    "news": dict(name="新闻", full="AI 工程新闻", desc="每日精选 Agent、Coding Agent、MCP、Harness 与模型动态，只挑工作里用得上的。", eyebrow="Daily Briefing", hour=8, minute=30),
    "idea": dict(name="产品 Idea", full="产品 Idea Top 5", desc="从 HN、Reddit、Product Hunt、Indie Hackers 的真实抱怨里挖出的每日五个产品机会。", eyebrow="Idea Radar", hour=7, minute=0),
    "oss":  dict(name="开源", full="开源推荐", desc="每天 1–3 个值得今天就试的 AI 开源项目，读过完整 README、Issue 和提交记录后再推荐。", eyebrow="Daily OSS Pick", hour=9, minute=0),
}
WK = "一二三四五六日"
I = {
    "rss": '<svg viewBox="0 0 24 24"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1.2" fill="currentColor"/></svg>',
    "flame": '<svg viewBox="0 0 24 24"><path d="M12 3c1 3.5 5 5.5 5 10a5 5 0 0 1-10 0c0-2 1-3.4 2-4.4.3 1.6 1.2 2.6 2.2 2.9C10.6 9 11 5.6 12 3z"/></svg>',
    "star": '<svg viewBox="0 0 24 24"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/></svg>',
    "chev": '<svg viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg>',
    "auto": '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
}

def esc(s): return html.escape("" if s is None else str(s), quote=True)
def dparts(d):
    x = dt.date.fromisoformat(d); return x, "周" + WK[x.weekday()]
def mmdd(d): x, _ = dparts(d); return f"{x.month:02d}.{x.day:02d}"
def cn(d): x, _ = dparts(d); return f"{x.month}月{x.day}日"
def fmt_int(n): return f"{n:,}"

# ---------------- data ----------------
def load(data_dir):
    items, days = [], {}
    for typ in CH:
        for f in sorted(glob.glob(os.path.join(data_dir, typ, "????-??-??.json"))):
            doc = json.load(open(f, encoding="utf-8"))
            its = sorted(doc["items"], key=lambda i: (i.get("rank") or 99, i["id"]))
            day = dict(doc.get("day") or {}); day.update(type=typ, date=doc["date"], count=len(its))
            if typ == "oss":
                day["status"] = "picked" if any(i["detail"].get("status") == "picked" for i in its) else "candidate"
            days[(typ, doc["date"])] = day
            items.extend(its)
    return items, days

class Hub:
    def __init__(self, items, days, today):
        self.items, self.days, self.today = items, days, today
    def by_type(self, t): return [i for i in self.items if i["type"] == t]
    def dates(self, t): return sorted({i["date"] for i in self.by_type(t)}, reverse=True)
    def meta(self, t, d): return self.days.get((t, d), {})
    def day_items(self, t, d): return sorted([i for i in self.by_type(t) if i["date"] == d], key=lambda i: (i.get("rank") or 99))

# ---------------- urls ----------------
def u_home(): return BASE
def u_ch(t): return f"{BASE}{t}/"
def u_day(t, d, it=None): return f"{BASE}{t}/{d}/" + (f"#c-{it['id']}" if it else "")
def u_rss(t): return f"{BASE}{t}/rss.xml"
def u_search(q=None): return f"{BASE}search/" + (f"?q={q}" if q else "")

# ---------------- fragments (ported 1:1 from the prototype app.js) ----------------
def rss_link(t): return f'<a class="rss" href="{u_rss(t)}" title="{CH[t]["name"]} RSS">{I["rss"]}RSS</a>'
def tags_html(tags, n=9): return '<span class="tags">' + "".join(f'<span class="tag">{esc(t)}</span>' for t in tags[:n]) + "</span>"
def dots(v): return "".join(f'<b class="{"on" if k < (v or 0) else ""}"></b>' for k in range(5))
def meters(it):
    d = it["detail"]
    if d.get("difficulty") is None: return ""
    return (f'<span class="meter dif" title="开发难度 {d["difficulty"]}/5">难度<i>{dots(d["difficulty"])}</i></span>'
            f'<span class="meter pot" title="商业潜力 {d.get("potential")}/5">潜力<i>{dots(d.get("potential"))}</i></span>')
def score_html(it):
    d = it["detail"]
    if it["type"] == "news": return f'<span class="heat" title="热度">{I["flame"]}{esc(d["heat"])}</span>' if d.get("heat") else ""
    if it["type"] == "idea": return meters(it)
    if d.get("stars"): return f'<span class="star">{I["star"]}{fmt_int(d["stars"])}</span>'
    return "" if d.get("status") == "picked" else '<span class="tag">候选 · 仅 README</span>'
def oss_status(it):
    return '<span class="badge ch-oss">当日推荐</span>' if it["detail"].get("status") == "picked" else '<span class="badge" style="background:var(--s3);color:var(--mut)">调研候选</span>'
def ext(u, label):
    return f'<a href="{esc(u)}" target="_blank" rel="noopener">{label}</a>'

def page(title, body, nav, desc="AI 工程新闻、产品 Idea、开源推荐，每天一页。", canonical=BASE, extra_head=""):
    navs = [("home", u_home(), "今天"), ("news", u_ch("news"), "新闻"), ("idea", u_ch("idea"), "产品 Idea"), ("oss", u_ch("oss"), "开源")]
    nav_html = "".join(f'<a href="{h}" data-nav="{k}"{" class=\"on\" aria-current=\"page\"" if k == nav else ""}>{n}</a>' for k, h, n in navs)
    feeds = "".join(f'<link rel="alternate" type="application/rss+xml" title="{CH[t]["full"]} · {BRAND}" href="{u_rss(t)}">' for t in CH)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}{canonical}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{SITE}{canonical}"><meta property="og:type" content="website"><meta property="og:locale" content="zh_CN">
{feeds}
<script>/* mark JS + apply saved theme before paint */(function(){{var d=document.documentElement;d.className+=' js';try{{var t=localStorage.getItem('hub-theme');if(t)d.dataset.theme=t}}catch(e){{}}}})()</script>
<link rel="stylesheet" href="{BASE}assets/style.css">{extra_head}
</head>
<body data-base="{BASE}">
<a class="skip" href="#main">跳到正文</a>
<header class="site">
  <div class="bar wrap">
    <a class="brand" href="{BASE}"><span class="logo" aria-hidden="true"></span><span>{BRAND}</span></a>
    <nav class="nav" aria-label="频道">{nav_html}</nav>
    <form class="search" role="search" id="searchForm" action="{u_search()}" method="get">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input id="q" name="q" type="search" placeholder="搜索标题、标签、内容" aria-label="搜索" autocomplete="off">
    </form>
    <div class="acts">
      <a class="icon-btn blog" href="https://tangwin.github.io/blog/" title="博客">博客</a>
      <button class="icon-btn" id="themeBtn" type="button" aria-label="切换主题" title="主题：跟随系统（点击切换）">{I["auto"]}</button>
    </div>
  </div>
</header>
<main id="main" class="wrap" tabindex="-1">
{body}
</main>
<footer class="site-foot wrap">
  <span>{BRAND} · 每天北京时间 08:30 后更新</span>
  <span><a href="{u_ch('news')}">新闻</a> · <a href="{u_ch('idea')}">产品 Idea</a> · <a href="{u_ch('oss')}">开源</a> · <a href="https://tangwin.github.io/blog/">博客</a> · <a href="https://github.com/TangWin/daily">GitHub</a></span>
</footer>
<script src="{BASE}assets/app.js" defer></script>
</body>
</html>
"""

# ---------------- pages ----------------
def home(h):
    T = h.today; x, wk = dparts(T)
    nd, idd, od = (h.dates(t)[0] if h.dates(t) else None for t in CH)
    news = h.day_items("news", nd) if nd else []
    hl = h.meta("news", nd).get("highlights") or []
    news_top = ([i for i in news if i["rank"] in hl] + [i for i in news if i["rank"] not in hl])[:5]
    ideas = h.day_items("idea", idd)[:5] if idd else []
    oss = h.day_items("oss", od) if od else []
    oss_recent = [h.day_items("oss", d)[0] for d in h.dates("oss") if d != od][:4]
    def stale(d): return f'<div class="notice">今天（{cn(T)}）这个频道还没有更新，下面是最近一期 <b>{cn(d)}</b>。</div>' if d != T else ""
    news_rows = "".join(
        f'<li><a class="row" href="{u_day("news", nd, it)}"><span class="num">{it["rank"]:02d}</span><span class="t">{esc(it["title"])}</span>'
        + (f'<span class="s">{esc(it["summary"])}</span>' if k < 3 else "") + f'<span class="m">{score_html(it)}{tags_html(it["tags"], 2)}</span></a></li>'
        for k, it in enumerate(news_top))
    idea_rows = "".join(f'<li><a class="row" href="{u_day("idea", idd, it)}"><span class="num">#{it["rank"]}</span><span class="t">{esc(it["title"])}</span><span class="m">{meters(it)}</span></a></li>' for it in ideas)
    oss_cards = "".join(
        f'<div class="oss-card"><div class="repo">{esc(it["detail"]["repo"])} {oss_status(it)}</div><a class="t" href="{u_day("oss", od, it)}">{esc(it["title"])}</a><p>{esc(it["summary"])}</p>'
        f'<div class="tags">{score_html(it)}' + "".join(f'<span class="tag">{esc(t)}</span>' for t in it["tags"]) + "</div></div>" for it in oss[:3])
    oss_more = "".join(f'<li><span class="d mono">{mmdd(it["date"])}</span><a href="{u_day("oss", it["date"], it)}">{esc(it["detail"]["repo"])}</a></li>' for it in oss_recent)
    oss_line = f"{len(oss)} 个" if od == T else "今日暂无"
    return f"""<div class="page-h home-h"><div>
  <div class="eyebrow"><i></i>TODAY · {mmdd(T)}</div>
  <h1>{x.month}月{x.day}日 <small>{wk} · 今天的三份雷达</small></h1>
  <p class="lede">新闻 {len(news)} 条 · 产品 Idea {len(ideas)} 个 · 开源 {oss_line}</p>
</div></div>
<div class="today">
  <section class="block b-news ch-news" aria-labelledby="h-news">
    <div class="block-h"><span class="dot"></span><h2 id="h-news">AI 工程新闻</h2><span class="cnt">{cn(nd) if nd else ''} · 共 {len(news)} 条</span><span class="sp"></span>{rss_link('news')}</div>
    {stale(nd) if nd else ''}
    <ol>{news_rows}</ol>
    <div class="block-f"><a href="{u_day('news', nd) if nd else u_ch('news')}">看今天全部 {len(news)} 条 →</a><a href="{u_ch('news')}" class="mut">往期</a></div>
  </section>
  <section class="block b-idea ch-idea" aria-labelledby="h-idea">
    <div class="block-h"><span class="dot"></span><h2 id="h-idea">产品 Idea Top 5</h2><span class="cnt">{cn(idd) if idd else ''}</span><span class="sp"></span>{rss_link('idea')}</div>
    {stale(idd) if idd else ''}
    <ol>{idea_rows}</ol>
    <div class="block-f"><a href="{u_day('idea', idd) if idd else u_ch('idea')}">看痛点、原话和 MVP →</a><a href="{u_ch('idea')}" class="mut">往期</a></div>
  </section>
  <section class="block b-oss ch-oss" aria-labelledby="h-oss">
    <div class="block-h"><span class="dot"></span><h2 id="h-oss">开源推荐</h2><span class="sp"></span>{rss_link('oss')}</div>
    {stale(od) if od else ''}
    {oss_cards}
    <div class="oss-more"><h3>最近几期</h3><ul>{oss_more}</ul></div>
    <div class="block-f"><a href="{u_ch('oss')}">全部开源推荐 →</a></div>
  </section>
</div>"""

def channel(h, t):
    allx = h.by_type(t); cnt = {}
    for i in allx:
        for g in i["tags"]: cnt[g] = cnt.get(g, 0) + 1
    tags = [(g, n) for g, n in sorted(cnt.items(), key=lambda kv: -kv[1]) if n >= (1 if t == "oss" else 2)]
    ds = h.dates(t)
    pill = ""
    if t == "oss":
        np_ = sum(1 for d in ds if h.meta("oss", d).get("status") == "picked")
        nc = sum(1 for i in allx if i["detail"].get("status") != "picked")
        if nc: pill = f'<span class="pill">数据稀疏：{np_} 期成稿 + {nc} 个调研候选</span>'
    secs = []
    for d in ds:
        its = h.day_items(t, d); x, wk = dparts(d); dm = h.meta(t, d)
        st = (" · 成稿" if dm.get("status") == "picked" else " · 候选") if t == "oss" else ""
        rows = "".join(
            f'<li data-tags="{esc("|".join(it["tags"]))}"><a class="row" href="{u_day(t, d, it)}"><span class="num">{f"{it["rank"]:02d}" if it.get("rank") else "·"}</span>'
            f'<span class="t">{esc(it["title"])}</span><span class="m">{score_html(it)}{tags_html(it["tags"], 4)}</span></a></li>' for it in its)
        secs.append(f'<section class="day" data-date="{d}"><div class="day-d"><div class="md">{mmdd(d)}</div><div class="wk">{x.year} · {wk}{st}</div><a href="{u_day(t, d)}">当日详情 →</a></div>\n<ol>{rows}</ol></section>')
    chips = "".join(f'<button class="chip" type="button" data-tag="{esc(g)}" aria-pressed="false">{esc(g)}<span class="n">{n}</span></button>' for g, n in tags)
    return f"""<div class="page-h ch-head ch-{t}"><div>
  <div class="eyebrow"><i style="background:var(--c)"></i>{t.upper()} · ARCHIVE</div>
  <h1>{CH[t]['full']}</h1>
  <p class="lede">{CH[t]['desc']}</p>
  <div class="facts"><span><b>共</b>{len(ds)} 期 · {len(allx)} 条</span><span><b>最近更新</b>{cn(ds[0]) if ds else '—'}</span>{pill}</div>
</div>{rss_link(t)}</div>
<div class="chips" role="group" aria-label="按标签筛选" data-mode="archive" data-channel="{t}">
  <button class="chip" type="button" data-tag="" aria-pressed="true">全部<span class="n">{len(allx)}</span></button>
  {chips}
</div>
<p class="stat" id="stat">全部 {len(allx)} 条，按日期倒序</p>
<div id="arch" class="ch-{t}">{''.join(secs)}</div>
<p class="empty hide" id="empty">这个标签下没有内容</p>"""

def pager(h, t, d):
    ds = h.dates(t); k = ds.index(d)
    newer = ds[k - 1] if k > 0 else None; older = ds[k + 1] if k + 1 < len(ds) else None
    return (f'<nav class="pager" aria-label="翻页"><span>{f"<a href=\"{u_day(t, older)}\" rel=\"prev\">← {cn(older)}</a>" if older else ""}</span>'
            f'<a href="{u_ch(t)}">{CH[t]["name"]} · 全部往期</a><span>{f"<a href=\"{u_day(t, newer)}\" rel=\"next\">{cn(newer)} →</a>" if newer else ""}</span></nav>')
def crumbs(t, d): return f'<div class="crumbs"><a href="{BASE}">今天</a> / <a href="{u_ch(t)}">{CH[t]["name"]}</a> / {d}</div>'

def news_day(h, d):
    its = h.day_items("news", d); dm = h.meta("news", d); x, wk = dparts(d)
    hl = [i for r in (dm.get("highlights") or []) for i in its if i["rank"] == r]
    cnt = {}
    for i in its:
        for g in i["tags"]: cnt[g] = cnt.get(g, 0) + 1
    hl_html = "".join(f'<li><a href="#c-{it["id"]}" data-open="{it["id"]}"><span class="k"><span class="mono">{it["rank"]:02d}</span>{score_html(it)}</span><span class="t">{esc(it["title"])}</span><span class="s">{esc(it["summary"])}</span></a></li>' for it in hl)
    chips = "".join(f'<button class="chip" type="button" data-tag="{esc(g)}" aria-pressed="false">{esc(g)}<span class="n">{n}</span></button>' for g, n in sorted(cnt.items(), key=lambda kv: -kv[1]))
    cards = "".join(f"""<li class="card" id="c-{it['id']}" data-tags="{esc('|'.join(it['tags']))}">
<button class="head" type="button" aria-expanded="false"><span class="rk">{it['rank']:02d}</span><span class="title">{esc(it['title'])}</span><span class="chev">{I['chev']}</span><span class="sum">{esc(it['summary'])}</span><span class="meta">{tags_html(it['tags'])}{score_html(it)}</span></button>
<div class="body"><section class="blk"><h3>事件</h3><p>{esc(it['detail'].get('event'))}</p></section><section class="blk why"><h3>为什么值得关注</h3><p>{esc(it['detail'].get('why'))}</p></section><section class="blk"><h3>工作中怎么用</h3><p>{esc(it['detail'].get('use'))}</p></section>
<div class="src">{''.join(ext(l['url'], esc(l['name']) + ' ↗') for l in it['detail'].get('links') or [])}</div></div></li>""" for it in its)
    hl_block = f'<div class="sec-h"><h2>今日看点</h2><small>Top {len(hl)}</small></div>\n<ol class="hl">{hl_html}</ol>' if hl else ""
    return f"""<div class="narrow ch-news">{crumbs('news', d)}
<header class="page-h"><div class="eyebrow"><i></i>Daily Briefing · {mmdd(d)}</div>
<h1>{x.year}年{x.month}月{x.day}日 <small>{wk}</small></h1>
<p class="lede">今天筛出 {len(its)} 条值得一读的 AI 工程动态，点开卡片查看细节与落地建议。</p>
<div class="facts"><span><b>时间窗</b>{esc(dm.get('window'))}</span>{f'<span class="pill">{esc(dm.get("note"))}</span>' if dm.get('note') else ''}{rss_link('news')}</div></header>
{hl_block}
<div class="chips" role="group" aria-label="按标签筛选" data-mode="cards"><button class="chip" type="button" data-tag="" aria-pressed="true">全部<span class="n">{len(its)}</span></button>{chips}</div>
<ol class="cards">{cards}</ol>
<p class="empty hide" id="empty">这个标签下今天没有内容</p>
{f'<div class="foot-note"><b>其他：</b>{esc(dm["footer"])}</div>' if dm.get('footer') else ''}
{pager(h, 'news', d)}</div>"""

def idea_day(h, d):
    its = h.day_items("idea", d); dm = h.meta("idea", d); x, wk = dparts(d)
    def sec(hh, v): return f'<section class="blk"><h3>{hh}</h3><p>{esc(v)}</p></section>' if v else ""
    cards = []
    for it in its:
        v = it["detail"]; qs = v.get("quotes") or []
        prob = v.get("problem") or ""
        quotes = "".join(f'<blockquote>{esc(q.get("text"))}<span class="from">' + " · ".join(ext(l["url"], esc(l.get("label") or "来源") + " ↗") for l in q.get("links") or [] if l.get("url")) + "</span></blockquote>" for q in qs)
        srcs = ""
        if not qs and v.get("sources"):
            srcs = '<div class="src">' + "".join(ext(s.get("url"), esc(s.get("title") or s.get("label") or s.get("url")) + " ↗") if isinstance(s, dict) and s.get("url") else ext(s, esc(s) + " ↗") for s in v["sources"] if (isinstance(s, dict) and s.get("url")) or (isinstance(s, str) and s.startswith("http"))) + "</div>"
        cards.append(f"""<li class="card" id="c-{it['id']}">
<button class="head" type="button" aria-expanded="false"><span class="rk">#{it['rank']}</span><span class="title">{esc(it['title'])}</span><span class="chev">{I['chev']}</span><span class="sum"><b class="mut" style="font-weight:600">痛点</b> {esc(prob[:92])}…</span><span class="meta">{meters(it)}{tags_html(it['tags'])}</span></button>
<div class="body">{sec('痛点', v.get('problem'))}{sec('目标用户', v.get('target_users'))}
<div class="grid2 blk"><div class="box">{sec('现有方案', v.get('existing'))}</div><div class="box">{sec('现有方案的缺陷', v.get('defects'))}</div></div>
{sec('解决方案', v.get('solution'))}{sec('MVP', v.get('mvp'))}
<details class="q"><summary>用户原话 {len(qs)} 条</summary>{quotes}</details>{srcs}</div></li>""")
    return f"""<div class="narrow ch-idea">{crumbs('idea', d)}
<header class="page-h"><div class="eyebrow"><i style="background:var(--idea)"></i>Idea Radar · {mmdd(d)}</div>
<h1>{x.year}年{x.month}月{x.day}日 <small>{wk} · 产品 Idea Top 5</small></h1>
<p class="lede">难度点越少越容易，潜力点越多越好。点开查看痛点原话、现有方案和 MVP。</p>
<div class="facts"><span>{esc(dm.get('sample'))}</span>{rss_link('idea')}</div></header>
<div class="tools"><button type="button" id="openAll">全部展开</button><button type="button" id="closeAll">全部收起</button></div>
<ol class="cards">{''.join(cards)}</ol>
{pager(h, 'idea', d)}</div>"""

def md(src):
    """tiny markdown -> html, same rules as the prototype (headings, lists, bold, code, links)."""
    def inline(s):
        s = esc(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?:[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
        s = re.sub(r"(^|[\s(（])(https?://[^\s<)）]+)", r'\1<a href="\2" target="_blank" rel="noopener">\2</a>', s)
        return s.replace("&amp;lt;", "&lt;")
    out, lst = [], [None]
    def close():
        if lst[0]: out.append(f"</{lst[0]}>"); lst[0] = None
    for raw in (src or "").split("\n"):
        l = raw.rstrip()
        if not l.strip(): close(); continue
        if re.fullmatch(r"---+", l): close(); out.append("<hr>"); continue
        m = re.match(r"^(#{2,4})\s+(.*)", l)
        if m: close(); hh = min(len(m.group(1)), 3); out.append(f"<h{hh}>{inline(m.group(2))}</h{hh}>"); continue
        m = re.match(r"^\s*[-*]\s+(?:\[[x ]\]\s*)?(.*)", l)
        if m:
            if lst[0] != "ul": close(); out.append("<ul>"); lst[0] = "ul"
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        m = re.match(r"^\s*\d+\.\s+(.*)", l)
        if m:
            if lst[0] != "ol": close(); out.append("<ol>"); lst[0] = "ol"
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        if lst[0] and re.match(r"^\s{2,}", l) and out and out[-1].endswith("</li>"):
            out[-1] = out[-1][:-5] + " " + inline(l.strip()) + "</li>"; continue
        close(); out.append(f"<p>{inline(l)}</p>")
    close(); return "".join(out)

def oss_day(h, d):
    its = h.day_items("oss", d); x, wk = dparts(d)
    picked = [i for i in its if i["detail"].get("status") == "picked"]; cands = [i for i in its if i["detail"].get("status") != "picked"]
    parts = []
    for it in picked:
        v = it["detail"]
        kv = []
        if v.get("stars") is not None: kv.append(f'<span class="star">{I["star"]}{fmt_int(v["stars"])}</span>')
        if v.get("forks") is not None: kv.append(f'<span class="tag">{fmt_int(v["forks"])} forks</span>')
        for k in ("license", "language"):
            if v.get(k): kv.append(f'<span class="tag">{esc(v[k])}</span>')
        if v.get("latest_release"): kv.append(f'<span class="tag">最新发布 {esc(v["latest_release"])}</span>')
        if v.get("homepage"): kv.append(f'<a class="tag" href="{esc(v["homepage"])}" target="_blank" rel="noopener">主页 ↗</a>')
        parts.append(f"""<article class="repo-card" id="c-{it['id']}">
<div class="repo"><a href="{esc(it['url'])}" target="_blank" rel="noopener">{esc(v['repo'])} ↗</a> {oss_status(it)}</div>
<div class="t">{esc(it['title'])}</div><p>{esc(it['summary'])}</p>
<div class="kv">{''.join(kv)}</div>
<div class="kv">{''.join(f'<span class="badge ch-oss">{esc(t)}</span>' for t in it['tags'])}</div></article>
<div class="prose">{md(v.get('body_md'))}</div>""")
    if cands:
        lis = "".join(f'<li class="card cand" id="c-{it["id"]}"><div class="repo"><a href="{esc(it["url"])}" target="_blank" rel="noopener">{esc(it["detail"]["repo"])} ↗</a> {oss_status(it)}</div><h3>{esc(it["title"])}</h3><p>{esc(it["summary"])}</p><div class="tags">'
                      + "".join(f'<span class="tag">{esc(t)}</span>' for t in it["tags"]) + ('<span class="tag">日期按文件推断</span>' if it["detail"].get("date_inferred") else "")
                      + (f'<span class="tag">来源 {esc(it["detail"]["source_file"])}</span>' if it["detail"].get("source_file") else "") + "</div></li>" for it in cands)
        parts.append(f'<div class="notice"><b>这一天只有调研素材。</b>工作目录里只留下了下面这些项目的原始 README，没有找到成稿的推荐理由、Issue/提交核查，也无法确认最终推的是哪一个。</div>\n<ol class="cards">{lis}</ol>')
    return f"""<div class="narrow ch-oss">{crumbs('oss', d)}
<header class="page-h"><div class="eyebrow"><i style="background:var(--oss)"></i>Daily OSS Pick · {mmdd(d)}</div>
<h1>{x.year}年{x.month}月{x.day}日 <small>{wk} · 开源推荐</small></h1>
<div class="facts">{rss_link('oss')}</div></header>
{''.join(parts)}
{pager(h, 'oss', d)}</div>"""

def search_page():
    return f"""<div id="searchRoot" data-index="{BASE}search/index.json"><div class="page-h"><h1>搜索</h1><p class="lede">在上方输入关键词，例如「Java」「MCP」「支付」「Claude Code」。</p></div>
<noscript><p class="empty">搜索需要浏览器开启 JavaScript。也可以从 <a href="{u_ch('news')}">新闻</a>、<a href="{u_ch('idea')}">产品 Idea</a>、<a href="{u_ch('oss')}">开源</a> 的往期列表按标签浏览。</p></noscript></div>"""

def not_found():
    return f'<div class="page-h"><h1>页面不存在</h1><p class="lede">这个地址没有内容。去 <a href="{BASE}">今天</a>，或者看 <a href="{u_ch("news")}">新闻</a> · <a href="{u_ch("idea")}">产品 Idea</a> · <a href="{u_ch("oss")}">开源</a>。</p></div>'

# ---------------- feeds / index ----------------
def rss(h, t, limit=60):
    def pub(d):
        x = dt.date.fromisoformat(d)
        return format_datetime(dt.datetime(x.year, x.month, x.day, CH[t]["hour"], CH[t]["minute"], tzinfo=TZ))
    its = sorted(h.by_type(t), key=lambda i: (i["date"], -(i.get("rank") or 99)), reverse=True)[:limit]
    entries = []
    for it in its:
        link = SITE + u_day(t, it["date"], it)
        dh = ("【调研候选】" if t == "oss" and it["detail"].get("status") != "picked" else "") + esc(it["summary"])
        if t == "news" and it["detail"].get("why"): dh += "<p><b>为什么值得关注：</b>" + esc(it["detail"]["why"]) + "</p>"
        desc = esc(dh)
        cats = "".join(f"<category>{esc(g)}</category>" for g in it["tags"])
        entries.append(f"<item><title>{esc(f'[{mmdd(it['date'])}] ' + it['title'])}</title><link>{esc(link)}</link><guid isPermaLink=\"false\">{esc(it['id'])}</guid><pubDate>{pub(it['date'])}</pubDate>{cats}<description>{desc}</description></item>")
    last = pub(its[0]["date"]) if its else pub(h.today)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{esc(CH[t]['full'])} · {BRAND}</title>
<link>{SITE}{u_ch(t)}</link>
<atom:link href="{SITE}{u_rss(t)}" rel="self" type="application/rss+xml"/>
<description>{esc(CH[t]['desc'])}</description>
<language>zh-CN</language>
<lastBuildDate>{last}</lastBuildDate>
{chr(10).join(entries)}
</channel>
</rss>
"""

def search_index(h):
    out = []
    for i in sorted(h.items, key=lambda i: (i["date"], i["type"], i.get("rank") or 99), reverse=True):
        d = i["detail"]
        text = " ".join(str(d.get(k) or "") for k in ("repo", "event", "why", "use", "problem", "solution", "mvp", "body_md"))
        out.append({"id": i["id"], "type": i["type"], "date": i["date"], "title": i["title"], "summary": i["summary"],
                    "tags": i["tags"], "raw_tags": i.get("raw_tags") or [], "text": text})
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))

# ---------------- main ----------------
def write(out, rel, content):
    p = os.path.join(out, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh: fh.write(content)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=dt.datetime.now(TZ).date().isoformat())
    ap.add_argument("--out", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    a = ap.parse_args()
    items, days = load(a.data); h = Hub(items, days, a.today)
    out = a.out
    if os.path.isdir(out): shutil.rmtree(out)
    os.makedirs(out)
    pages = [BASE]
    write(out, "index.html", page(BRAND, home(h), "home"))
    for t in CH:
        write(out, f"{t}/index.html", page(f"{CH[t]['full']} · {BRAND}", channel(h, t), t, desc=CH[t]["desc"], canonical=u_ch(t)))
        write(out, f"{t}/rss.xml", rss(h, t)); pages.append(u_ch(t))
        R = {"news": news_day, "idea": idea_day, "oss": oss_day}[t]
        for d in h.dates(t):
            its = h.day_items(t, d)
            desc = f"{cn(d)} {CH[t]['full']}：" + "；".join(i["title"] for i in its[:3])
            write(out, f"{t}/{d}/index.html", page(f"{CH[t]['name']} {d} · {BRAND}", R(h, d), t, desc=desc[:160], canonical=u_day(t, d)))
            pages.append(u_day(t, d))
    write(out, "search/index.html", page(f"搜索 · {BRAND}", search_page(), "", canonical=u_search(), extra_head='\n<meta name="robots" content="noindex">'))
    write(out, "search/index.json", search_index(h))
    write(out, "404.html", page(f"页面不存在 · {BRAND}", not_found(), "", canonical=BASE).replace('<link rel="canonical"', '<meta name="robots" content="noindex"><link rel="canonical"'))
    write(out, "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(f"<url><loc>{SITE}{p}</loc></url>" for p in pages) + "\n</urlset>\n")
    write(out, "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
    write(out, ".nojekyll", "")
    os.makedirs(os.path.join(out, "assets"))
    for f in ("style.css", "app.js"): shutil.copy(os.path.join(ROOT, "assets", f), os.path.join(out, "assets", f))
    n = {t: (len(h.dates(t)), len(h.by_type(t))) for t in CH}
    print(f"[build] today={a.today} " + " ".join(f"{t}={n[t][0]}d/{n[t][1]}i" for t in CH) + f" pages={len(pages) + 1} -> {os.path.relpath(out, ROOT)}/")

if __name__ == "__main__":
    main()
