# 🧪 Dual-Track Science Script Automation Engine V3
### —— 科學先決 × 爆點後置：人類創作者的靈感工作檯 ——

專為 YouTube 科普創作者設計的「科學-時事-社群」三軌創意引擎。採用 **Science-First, Hook-Last** 架構——先產出一篇站得住腳的科普核心，再以時事、動漫梗、網路迷因作為包裝層疊加爆點。

---

## 🚀 核心特色

- **🔬 科學先決管線**：從頂級期刊 (Nature, Science, ScienceDaily) 萃取底層機制，附帶可信度星級評分 (★★★)
- **🎯 三軌資料來源**：
  - **時事軌**：自由時報 / 公視 RSS → LLM 過濾政治八卦 → 提取底層運作機制
  - **科學軌**：5 大國際科學 RSS + Brave Search 動態檢索 → 白黑名單過濾
  - **社群軌**：瓦特兄弟 / 網路溫度計 / 木棉花 Shorts / 搞完君 → 動漫梗提取
- **🤖 Proposer-Critic 辯論引擎**：
  - **Proposer**：生成科學核心分析 + 三視角 Hook（幽默 / 動漫 / 懸疑）
  - **Critic**：替換測試 (Substitution Test) + 三維評分，最多 3 回合迭代
- **🎲 Surprise Me!**：一鍵隨機科學文獻 × 自動配對，打破創作瓶頸
- **💾 解耦爬取/生成**：爬取結果持久化至 SQLite，支援手動觸發，不必每次重新抓取

---

## 🛠️ 技術棧

| 類別 | 技術 |
|------|------|
| 後端 | FastAPI (Python) |
| 前端 | Vanilla HTML / CSS / JS (Glassmorphism 深色模式) |
| LLM | Google Gemini (`gemini-3-flash-preview`) via LangChain |
| 資料庫 | SQLite (6 表持久化) + ChromaDB (向量配對) |
| 爬蟲 | YouTube Data API v3, Brave Search API, Feedparser, BeautifulSoup |

---

## 📁 檔案結構

```text
project_root/
├── app.py                    # FastAPI 主應用 (12 條 V3 API 路由)
├── config.py                 # 集中設定 (模型/RSS/頻道/白黑名單/星級)
├── populate_db.py            # 一鍵爬取填充資料庫
├── .env                      # API 金鑰
├── crawlers/
│   ├── trend_crawler.py      # Module 1: 台灣新聞 RSS + LLM 過濾
│   ├── science_crawler.py    # Module 2: 科學 RSS + Brave + 信譽評分
│   └── social_crawler.py     # Module 3: YouTube 頻道 + 動漫梗提取
├── engine/
│   ├── pipeline.py           # V3 Science-First Proposer-Critic 引擎
│   └── vector_matching.py    # Legacy V2 ChromaDB 配對 (備用)
├── db/
│   ├── store.py              # SQLite 6 表 CRUD
│   └── dedup.py              # URL 去重
└── static/
    ├── index.html            # V3 三欄互動面板
    ├── style.css             # 深色主題 + Tab/Badge/星級樣式
    └── script.js             # 前端邏輯 (爬取控制/卡片選取/Hook Tab)
```

---

## 🔌 API 端點

| Method | Route | 說明 |
|--------|-------|------|
| `POST` | `/api/crawl/trends` | 觸發時事爬蟲 |
| `POST` | `/api/crawl/social` | 觸發社群爬蟲 |
| `POST` | `/api/crawl/science` | 觸發科學爬蟲 |
| `POST` | `/api/crawl/all` | 全部爬取 |
| `GET` | `/api/data/trends` | 讀取時事快取 |
| `GET` | `/api/data/social` | 讀取社群快取 |
| `GET` | `/api/data/science` | 讀取科學快取 |
| `POST` | `/api/generate` | 執行 V3 Pipeline 生成 |
| `POST` | `/api/surprise` | 隨機選文生成 |
| `POST` | `/api/science/evaluate` | 評估 URL 可信度 |
| `GET` | `/api/history` | 歷史記錄 |
| `POST` | `/api/save` | 儲存靈感 |

---

## ⚙️ 快速上手

### 1. 安裝依賴
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1       # Windows
# source venv/bin/activate        # Mac/Linux
pip install -r requirements.txt
```

### 2. 配置環境變數
```bash
cp .env.example .env
```
```env
GOOGLE_API_KEY=您的Gemini金鑰
BRAVE_API_KEY=您的BraveSearch金鑰
YOUTUBE_API_KEY=您的YouTube金鑰
```

### 3. 首次填充資料庫
```bash
python populate_db.py
```

### 4. 啟動伺服器
```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
訪問 `http://127.0.0.1:8000` 進入 V3 儀表板。

---

## 📡 監視頻道配置

至 `config.py` 修改 `TARGET_SOCIAL_CHANNELS` 加入您想監控的 YouTube 頻道：

```python
TARGET_SOCIAL_CHANNELS = [
    {"id": "頻道ID", "name": "顯示名稱", "category": "anime", "fetch_shorts_only": True},
    # category: gaming_meme / social_trend / anime / meme
]
```

標記為 `anime` 的頻道會自動觸發「動漫梗提取」；`fetch_shorts_only: True` 僅抓取 Shorts。

---

## 🛡️ 免責聲明
本工具僅供靈感發想輔助使用。產出之腳本內容需經人類創作者最終查核與潤飾。請遵守 YouTube 數據 API 之服務條款。
