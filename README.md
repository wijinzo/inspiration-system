# 🧪 Dual-Track Science Script Automation Engine V3
### —— 科學先決 × 爆點後置：人類創作者的靈感工作檯 ——

專為 YouTube 科普創作者設計的「科學-時事-社群」三軌創意引擎。採用 **Science-First, Hook-Last** 架構——先產出一篇站得住腳的科普核心，再以時事、動漫梗、網路迷因作為包裝層疊加爆點。

---

## 🚀 核心特色

- **🔬 科學先決管線**：從頂級期刊 (Nature, Science, ScienceDaily) 萃取底層機制，附帶可信度星級評分 (★★★)
- **🎯 三軌資料來源**：
  - **時事軌**：自由時報 / 公視 RSS + Google Trends RSS → LLM 過濾政治八卦 → 提取底層運作機制
  - **科學軌**：5 大國際科學 RSS + Brave Search 動態檢索 → 白黑名單過濾 → 全文解析
  - **社群軌**：瓦特兄弟官網 / 木棉花 Shorts / 搞完君 → 動漫梗提取（含歷史梗保留）
- **🤖 Proposer-Critic 辯論引擎**：
  - **Proposer**：生成科學核心分析 + 三視角 Hook（幽默 / 動漫 / 懸疑）
  - **Critic**：替換測試 (Substitution Test) + 三維評分，最多 3 回合迭代，門檻分數 ≥ 8
- **🎲 Surprise Me!**：一鍵隨機科學文獻 × 自動配對，打破創作瓶頸
- **💾 解耦爬取/生成**：爬取結果持久化至 SQLite，支援無限捲動分頁，不必每次重新抓取

---

## 🛠️ 技術棧

| 類別 | 技術 |
|------|------|
| 後端 | FastAPI (Python) |
| 前端 | Vanilla HTML / CSS / JS (Glassmorphism 深色模式) |
| LLM | Google Gemini (`gemini-3-flash-preview`) via LangChain |
| 資料庫 | SQLite (6 表持久化) + ChromaDB (向量配對，備用) |
| 爬蟲 | YouTube Data API v3, Brave Search API, Feedparser, BeautifulSoup |

---

## 📁 檔案結構

```text
project_root/
├── app.py                    # FastAPI 主應用 (12 條 V3 API 路由)
├── config.py                 # 集中設定 (模型/RSS/頻道/白黑名單/星級)
├── populate_db.py            # 一鍵爬取填充資料庫
├── start.bat                 # 雙擊一鍵啟動（自動啟用 venv + 開啟瀏覽器）
├── requirements.txt          # Python 依賴清單
├── .env                      # API 金鑰 (不進版本控制)
├── .env.example              # 金鑰範本
├── crawlers/
│   ├── trend_crawler.py      # Module 1: 台灣新聞 RSS + Google Trends + LLM 過濾
│   ├── science_crawler.py    # Module 2: 科學 RSS + Brave Search + 全文解析 + 信譽評分
│   └── social_crawler.py     # Module 3: 瓦特兄弟官網 + YouTube 頻道 (木棉花/搞完君) + 動漫梗提取
├── engine/
│   ├── pipeline.py           # V3 Science-First Proposer-Critic 引擎
│   └── vector_matching.py    # Legacy V2 ChromaDB 配對 (備用)
├── db/
│   ├── store.py              # SQLite 6 表 CRUD + 分頁查詢
│   └── dedup.py              # URL 去重
└── static/
    ├── index.html            # V3 三欄互動面板（無限捲動）
    ├── style.css             # 深色主題 + Tab/Badge/星級樣式
    └── script.js             # 前端邏輯 (爬取控制/卡片選取/Hook Tab)
```

---

## 🗄️ 資料庫結構（SQLite 6 表）

| 表名 | 用途 |
|------|------|
| `processed_articles` | URL 去重紀錄 |
| `science_articles` | 科學文獻（含機制摘要 & 可信度分） |
| `trend_items` | 新聞時事（含熱度評分） |
| `social_items` | 社群影片（YouTube Shorts & 一般影片，含縮圖） |
| `anime_memes` | 動漫梗解析（一對多綁定 `social_item_id`，歷史保留） |
| `generation_history` | Hook 生成歷史紀錄 |

---

## 🔌 API 端點

| Method | Route | 說明 |
|--------|-------|------|
| `GET` | `/api/data/trends?page=1&limit=15` | 讀取時事快取（支援分頁） |
| `GET` | `/api/data/social?page=1&limit=15` | 讀取社群快取（支援分頁） |
| `GET` | `/api/data/science?page=1&limit=15` | 讀取科學快取（支援分頁） |
| `GET` | `/api/history` | 讀取生成歷史 |
| `POST` | `/api/crawl/trends` | 觸發時事爬蟲 |
| `POST` | `/api/crawl/social` | 觸發社群爬蟲 |
| `POST` | `/api/crawl/science` | 觸發科學爬蟲 |
| `POST` | `/api/crawl/all` | 全部爬取 |
| `POST` | `/api/generate` | 執行 V3 Pipeline 生成 |
| `POST` | `/api/surprise` | 隨機選文生成 |
| `POST` | `/api/science/evaluate` | 評估 URL 可信度（回傳星級 & 白黑名單狀態） |
| `POST` | `/api/save` | 儲存靈感至 DB |

---

## ⚙️ 快速上手

### 安裝依賴
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1       # Windows PowerShell
# source venv/bin/activate        # Mac/Linux
pip install -r requirements.txt
```
### 配置環境變數
創建一個.env檔案(同.env.example內容)，並輸入金鑰

```env
GOOGLE_API_KEY=您的Gemini金鑰
BRAVE_API_KEY=您的BraveSearch金鑰
YOUTUBE_API_KEY=您的YouTube金鑰
```

接下來開啟系統

### 方法 A：全自動啟動 (推薦)

直接雙擊 `start.bat`，啟動器會自動檢測並執行以下流程：
1. **自動環境設置**：若無 `venv` 則自動建立並安裝 `requirements.txt`。
2. **自動配置檢查**：若無 `.env` 則自動複製 `.env.example`。
3. **自動資料初始化**：若無 `articles.db` 則自動執行 `populate_db.py` 進行首次爬取。
4. **自動開啟服務**：啟動 FastAPI 後端並自動開啟瀏覽器。

---

### 方法 B：手動啟動

#### 2. 填充資料庫
```bash
python populate_db.py
```

#### 3. 啟動伺服器
```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
訪問 `http://127.0.0.1:8000` 進入 V3 儀表板。

---

## 📡 監視頻道配置

至 `config.py` 修改 `TARGET_SOCIAL_CHANNELS`，加入您想監控的 YouTube 頻道：

```python
TARGET_SOCIAL_CHANNELS = [
    {
        "id": "UCgdwtyqBunlRb-i-7PnCssQ",
        "name": "木棉花",
        "category": "anime",       # anime 類別會自動觸發動漫梗提取
        "fetch_shorts_only": True  # 僅抓 Shorts
    },
    {
        "id": "UCwYTuoLZaII23xxAGV2zqcA",
        "name": "搞完君",
        "category": "meme",
        "fetch_shorts_only": False
    },
    # 新增頻道範例：
    # {"id": "頻道ID", "name": "顯示名稱", "category": "gaming_meme", "fetch_shorts_only": True},
]
```

**`category` 可用值：** `anime` / `gaming_meme` / `social_trend` / `meme`
標記為 `anime` 的頻道會自動觸發「動漫梗提取」流程，且每次爬取的梗解析結果都會累積保留（不覆蓋舊資料）。

---

## 🔬 科學來源可信度

| 分數 | 網域 |
|------|------|
| ★★★ (3) | `nature.com`, `science.org`, `cell.com` |
| ★★☆ (2) | `sciencedaily.com`, `phys.org`, `nationalgeographic.com` |
| ★☆☆ (1) | 其他白名單來源 |
| ❌ 封鎖 | `dailymail.co.uk`, `buzzfeed.com`, `reddit.com` 等（黑名單） |

可信度白黑名單及分數均可於 `config.py` 的 `SCIENTIFIC_WHITELIST` / `SCIENTIFIC_BLACKLIST` / `CREDIBILITY_SCORES` 調整。

---

## 🛡️ 免責聲明
本工具僅供靈感發想輔助使用。產出之腳本內容需經人類創作者最終查核與潤飾。請遵守 YouTube 數據 API 及 Brave Search API 之服務條款。
