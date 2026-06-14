# 🧪 Dual-Track Science Script Automation Engine V3
### —— 科學先決 × 爆點後置：人類創作者的靈感工作檯 ——

專為 YouTube 科普創作者設計的「科學-時事-社群」三軌創意引擎。採用 **Science-First, Hook-Last** 架構——先產出站得住腳的科普核心，再以時事、動漫梗、網路迷因包裝爆點，最後由雙 Agent 大腦自動撰寫完整腳本並匯出 Word 檔。

---

## 🚀 核心特色

### 📡 三軌資料蒐集（解耦爬取）
- **時事軌**：自由時報 / 公視 RSS + Google Trends RSS → LLM 政治雜訊過濾 → 底層機制提取
- **科學軌**：5 大國際科學 RSS（ScienceDaily / Nature / Science.org）+ Brave Search 動態檢索 → 白黑名單過濾 → 可信度星級評分（★★★）→ 全文解析
- **社群軌**：瓦特兄弟官網 / 木棉花 Shorts / 搞完君 → 動漫梗提取（歷史保留不覆蓋）

### 🤖 Proposer-Critic 辯論引擎（V3 核心）
```
科學文獻 (Science Core)
        ↓
Proposer 生成「科學核心分析」+ 三視角 Hook（幽默 / 動漫 / 懸疑）
        ↓
Critic 執行「魔法替換測試」+ 三維評分（科學先決/吸引力/格式）
        ↓
未達門檻（< 8 分）→ 附帶評審意見反饋給 Proposer → 最多 3 回合
        ↓
通過 → 輸出最佳 Hook + 評審報告
```

### ✍️ 雙 Agent 腳本生成
選定 Hook 後，一鍵啟動兩階段深度撰稿：

| Agent | 角色 | 任務 |
|-------|------|------|
| **Agent 1 (The Analyst)** | 科學解構分析師 | 將論文拆解為六大區塊（背景/痛點/核心問題/方法/結果/展望），為每塊產出生動比喻（含量化數據保留） |
| **Agent 2 (The Script Writer)** | 首席腳本作家 | 基於 Agent 1 輸出 + 腳本範本語氣，撰寫 ~1300 字的泛科學風格完整腳本，含懸念銜接與創意標題 |

### 📄 智慧 PDF 文獻獲取
- **三層 Fallback 策略**：OpenAlex API → ScienceDirect 全文爬取（trafilatura）→ 網頁新聞稿
- **PDF 內容驗證**：透過 DOI regex 比對或論文標題關鍵字命中率（閾值 40%）確認 PDF 為正確論文，防止下載錯誤
- **本地快取**：PDF / 全文存於 `data/pdfs/`，下次直接讀取不重複下載

### 💾 其他功能
- **手動上傳**：浮動按鈕新增科學論文（支援 PDF）或社群迷因梗，LLM 自動提取 mechanism/category
- **刪除功能**：三軌資料卡片均可單筆刪除（social 同步清除關聯 anime_memes）
- **搜尋過濾**：科學軌支援全文關鍵字搜尋（標題/分類/機制）
- **無限捲動分頁**：三欄均支援前端懶加載，不必一次載入全部
- **匯出 DOCX**：腳本一鍵匯出 Word 格式供編輯參考
- **🎲 Surprise Me!**：隨機挑選科學文獻自動配對生成，打破創作瓶頸
- **歷史記錄**：所有生成靈感持久化至 SQLite，可隨時回溯

---

## 🛠️ 技術棧

| 類別 | 技術 |
|------|------|
| 後端 | FastAPI (Python) |
| 前端 | Vanilla HTML / CSS / JS（Glassmorphism 深色模式） |
| LLM | Google Gemini (`gemini-3-flash-preview`) via LangChain |
| 資料庫 | SQLite（6 表持久化）+ ChromaDB（向量配對，備用） |
| 爬蟲 | YouTube Data API v3, Brave Search API, Feedparser, BeautifulSoup, trafilatura, cloudscraper |
| PDF | PyMuPDF（`fitz`）解析 + OpenAlex API 自動下載 |
| 匯出 | python-docx（Markdown → DOCX） |

---

## 📁 檔案結構

```text
project_root/
├── app.py                    # FastAPI 主應用（19 條 API 路由）
├── config.py                 # 集中設定（模型/RSS/頻道/白黑名單/星級/DB路徑）
├── populate_db.py            # 一鍵爬取填充資料庫
├── start.bat                 # 雙擊一鍵啟動（自動啟用 venv + 開啟瀏覽器）
├── requirements.txt          # Python 依賴清單
├── 腳本範本.md               # 泛科學風格腳本語氣範本（Agent 2 學習用）
├── .env                      # API 金鑰（不進版本控制）
├── .env.example              # 金鑰範本
│
├── crawlers/
│   ├── trend_crawler.py      # Module 1：台灣新聞 RSS + Google Trends + LLM 過濾
│   ├── science_crawler.py    # Module 2：科學 RSS + Brave Search + 全文解析 + 信譽評分
│   ├── social_crawler.py     # Module 3：瓦特兄弟官網 + YouTube 頻道（木棉花/搞完君）+ 動漫梗提取
│   ├── article_scraper.py    # 特定網站全文爬蟲（ScienceDaily 等）+ paper_doi/title 萃取
│   ├── pdf_downloader.py     # 智慧 PDF 下載器（OpenAlex → ScienceDirect → trafilatura）
│   └── pdf_parser.py         # PDF 轉文字解析器（PyMuPDF），含 UnreadablePDFError 處理
│
├── engine/
│   ├── pipeline.py           # V3 Science-First Proposer-Critic 辯論引擎
│   ├── script_generator.py   # 雙 Agent 腳本生成（Agent 1 解構 + Agent 2 撰稿）
│   └── vector_matching.py    # Legacy V2 ChromaDB 配對（備用）
│
├── db/
│   ├── store.py              # SQLite 6 表 CRUD + 分頁查詢 + 精確 URL 查找 + 刪除
│   └── dedup.py              # URL 去重
│
├── data/
│   └── pdfs/                 # 本地 PDF / trafilatura 全文快取
│
└── static/
    ├── index.html            # V3 三欄互動面板（無限捲動 + 手動上傳 Modal）
    ├── style.css             # 深色主題 + Glassmorphism + Tab/Badge/星級樣式
    └── script.js             # 前端邏輯（爬取控制/卡片選取/Hook Tab/腳本展示/匯出）
```

---

## 🗄️ 資料庫結構（SQLite 6 表）

| 表名 | 主要欄位 | 用途 |
|------|---------|------|
| `processed_articles` | `url`, `title`, `source` | URL 全域去重紀錄 |
| `science_articles` | `title`, `summary`, `mechanism`, `category`, `credibility_score`, `pdf_path`, `paper_title`, `paper_doi` | 科學文獻（含機制摘要、PDF 路徑、DOI） |
| `trend_items` | `title`, `summary`, `mechanism`, `heat_score` | 新聞時事（含熱度評分） |
| `social_items` | `title`, `summary`, `category`, `is_short`, `thumbnail` | 社群影片（YouTube Shorts & 一般影片） |
| `anime_memes` | `social_item_id`, `anime_name`, `meme_content`, `related_topics_json` | 動漫梗解析（一對多綁定，歷史保留不覆蓋） |
| `generation_history` | `science_core`, `mechanism`, `hooks_json`, `critic_score`, `reasoning`, `critic_comment`, `hook_evaluations_json` | Hook 與腳本生成歷史 |

---

## 🔌 API 端點

### 資料讀取
| Method | Route | 說明 |
|--------|-------|------|
| `GET` | `/api/data/trends?page=1&limit=15` | 讀取時事快取（支援分頁） |
| `GET` | `/api/data/social?page=1&limit=15` | 讀取社群快取（支援分頁） |
| `GET` | `/api/data/science?page=1&limit=15&search=關鍵字` | 讀取科學快取（支援分頁+搜尋） |
| `GET` | `/api/history` | 讀取生成歷史（最近 50 筆） |

### 爬蟲觸發
| Method | Route | 說明 |
|--------|-------|------|
| `POST` | `/api/crawl/trends` | 觸發時事爬蟲 |
| `POST` | `/api/crawl/social` | 觸發社群爬蟲 |
| `POST` | `/api/crawl/science` | 觸發科學爬蟲 |
| `POST` | `/api/crawl/all` | 全部爬取（依序執行三軌） |

### 生成與腳本
| Method | Route | 說明 |
|--------|-------|------|
| `POST` | `/api/generate` | 執行 V3 Proposer-Critic Pipeline |
| `POST` | `/api/surprise` | 隨機選文生成 |
| `POST` | `/api/build_script` | 雙 Agent 完整腳本生成（含 PDF 獲取） |
| `POST` | `/api/export_docx` | Markdown 腳本匯出為 DOCX |

### 資料管理
| Method | Route | 說明 |
|--------|-------|------|
| `POST` | `/api/save` | 儲存靈感至 DB |
| `DELETE` | `/api/data/{item_type}?url=...` | 刪除單筆資料（science/social/trend） |
| `POST` | `/api/science/evaluate` | 評估 URL 可信度（回傳星級 & 白黑名單狀態） |
| `POST` | `/api/manual/science` | 手動新增科學論文（支援 PDF 上傳） |
| `POST` | `/api/manual/social` | 手動新增迷因/社群內容 |

---

## 🔬 兩階段生成流程圖

```
[使用者選取卡片]
科學文獻 + (時事) + (社群)
        │
        ▼
[POST /api/generate]
  Proposer → 科學核心 + 3 視角 Hook
  Critic   → 三維評分（≥ 8 通過）
  ↓ 最多 3 回合迭代
  輸出：science_core / hooks[3] / hook_evaluations / critic_score
        │
[使用者選擇最佳 Hook]
        │
        ▼
[POST /api/build_script]
  Step 0: 即時萃取 paper_doi / paper_title（若無）
  Step 1: OpenAlex → PDF 自動下載（或讀本地快取）
  Step 2: 讀取 PDF / 全文（含驗證）
  Step 3: 爬取網頁新聞稿（作 Fallback / 框架參考）
  Step 4: Agent 1 → 六大區塊 + 深度比喻（JSON）
  Step 5: Agent 2 → 完整 ~1300 字 Markdown 腳本
        │
        ▼
[POST /api/export_docx]  →  下載 script_generated.docx
```

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
複製 `.env.example` 為 `.env` 並填入金鑰：
```env
GOOGLE_API_KEY=您的Gemini金鑰
BRAVE_API_KEY=您的BraveSearch金鑰
YOUTUBE_API_KEY=您的YouTube金鑰
```

### 啟動

#### 方法 A：全自動啟動（推薦）

直接雙擊 `start.bat`，啟動器自動執行以下流程：
1. **環境設置**：若無 `venv` 則自動建立並安裝依賴
2. **配置檢查**：若無 `.env` 則自動複製 `.env.example`
3. **資料初始化**：若無 `articles.db` 則自動執行 `populate_db.py` 首次爬取
4. **開啟服務**：啟動 FastAPI 後端並自動開啟瀏覽器

#### 方法 B：手動啟動
```bash
# 填充資料庫（首次必須）
python populate_db.py

# 啟動伺服器
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

訪問 `http://127.0.0.1:8000` 進入 V3 儀表板。

---

## 📡 監視頻道配置

至 `config.py` 修改 `TARGET_SOCIAL_CHANNELS`：

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
    # 新增範例：
    # {"id": "頻道ID", "name": "顯示名稱", "category": "gaming_meme", "fetch_shorts_only": True},
]
```

> **注意**：瓦特兄弟官網（`WATTBROTHER_URL`）採用**網頁爬取**而非 YouTube API，設定在 `config.py` 的 `WATTBROTHER_URL` 欄位。

**`category` 可用值：** `anime` / `gaming_meme` / `social_trend` / `meme`  
標記為 `anime` 的頻道會自動觸發「動漫梗提取」流程，且每次爬取的梗解析結果均累積保留（不覆蓋舊資料）。

---

## 🔬 科學來源可信度

| 分數 | 網域 |
|------|------|
| ★★★ (3) | `nature.com`, `science.org`, `cell.com` |
| ★★☆ (2) | `sciencedaily.com`, `phys.org`, `nationalgeographic.com` |
| ★☆☆ (1) | 其他白名單來源（`thelancet.com`, `nejm.org`, `pnas.org` 等） |
| ❌ 封鎖 | `dailymail.co.uk`, `buzzfeed.com`, `reddit.com` 等（黑名單） |

白黑名單及分數均可於 `config.py` 的 `SCIENTIFIC_WHITELIST` / `SCIENTIFIC_BLACKLIST` / `CREDIBILITY_SCORES` 調整。

---

## 🔑 主要環境變數與設定

| 變數 / 設定 | 位置 | 說明 |
|------------|------|------|
| `GOOGLE_API_KEY` | `.env` | Gemini LLM |
| `BRAVE_API_KEY` | `.env` | Brave Search 動態科學檢索 |
| `YOUTUBE_API_KEY` | `.env` | YouTube Data API v3 |
| `MODEL_NAME` | `config.py` | Gemini 模型名稱（預設 `gemini-3-flash-preview`） |
| `TEMPERATURE_FILTER` | `config.py` | 過濾/分析用溫度（預設 `0.1`，低溫度 = 精確） |
| `TEMPERATURE_CREATIVE` | `config.py` | 生成 Hook 用溫度（預設 `0.7`，高溫度 = 創意） |
| `CRITIC_THRESHOLD` | `config.py` | Critic 通過門檻（預設 8 分） |
| `MAX_DEBATE_RETRIES` | `config.py` | Proposer 最多重試次數（預設 3 回合） |
| `BRAVE_SCIENCE_QUERIES` | `config.py` | 每次爬取最多 Brave 查詢次數（預設 3，節省 API 額度） |
| `BRAVE_RETRY_MAX` | `config.py` | Brave API 重試次數上限（預設 3） |
| `BRAVE_RETRY_BACKOFF` | `config.py` | 重試延遲（秒），預設 `[1, 2, 4]` |
| `DAILYVIEW_URL` | `config.py` | 網路溫度計爬取 URL（舊 API 已失效，改用網頁爬取） |
| `WATTBROTHER_URL` | `config.py` | 瓦特兄弟官網 URL（網頁爬取） |

---

## 🛡️ 免責聲明
本工具僅供靈感發想輔助使用。產出之腳本內容需經人類創作者最終查核與潤飾。使用時請遵守 YouTube 數據 API、Brave Search API 及各科學媒體之服務條款與著作權規範。
