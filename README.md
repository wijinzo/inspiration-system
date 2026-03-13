# 🧪 Dual-Track Science Script Automation Engine
### —— 科學先決：人類創作者的靈感工作檯 (Copilot Workbench) ——

這是一個專為 YouTube 短影音創作者設計的「科學-時事」雙軌創意引擎。它不追求全自動盲目產出，而是透過**「科學先決 (Science-First)」**的管線，將硬核科學機制與台灣熱門社群趨勢（動漫、梗、時事）無縫結合，產出具備高含金量與次文化共鳴的影片 Hook。

---

## 🚀 核心特色

- **🔬 科學先決管線**：從頂級科學期刊 (Nature, ScienceDaily) 萃取底層機制，確保內容的權威性與深度。
- **🔥 標靶式時事捕捉**：
  - **YouTube 頻道監控**：支援監控特定頻道（如：木棉花、泛科學），自動提取熱門動漫梗、ACG 次文化元素。
  - **Dcard & PTT 深度抓取**：整合 Brave Search 避開爬蟲封鎖，精準定位年輕世代熱議話題。
- **🤖 多智能體辯論 (Multi-Agent Debate)**：
  - **Proposer Agent**：採用 Chain of Thought (CoT) 邏輯，從「黑色幽默/社畜」、「動漫/遊戲機制」、「懸疑/反常識」多維度生成腳本。
  - **Critic Agent**：執行「抽換詞面測試」，嚴格審查科學與梗的融合度。
- **🎲 靈感吃角子老虎機 (Surprise Me!)**：一鍵隨機碰撞「隨機時事」與「隨機科學」，打破創作瓶頸。

---

## 🛠️ 技術棧 (Tech Stack)

- **後端**: `FastAPI` (Python)
- **前端**: `Vanilla HTML / JS / CSS` (Glassmorphism 設計風格)
- **大語言模型**: `Google Gemini` (透過 LangChain 調度)
- **向量資料庫**: `ChromaDB` (科學機制儲存與匹配)
- **爬蟲技術**: `YouTube Data API v3`, `Brave Search API`, `Feedparser`, `BeautifulSoup`

---

## 📁 檔案結構

```text
 project_root/
 ├── app.py             # FastAPI 主要路由與 API 接口
 ├── config.py          # 集中配置檔（模型參數、RSS、YouTube 頻道）
 ├── .env               # API 金鑰 (GOOGLE, BRAVE, YOUTUBE)
 ├── crawlers/          # 數據採集模組
 │   ├── trend_crawler.py      # 台灣社群趨勢、YouTube、Dcard 爬取
 │   └── science_crawler.py    # 國際科學文獻 RSS 與檢索
 ├── engine/            # 核心邏輯層
 │   └── vector_matching.py    # 向量匹配 + 多智能體辯論引擎
 ├── static/            # UI 靜態檔案
 │   ├── index.html     # 雙欄位互動設計面板
 │   ├── style.css      # 現代感深色模式樣式
 │   └── script.js      # 前端邏輯與動態效果
 └── data/              # 暫存結果與歷史靈感
```

---

## ⚙️ 快速上手

### 1. 安裝環境
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置 API 金鑰
在 `.env` 檔案中填入：
```env
GOOGLE_API_KEY=YOUR_GEMINI_KEY
BRAVE_API_KEY=YOUR_BRAVE_KEY
YOUTUBE_API_KEY=YOUR_YT_KEY
```

### 3. 配置監視頻道 (選配)
至 `config.py` 修改 `TARGET_YOUTUBE_CHANNELS` 加入您想關注的頻道：
```python
TARGET_YOUTUBE_CHANNELS = [
    {"id": "UCgdwtyqBunlRb-i-7PnCssQ", "name": "木棉花", "category": "anime"},
]
```

### 4. 啟動服務
```bash
python app.py
```
啟動後訪問 `http://127.0.0.1:8000` 即可進入儀表板。

---

## 🛡️ 免責聲明
本工具僅供靈感發想輔助使用。產出之腳本內容需經人類創作者最終查核與潤飾。請遵守 YouTube 數據 API 之服務條款。
