# 信源（X）更新 Runbook — 每 4 小时执行一次

目标：把 config/x_sources.json 里信源（karpathy / mattpocockuk / thedankoe）的**新**帖子（原创、引用、回复；不收纯转推）
采集下来，写原文 + 中文翻译 + 中文解读，合并进 `data/x/YYYY-MM-DD.json`，发布到 https://tangwin.github.io/daily/x/ 。

**没有新帖 → 什么都不做，不发布。**

工作目录：`/workspace/daily-hub`。X 读取额度：30 次/分钟、1000 次/天、每次最多 25 条结果；一次正常运行约 4 次调用。

## 1. 取上次看到的位置

```bash
cd /workspace/daily-hub && python3 scripts/import_x.py --since
```
输出 `{handle: last_seen_post_id}`。user_id 在 `config/x_sources.json`（karpathy=33836629，mattpocockuk=346640777，thedankoe=256523056）。

## 2. 拉新帖（X 内置公开读取工具，命名空间 `x`）

先按 `x-api-mcp-guide` skill 的规则使用。对每个信源调用一次（用 `write_to_file: true` 保存结果文件，记下路径）：

```
CallDynamicTool namespace=x toolName=get_users_posts
  arguments = {
    "id": "<user_id>",
    "since_id": "<last_seen_post_id>",      // 第 1 步的值；没有时改用 "start_time": 3 天前的 ISO 时间
    "max_results": 25,
    "exclude": "retweets",
    "post.fields": "created_at,author_id,conversation_id,in_reply_to_user_id,referenced_tweets,note_tweet,entities,article",
    "expansions": "author_id,referenced_tweets.id,referenced_tweets.id.author_id,in_reply_to_user_id",
    "user.fields": "username,name"
  }
```
- 若三个结果都是 `result_count: 0` / 没有 `data` → **结束，不发布**。
- 若某信源返回了 `meta.next_token`（> 25 条新帖），带 `pagination_token` 再取一页。
- 时间线结果可能缺 `note_tweet`（长帖全文）和 `entities`（t.co 展开）。把所有新帖 id 用逗号拼起来再调一次（≤100 个 id 一次）：

```
CallDynamicTool namespace=x toolName=get_posts_by_ids   write_to_file=true
  arguments = {"ids": "<id1,id2,...>", 同上的 post.fields / expansions / user.fields}
```

## 3. 生成待填写的骨架

```bash
python3 scripts/x_prepare.py /tmp/x_raw.json <第2步所有结果文件路径...>
```
它会：只保留配置里的作者、跳过纯转推、跳过 data/x 里已有的帖子、跳过只有表情/链接的帖子、用长帖全文、展开链接、
标出 kind（post/quote/reply）和被回复/被引用的帖子（reply_to / quoted）、按北京时间算出日期。
输出 `0 new post(s)` → **结束，不发布**。

## 4. 写翻译和解读（agent 手写，忠实于原文）

编辑 `/tmp/x_raw.json`，对每个 post 填：
- `translation_zh`：完整、忠实的中文翻译，不增删内容；保留换行和链接；专有名词（模型名、技能名如 /pr）保留原文。
- `analysis.summary`：一两句中文摘要。回复/引用要交代上下文（“有人说……，他回复……”）。
- `analysis.points`：1–6 条要点，只写帖子（及被回复/引用帖）里有的信息。
- `analysis.why`：为什么重要 / 解读。纯社交回复就直说“信息量很低”；作者的估算/观点要标明是观点而非数据；上下文不全要说明。
- `analysis.tags`：1–4 个中文/通用标签（如 Agent 工程、Skills、强化学习、创作者经济）。
- `digests["YYYY-MM-DD"]`：对骨架里列出的每个日期写 `digest`（当日整体摘要 1–3 句，如该日文件已存在，要概括全天含旧帖）和
  `by_source`（当日有帖的信源各一句）。
- `collected_at`：当前时间 ISO（如 `2026-10-30T16:20:00+09:00`）。

**不要编造**：不知道的背景（例如长文只拿到标题）就写“未采集到正文，不做推断”。

## 5. 校验、导入、发布

```bash
cd /workspace/daily-hub
python3 scripts/import_x.py --check /tmp/x_raw.json   # 有问题会列出并退出 1，改好再来
python3 scripts/import_x.py /tmp/x_raw.json           # 合并去重写入 data/x/，更新 state/x_state.json
./publish.sh -m "Publish x (信源) $(TZ=Asia/Shanghai date '+%F %H:%M') CST"
```
publish.sh 会再跑 validate → build → linkcheck → 单次 commit → push（从不 force-push；冲突时报错退出，不要强推）。

## 6. 验证

约 1 分钟后打开 https://tangwin.github.io/daily/x/ ，确认最新帖出现。

## 故障处理
- 429：等到 reset 时间后重试一次；当次不发布也没关系，下次会从 last_seen 继续。
- 某个信源报错：其余信源照常处理；last_seen 只按成功导入/取到的帖子前进。
- 想重做某条解读：把该帖重新放进 raw 文件（同 post_id）再 import，会覆盖旧版本。
- 增加信源：在 `config/x_sources.json` 加一项（用 `get_users_by_username` 查 user_id），头像下载到 `assets/x/<handle>.jpg`（可选）。
