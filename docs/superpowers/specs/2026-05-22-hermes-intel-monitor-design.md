# Hermes — 全网情报监测站 · 技术设计

> 2026-05-22 · MVP v1

## 1. 项目概述

每天早上 9 点自动生成个性化情报简报，写入 Obsidian vault，自动关联已有知识节点。

**核心链路**：RSS → 语义去重 → LLM 初筛 → LLM 深度分析 → Obsidian（含 embedding 关联 + 反馈闭环）

**MVP 范围**：
- RSS 信源，每日一次
- 语义去重（URL + simhash）
- DeepSeek V4 Pro 两阶段 LLM 处理（初筛 + 分析）
- all-MiniLM-L6-v2 本地 embedding 做 Obsidian 节点关联
- 反馈闭环：用户 rating 1-5 → 下次 Filter 调整
- CLI 单次执行，cron 定时触发

**明确不做（v1）**：网页抓取、arXiv 论文、Web UI、团队协作

## 2. 技术栈

- Python 3.12+
- SQLite（标准库）
- feedparser（RSS 解析）
- html2text（HTML 清洗）
- openai SDK（DeepSeek V4 Pro 兼容接口）
- sentence-transformers（all-MiniLM-L6-v2，本地 embedding）
- python-frontmatter（Obsidian 笔记读写）
- cron / launchd（定时触发）

## 3. 项目结构

```
hermes/
├── hermes/
│   ├── __init__.py
│   ├── __main__.py          # python -m hermes run
│   ├── config.py            # YAML 配置加载
│   ├── db.py                # SQLite 初始化 + 读写
│   ├── models.py            # dataclass
│   ├── ingestors/
│   │   ├── __init__.py
│   │   └── rss.py           # feedparser
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── dedup.py         # URL + simhash
│   │   ├── filter.py        # LLM 初筛
│   │   ├── analyze.py       # LLM 深度分析
│   │   └── write.py         # Obsidian 输出
│   ├── embeddings.py        # sentence-transformers
│   └── notify.py            # 终端通知 / Slack webhook
├── config.yaml
├── pyproject.toml
└── tests/
```

## 4. 数据库设计

```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    source TEXT,
    title TEXT,
    url TEXT,
    content TEXT,
    published_at TIMESTAMP,
    simhash TEXT,
    cluster_id TEXT,
    relevance_score INTEGER,
    relevance_reason TEXT,
    analysis TEXT,
    linked_notes TEXT,          -- JSON array
    status TEXT DEFAULT 'new',  -- new/filtered/analyzed/written/skipped
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE feedback (
    item_id TEXT,
    rating INTEGER,             -- 1-5
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    stage TEXT,
    status TEXT,                -- started/ok/error
    item_count INTEGER,
    duration_ms INTEGER,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 5. 各阶段设计

### Stage 1: RSS Ingestor

- `feedparser` 解析 RSS 源
- 提取 title, url, published_at, content（优先 content:encoded，回退 summary）
- `html2text` 清洗 HTML → 纯文本
- 写入 items，id = sha256(url)
- 每个源独立 try/except，一个挂了不影响其他

### Stage 2: Dedup

- **URL 去重**：查 items 表，已有则跳过
- **语义去重**：前 500 字符算 simhash，Hamming distance ≤ 3 判为相似
- 相似 item 归入同一 cluster，选内容最长的为主 item，其余标记 skipped

### Stage 3: LLM Filter

- 读取 status='new' 的 item，按 cluster_id 分组
- DeepSeek V4 Pro，输出 JSON `{"score": int, "reason": "str"}`
- 分数 ≤ 2 → skipped，≥ 3 → filtered
- 阈值故意偏低（宁可多放）
- 并发：asyncio + semaphore，每批 10 个

### Stage 4: LLM Analyze

- 读取 status='filtered' 的 item
- 同事件多源报道合并分析
- 输出 JSON：title_cn, summary（批判性摘要）, key_points, implications, confidence
- confidence=low 在简报中标注"信源未充分验证"
- 并行调用

### Stage 5: Obsidian Writer

- **Embedding 索引**：启动时对 vault 所有 .md 编码，存 SQLite
- 每条分析完的 item 编码 → cosine similarity 取 Top-3
- 生成 `Intel Brief – YYYY-MM-DD.md`，按相关度分段（高/中/低）
- 嵌入反向链接 `[[已有笔记]]`
- **反馈闭环**：扫描 vault 中 `type: intel-brief` 笔记的 `rating` frontmatter → 写入 feedback 表 → 下次 Filter prompt 追加偏好

## 6. 运行日志

每个 stage 写入 run_log（stage, status, item_count, duration_ms, error）。执行完毕后终端输出摘要，可选 Slack webhook 通知。

## 7. 成本

DeepSeek V4 Pro，日均 ~11 万 token，约 ¥0.1。
