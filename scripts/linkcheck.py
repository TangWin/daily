#!/usr/bin/env python3
"""Check every internal link in the built site (docs/): href/src in HTML, <link> in RSS, <loc> in sitemap.
Internal = starts with /daily/ or https://tangwin.github.io/daily/. Also flags root-relative links that miss
the /daily/ base and #fragments that do not exist on the target page. Exit 1 on any problem.
Usage: python3 scripts/linkcheck.py [docs]"""
import glob, os, re, sys
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
BASE, SITE = "/daily/", "https://tangwin.github.io"

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.links, self.ids = [], set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"): self.ids.add(a["id"])
        for k in ("href", "src"):
            if a.get(k): self.links.append(a[k])

pages, ids = {}, {}
for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
    p = P(); p.feed(open(f, encoding="utf-8").read()); rel = os.path.relpath(f, OUT)
    pages[rel] = p.links; ids[rel] = p.ids

def target(path):
    rel = path[len(BASE):]
    if rel == "" or rel.endswith("/"): rel += "index.html"
    return rel

errs, n = [], 0
def check(src, link):
    global n
    if link.startswith(SITE + BASE): link = link[len(SITE):]  # other paths on the host (e.g. /blog/) are external sites
    if re.match(r"^(https?:|mailto:|data:|javascript:)", link): return
    n += 1
    s = urlsplit(link)
    if not s.path:  # same-page fragment
        if s.fragment and s.fragment not in ids.get(src, set()) and src.endswith(".html"): errs.append(f"{src}: missing anchor #{s.fragment}")
        return
    if not s.path.startswith(BASE): errs.append(f"{src}: link without {BASE} base: {link}"); return
    t = target(unquote(s.path))
    if not os.path.isfile(os.path.join(OUT, t)): errs.append(f"{src}: broken link {link} (no {t})"); return
    if s.fragment and t.endswith(".html") and s.fragment not in ids.get(t, set()): errs.append(f"{src}: missing anchor {link}")

for src, links in pages.items():
    for l in links: check(src, l)
for f in glob.glob(os.path.join(OUT, "**", "*.xml"), recursive=True):
    rel = os.path.relpath(f, OUT); txt = open(f, encoding="utf-8").read()
    for l in re.findall(r"<(?:link|loc)>([^<]+)</(?:link|loc)>", txt) + re.findall(r'<atom:link href="([^"]+)"', txt):
        check(rel, l.replace("&amp;", "&"))
if errs:
    print(f"[linkcheck] FAILED: {len(errs)} problem(s) in {len(pages)} pages", file=sys.stderr)
    for e in errs[:200]: print("  - " + e, file=sys.stderr)
    sys.exit(1)
print(f"[linkcheck] ok — {n} internal links in {len(pages)} HTML pages + feeds/sitemap")
