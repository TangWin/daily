# Peter 的每日雷达

https://tangwin.github.io/daily/ — AI 工程新闻 · 产品 Idea Top 5 · 开源推荐，每天一页。

- 数据：`data/{news,idea,oss}/YYYY-MM-DD.json`，格式见 [SCHEMA.md](SCHEMA.md)
- 构建：`python3 build.py` → `docs/`（GitHub Pages 从 `main` 分支的 `/docs` 发布，无 Actions）
- 发布：`./publish.sh`（校验 → 构建 → 链接检查 → 只提交改动 → push 一次；有文件锁，多个机器人可同时调用）
  `./publish.sh --dry-run` 只校验和构建，`--no-push` 只提交不推送
- 前端：`assets/style.css`、`assets/app.js`（只负责主题、标签筛选、卡片展开和搜索；内容都是静态 HTML，不开 JS 也能看）
- 地址：`/daily/` 今天 · `/daily/news/` 等频道 · `/daily/news/2026-10-22/` 单日 · `/daily/search/?q=MCP` 搜索 ·
  `/daily/{news,idea,oss}/rss.xml` RSS · `/daily/sitemap.xml`
- 工具：`scripts/validate.py` 校验 · `scripts/linkcheck.py` 链接检查 · `scripts/import_news.py` / `scripts/import_idea.py` 导入旧格式 ·
  `scripts/shot.py` 截图（`/workspace/.pwenv/bin/python scripts/shot.py [BASE_URL]`）
- 本地预览：`mkdir -p /tmp/p && ln -sfn $PWD/docs /tmp/p/daily && cd /tmp/p && python3 -m http.server 8766`，打开 http://127.0.0.1:8766/daily/

历史数据：新闻来自 TangWin/ai-briefing（/workspace/briefing/data），Idea 来自 TangWin/idea-radar，开源来自 2 篇成稿 + 10 月调研候选（标「调研候选」）。
