#!/usr/bin/env python3
"""Screenshots with headless Chromium (playwright).
Usage: /workspace/.pwenv/bin/python scripts/shot.py [BASE_URL] [name ...]
  BASE_URL defaults to the live site https://tangwin.github.io/daily/ ; local preview: serve a dir that
  contains daily -> docs (see README) and pass http://127.0.0.1:8766/daily/
Writes shots/<name>-<variant>.png"""
import os, sys
from playwright.sync_api import sync_playwright
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
a = sys.argv[1:]
B = a.pop(0) if a and a[0].startswith("http") else "https://tangwin.github.io/daily/"
PAGES = {"home": "", "channel-news": "news/", "channel-idea": "idea/?tag=Coding%20Agent", "channel-oss": "oss/",
         "detail-news": "news/2026-10-22/#c-news-2026-10-22-01", "detail-idea": "idea/2026-10-22/#c-idea-2026-10-22-01",
         "detail-oss": "oss/2026-09-16/", "search": "search/?q=Java"}
VARIANTS = {"desktop-light": dict(viewport={"width": 1280, "height": 900}, color_scheme="light"),
            "desktop-dark": dict(viewport={"width": 1280, "height": 900}, color_scheme="dark"),
            "mobile-light": dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme="light")}
spec = a or ["home:desktop-light", "home:mobile-light"]
os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    try: b = p.chromium.launch()
    except Exception: b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
    for s in spec:
        name, _, vn = s.partition(":")
        for v in ([vn] if vn else list(VARIANTS)):
            ctx = b.new_context(**VARIANTS[v]); pg = ctx.new_page()
            pg.goto(B + PAGES[name], wait_until="networkidle"); pg.wait_for_timeout(600)
            path = f"{OUT}/{name}-{v}.png"
            if name == "home": pg.screenshot(path=path, full_page=True)
            elif name.startswith("detail"): pg.screenshot(path=path)
            else:
                h = pg.evaluate("document.documentElement.scrollHeight")
                pg.screenshot(path=path, full_page=True, clip={"x": 0, "y": 0, "width": VARIANTS[v]["viewport"]["width"], "height": min(h, 2200)})
            print(path); ctx.close()
    b.close()
