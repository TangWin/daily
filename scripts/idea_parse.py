"""Idea Top-5 parser, vendored verbatim from /workspace/idea-radar/build.py (lines 3-171) so the
X产品idea挖掘 bot output (/workspace/idea-mining-YYYY-MM-DD/top5.{md,json}) can be imported without the
old repo. load_day(dirpath) -> {"date","sample","ideas":[...]}."""
import json, glob, os, re, html, sys, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = "/workspace/idea-mining-*"
FIELDS = ["title", "problem", "target_users", "quotes", "existing", "defects", "solution", "mvp", "difficulty", "potential"]
ALIASES = {
    "title": ["title"], "problem": ["problem", "问题"],
    "target_users": ["target_users", "users", "目标用户"],
    "quotes": ["quotes", "用户原话"],
    "existing": ["existing_products", "existing", "已有产品"],
    "defects": ["competitor_defects", "defects", "existing_defects", "product_gaps", "gaps", "已有产品缺陷"],
    "solution": ["solution", "可能的产品方案"], "mvp": ["mvp", "MVP"],
    "difficulty": ["difficulty", "dev_difficulty", "开发难度"],
    "potential": ["potential", "commercial_potential", "business_potential", "商业潜力"],
}
MD_LABELS = [("problem", "问题"), ("target_users", "目标用户"), ("quotes", "用户原话"), ("defects", "已有产品缺陷|缺陷"),
             ("existing", "已有产品"), ("solution", "可能的产品方案|产品方案|方案"), ("mvp", "MVP"),
             ("difficulty", "开发难度"), ("potential", "商业潜力")]
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")

TAGS = [  # English terms are word-bounded (\b) to avoid hits like "git" in "digital", "ide" in "idea"
    ("Agent/AI编码", r"\b(?:agents?|agentic|claude|codex|cursor|copilot|llms?|mcp|prompts?|vibe.?cod\w*|coding)\b|编程|编码|提示词|token"),
    ("开发者工具", r"\b(?:cli|apis?|git|github|ssh|terminal|devops|vps|ide|self.?host\w*|sdk|webhooks?)\b|开发者|终端|部署|服务器|日志|代码|自托管"),
    ("支付/计费", r"\b(?:billing|stripe|invoices?|pricing|refunds?)\b|支付|计费|订阅|账单|发票|定价|退款|费用|收入"),
    ("增长/转化", r"\b(?:seo|marketing|distribution|growth)\b|增长|转化|获客|冷邮|分发|营销|落地页|首批|推广|激活"),
    ("Mac/桌面工具", r"\b(?:mac|macos|macbook|touch id|menu ?bar)\b|桌面|菜单栏|windows ?(?:应用|客户端|app)"),
    ("语言学习", r"\b(?:language learning|duolingo|vocabulary)\b|语言学习|外语|英语|学习者|词汇|可懂输入"),
    ("安全/隐私", r"\b(?:security|privacy|secrets?|creds|malware)\b|安全|隐私|密码|凭证|密钥|恶意|加密|爬虫"),
    ("电商", r"\b(?:shopify|sku|amazon|etsy|e-?commerce)\b|电商|商家|店铺|商品|采购|库存|市集"),
    ("运营/客服", r"\b(?:support|inbox|helpdesk|crm)\b|客服|运营|询盘|收件箱|工单|催收|催款|会计|行政|事务所"),
    ("个人/生活", r"\b(?:iphone|diy|family)\b|家庭|家人|照片|手机|键盘|木工|求职|面试|约会|生活"),
]

def first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None

def score(v):
    if isinstance(v, int): return v
    m = re.search(r"([1-5])\s*/\s*5", str(v or "")) or re.search(r"\b([1-5])\b", str(v or ""))
    return int(m.group(1)) if m else None

def norm_quotes(v):
    out = []
    for q in v or []:
        if isinstance(q, str):
            links = [{"label": a, "url": u} for a, u in LINK.findall(q)]
            out.append({"text": LINK.sub(lambda m: m.group(1), q).strip(), "links": links})
        elif isinstance(q, dict):
            t = first(q, ["text", "quote", "原话", "content"]) or ""
            u = first(q, ["url", "link", "source_url"])
            lab = first(q, ["source", "src", "label"]) or "来源"
            out.append({"text": t, "links": [{"label": str(lab), "url": u}] if u else []})
    return [q for q in out if q["text"]]

def to_text(v):
    if v is None: return None
    if isinstance(v, list): return "、".join(map(str, v))
    return str(v).strip() or None

def parse_md(text):
    sample = None
    for line in text.splitlines()[:8]:
        if "样本" in line:
            sample = re.sub(r"^[#\s]*", "", line).strip(); break
    blocks = re.split(r"^#{2,3}\s*(\d)\.\s*", text, flags=re.M)
    ideas = []
    for i in range(1, len(blocks) - 1, 2):
        rank, body = int(blocks[i]), blocks[i + 1]
        lines = body.split("\n")
        idea = {"rank": rank, "title": lines[0].strip().strip("[]").strip()}
        cur = None
        for ln in lines[1:]:
            if re.match(r"^#", ln): break
            m = re.match(r"^- \s*([^：:]{1,10})[：:]\s*(.*)$", ln)
            if m:
                lab, val = m.group(1).strip(), m.group(2).strip()
                cur = None
                for key, pat in MD_LABELS:
                    if re.fullmatch(pat, lab):
                        cur = key; break
                if cur in ("difficulty", "potential"):
                    idea[cur] = score(val)
                    m2 = re.search(r"商业潜力[：:]\s*([1-5])", val)
                    if m2: idea["potential"] = int(m2.group(1))
                    cur = None
                elif cur == "quotes":
                    idea["quotes"] = [val] if val else []
                elif cur:
                    idea[cur] = val
                continue
            sm = re.match(r"^\s+[-*]\s+(.*)$", ln)
            if sm and cur == "quotes":
                idea["quotes"].append(sm.group(1).strip())
            elif sm and cur and cur in idea:
                idea[cur] += "；" + sm.group(1).strip()
        if "quotes" in idea: idea["quotes"] = norm_quotes(idea["quotes"])
        ideas.append(idea)
    return sample, ideas

def json_ideas(d):
    if isinstance(d, list): return d
    for k in ("top5", "ideas", "items"):
        if isinstance(d.get(k), list): return d[k]
    return []

def sample_from_json(d):
    if not isinstance(d, dict): return None
    c = first(d, ["sample_counts", "counts", "samples"])
    tot = d.get("sample_total")
    if isinstance(c, dict):
        nums = {k: v for k, v in c.items() if isinstance(v, int)}
        s = " / ".join(f"{k} {v}" for k, v in nums.items())
        return f"样本 {tot} 条（{s}）" if tot else f"样本：{s}"
    return f"样本 {tot} 条" if tot else None

def load_day(dirpath):
    date = dirpath.rsplit("idea-mining-", 1)[1]
    md_sample, md_ideas = None, []
    if os.path.exists(f"{dirpath}/top5.md"):
        md_sample, md_ideas = parse_md(open(f"{dirpath}/top5.md", encoding="utf-8").read())
    jd, ji = None, []
    if os.path.exists(f"{dirpath}/top5.json"):
        try:
            jd = json.load(open(f"{dirpath}/top5.json", encoding="utf-8")); ji = json_ideas(jd)
        except Exception as e:
            print(f"[warn] {date}: bad json {e}", file=sys.stderr)
    n = max(len(ji), len(md_ideas))
    ideas = []
    for i in range(n):
        j = ji[i] if i < len(ji) and isinstance(ji[i], dict) else {}
        if j.get("markdown"):
            _, emb = parse_md("## 1. " + re.sub(r"^#{2,3}\s*\d\.\s*", "", j["markdown"].lstrip()))
            jm = emb[0] if emb else {}
        else: jm = {}
        rank = j.get("rank") or i + 1
        m = next((x for x in md_ideas if x["rank"] == rank), md_ideas[i] if i < len(md_ideas) else {})
        idea = {"rank": rank}
        for f in FIELDS:
            v = first(j, ALIASES[f])
            if f == "title" and v is None: v = first(j, ["problem", "问题"])
            if f == "quotes": v = norm_quotes(v) if v else None
            elif f in ("difficulty", "potential"): v = score(v) if v is not None else None
            elif f != "title": v = to_text(v)
            if v in (None, "", []): v = jm.get(f) or m.get(f)
            if v not in (None, "", []): idea[f] = v
        if "title" in idea: idea["title"] = re.sub(r"^\s*\d+[.、]\s*", "", str(idea["title"]).strip().strip("[]")).strip()
        try: idea["rank"] = int(idea["rank"])
        except (TypeError, ValueError): idea["rank"] = i + 1
        if not idea.get("quotes") and j.get("sources"):
            idea["quotes"] = []  # sources only; keep as links
            idea["sources"] = j["sources"]
        idea["tags"] = tag(idea)
        ideas.append(idea)
    sample = md_sample or sample_from_json(jd)
    return {"date": date, "sample": sample, "ideas": ideas}

def tag(idea):
    blob = " ".join(str(idea.get(k, "")) for k in ("title", "problem", "target_users", "solution", "mvp")).lower()
    tblob = str(idea.get("title", "")).lower()
    scored = []
    for name, pat in TAGS:
        hits = len(re.findall(pat, blob)) + 3 * len(re.findall(pat, tblob))
        if hits: scored.append((hits, name))
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:3]] or ["其他"]
