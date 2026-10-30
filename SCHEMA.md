# 数据格式 v1（TangWin/daily）

三个频道的数据都在本仓库 `data/` 下，一天一个文件：

```
data/news/YYYY-MM-DD.json   AI 工程新闻（newsBot）
data/idea/YYYY-MM-DD.json   产品 Idea Top 5（X产品idea挖掘）
data/oss/YYYY-MM-DD.json    开源推荐（Open Source Scout Bot）
```

日期 = 期号日期（Asia/Shanghai）。写完后运行 `/workspace/daily-hub/publish.sh`。
`scripts/validate.py` 会检查下面所有规则，不合格就报错退出，不会构建也不会推送。

## 每日文件

```json
{
  "schema_version": 1,
  "type": "news | idea | oss",          // 必须等于所在目录
  "date": "YYYY-MM-DD",                 // 必须等于文件名
  "day": { ... },                        // 当天的元信息，见下
  "items": [ { 条目 }, ... ]             // 至少 1 条
}
```

`day` 各频道字段（原型里 days.json 的字段，`count`/`status` 在构建时自动算出）：
- news：`window`（时间窗文字）、`note`、`footer`、`highlights`（今日看点的 rank 列表，如 `[1,2,4]`）
- idea：`sample`（样本说明）
- oss：`{}`（成稿/候选状态由条目的 `detail.status` 推出）

## 条目（三个频道共用的顶层字段）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | `{type}-{date}-{rank 两位数}`，如 `news-2026-10-22-01`；开源调研候选用 repo 名，如 `oss-2026-10-18-openbot`。只能用字母数字 `._-` |
| `date` | `YYYY-MM-DD` | 等于文件日期 |
| `type` | `news` \| `idea` \| `oss` | 等于文件 type |
| `rank` | int \| null | 当天排序（新闻 1–N、Idea 1–5、开源 1–3；调研候选为 null） |
| `title` | string | 标题（非空） |
| `summary` | string | 一两句话，用在列表、首页和 RSS 里（非空） |
| `url` | string \| null | 主链接：新闻 = 第一个来源，Idea = 第一条用户原话链接，开源 = GitHub 仓库（开源必填） |
| `tags` | string[] | 跨频道统一后的标签（非空），用于筛选和搜索；映射见 `scripts/common.py` 的 `TAGMAP` |
| `raw_tags` | string[] | 机器人原本输出的标签（可为空） |
| `score` | number \| null | 新闻 = HN 分数，Idea = 商业潜力 1–5，开源 = star 数 |
| `score_label` | string \| null | 分数的显示文字 |
| `detail` | object | 各频道字段，见下 |

### detail · news
`heat`（热度文字）、`highlight`（bool）、`event`、`why`、`use`（三者必填）、`links[{name,url}]`

### detail · idea
`problem`、`target_users`、`quotes[{text,links[{label,url}]}]`（必填，可为空数组）、`existing`、`defects`、`solution`、`mvp`、`difficulty`（1–5）、`potential`（1–5）；可选 `sources`

### detail · oss
`status`：`picked`（当日推荐，已成稿）\| `candidate`（只有调研素材，页面标「调研候选」）
`repo`（`owner/name`，必填）、`homepage`、`stars`、`forks`、`license`、`language`、`latest_release`、`runners_up[]`、
`body_md`（完整中文成稿，Markdown；`picked` 必填）、`source_file`、`date_inferred`

Markdown 渲染支持：`##`/`###` 标题、`-` 列表、`1.` 列表、`**粗体**`、`` `代码` ``、`[文字](https://…)`、裸链接、`---`。

## Open Source Scout Bot：每天一条成稿

写 `data/oss/YYYY-MM-DD.json`，一个 `items` 元素，`rank: 1`，`id: oss-YYYY-MM-DD-01`，`detail.status: "picked"`。
完整模板：`examples/oss-pick.example.json`。然后 `/workspace/daily-hub/publish.sh`。

建议先写临时文件再 `mv` 成最终文件名（避免另一个机器人刚好在发布时读到半个文件）。

## 导入脚本（给另外两个机器人，保持它们原来的输出格式）

- `python3 scripts/import_news.py DATE` — `/workspace/briefing/data/DATE.json`（newsBot 原格式）→ `data/news/DATE.json`
- `python3 scripts/import_idea.py DATE` — `/workspace/idea-mining-DATE/top5.{json,md}` → `data/idea/DATE.json`（解析器与旧 idea-radar/build.py 相同）

## 信源频道（data/x/YYYY-MM-DD.json）

独立页面 `/daily/x/`（导航“信源”），**不进首页、不进搜索、没有 RSS**。信源固定在 `config/x_sources.json`
（`handle`、`user_id`、`name`、`bio`、`avatar`；头像文件在 `assets/x/<handle>.jpg`，缺失时显示首字母）。
日期 = 帖子发布时间换算到 Asia/Shanghai。文件由 `scripts/import_x.py` 写入，不要手改；流程见 `RUNBOOK_X.md`。

```json
{
  "schema_version": 1, "type": "x", "date": "2026-10-30",
  "day": {
    "digest": "当日整体中文摘要（必填）",
    "by_source": {"mattpocockuk": "该信源当日一句话"},
    "updated_at": "ISO 时间"
  },
  "items": [{
    "id": "x-2115855541285122189",          // x-<post_id>，全站唯一
    "date": "2026-10-30", "type": "x",
    "source": "mattpocockuk",                // 必须在 config 里
    "post_id": "2115855541285122189",
    "url": "https://x.com/mattpocockuk/status/2115855541285122189",   // 必须是这个格式
    "posted_at": "2026-10-30T01:17+08:00",
    "kind": "post | quote | reply",          // 纯转推不收
    "text": "英文原文（t.co 已展开，回复去掉开头的 @）",
    "article_title": null,                    // X 长文标题（若是长文）
    "reply_to": {"handle": "0x15f", "post_id": "…", "url": "…", "text": "被回复帖原文（截断 600 字）"} ,  // kind=reply 必填
    "quoted":   {"handle": "…", "post_id": "…", "url": "…", "text": "…"},                               // kind=quote 必填
    "links": [{"url": "https://…", "title": "…"}],
    "translation_zh": "完整、忠实的中文翻译（必填）",
    "analysis": {
      "summary": "中文摘要（必填，回复要交代上下文）",
      "points": ["要点 1–6 条"],
      "why": "为什么重要 / 解读（必填，信息量低就直说）",
      "tags": ["1–4 个标签"]
    }
  }]
}
```
`scripts/validate.py` 同样校验这些规则。采集状态（每个信源 last_seen_id）在 `state/x_state.json`（不入库；丢了会从 data/x 自动推出）。
