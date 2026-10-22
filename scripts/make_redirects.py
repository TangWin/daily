#!/usr/bin/env python3
"""Turn a clone of an old repo into redirect-only pages pointing at https://tangwin.github.io/daily/.

Usage: python3 scripts/make_redirects.py ai-briefing /workspace/redirects/ai-briefing
       python3 scripts/make_redirects.py idea-radar  /workspace/redirects/idea-radar
Covers every day page that exists in the clone AND every day in data/news (resp. data/idea), so re-running it
right before pushing also covers days the old bots published in the meantime. Old in-page anchors are mapped
(ai-briefing #item-N/#body-N, idea-radar #iN -> #c-<id>). Removes everything else (build scripts, data, css)
except .git; keeps .nojekyll; adds a 404.html that sends unknown paths to the channel archive."""
import glob, html, os, re, shutil, subprocess, sys

NEW = "https://tangwin.github.io/daily/"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = {
    "ai-briefing": dict(typ="news", name="AI 工程新闻", page=lambda d: f"{d[:4]}/{d[5:7]}/{d}.html",
                        pat=re.compile(r"^(\d{4})/(\d{2})/(\d{4}-\d{2}-\d{2})\.html$"), anchor=r"^#(?:item|body)-(\d+)$"),
    "idea-radar": dict(typ="idea", name="产品 Idea Top 5", page=lambda d: f"days/{d}.html",
                       pat=re.compile(r"^days/(\d{4}-\d{2}-\d{2})\.html$"), anchor=r"^#i(\d+)$"),
}

def redirect(target, label, anchor_js=""):
    t = html.escape(target, quote=True)
    js = f'var u="{target}",h=location.hash;{anchor_js}location.replace(u);'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>已搬家：{html.escape(label)} · Peter 的每日雷达</title>
<link rel="canonical" href="{t}">
<meta name="robots" content="noindex">
<script>{js}</script>
<meta http-equiv="refresh" content="0; url={t}">
<style>body{{font:16px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:560px;margin:15vh auto;padding:0 20px;color:#1c2024}}a{{color:#3a5bc7}}@media (prefers-color-scheme:dark){{body{{background:#111113;color:#edeef0}}a{{color:#9eb1ff}}}}</style>
</head>
<body>
<p>这个页面已经搬到 <b>Peter 的每日雷达</b>：</p>
<p><a href="{t}">{t}</a></p>
<p>如果没有自动跳转，请点上面的链接。</p>
</body>
</html>
"""

def main(kind, clone):
    c = CONF[kind]; typ = c["typ"]
    tracked = subprocess.run(["git", "-C", clone, "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    dates = set()
    for f in tracked:
        m = c["pat"].match(f)
        if m: dates.add(m.groups()[-1])
    dates |= {os.path.basename(f)[:-5] for f in glob.glob(f"{HERE}/data/{typ}/????-??-??.json")}
    for name in os.listdir(clone):  # wipe everything except .git
        if name == ".git": continue
        p = os.path.join(clone, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    def w(rel, s):
        p = os.path.join(clone, rel); os.makedirs(os.path.dirname(p) or clone, exist_ok=True)
        open(p, "w", encoding="utf-8").write(s)
    w("index.html", redirect(f"{NEW}{typ}/", c["name"]))
    w("404.html", redirect(f"{NEW}{typ}/", c["name"]))
    w(".nojekyll", "")
    for d in sorted(dates):
        a = (f'var m=h.match(/{c["anchor"]}/);if(m)u+="#c-{typ}-{d}-"+("0"+m[1]).slice(-2);')
        w(c["page"](d), redirect(f"{NEW}{typ}/{d}/", f'{c["name"]} {d}', a))
    w("README.md", f"# 已搬家\n\n{c['name']} 已并入 Peter 的每日雷达：{NEW}{typ}/ （源码与数据：https://github.com/TangWin/daily）。\n这个仓库只保留旧地址的跳转页。\n")
    print(f"[redirects] {kind}: index + 404 + {len(dates)} day pages -> {NEW}{typ}/")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
