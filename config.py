"""
集中配置檔：所有可調參數統一管理
"""

# ─── LLM 設定 ───
MODEL_NAME = "gemini-3-flash-preview"
TEMPERATURE_FILTER = 0.1       # 過濾/分析用 (低溫度 = 精確)
TEMPERATURE_CREATIVE = 0.7     # 生成 Hook 用 (高溫度 = 創意)

# ─── Critic 門檻 ───
CRITIC_THRESHOLD = 8           # 評分 ≥ 8 才通過
MAX_DEBATE_RETRIES = 3         # Proposer 最多重寫 3 次

# ═══════════════════════════════════════════════
#  2. 時事來源設定 (Trends / News)
# ═══════════════════════════════════════════════

TAIWAN_NEWS_RSS = [
    "https://news.ltn.com.tw/rss/all.xml",
    "https://news.pts.org.tw/xml/newsfeed.xml"
]

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo=TW"

# ═══════════════════════════════════════════════
#  4. 社群與趨勢來源設定 (Scrapers) (V3)
# ═══════════════════════════════════════════════

# 網路溫度計 API
DAILYVIEW_API = "https://medium.gaii.ai/api/articleMedia?web_id=dailyview&title=_&type=hot&t=1&guess=73"

# 瓦特兄弟官網
WATTBROTHER_URL = "https://wattbrother.com/c/game_meme"

TARGET_SOCIAL_CHANNELS = [
    {
        "id": "UCgdwtyqBunlRb-i-7PnCssQ",  # 木棉花 (Muse Communication)
        "name": "木棉花",
        "category": "anime",
        "fetch_shorts_only": True  # 只抓 Shorts
    },
    {
        "id": "UCwYTuoLZaII23xxAGV2zqcA",
        "name": "搞完君",
        "category": "meme",
        "fetch_shorts_only": False
    }
]

# ─── 科學文獻 RSS ───
SCIENCE_RSS_FEEDS = [
    "https://www.sciencedaily.com/rss/top/science.xml",
    "https://www.sciencedaily.com/rss/top/technology.xml",
    "https://www.sciencedaily.com/rss/strange_offbeat.xml",
    "https://www.nature.com/nature.rss",
    "https://www.science.org/rss/news_current.xml"
]

# ─── 科學過濾機制 (V3 新增) ───
SCIENTIFIC_WHITELIST = [
    "nature.com",
    "science.org",
    "cell.com",
    "thelancet.com",
    "nejm.org",
    "pnas.org",
    "phys.org",
    "sciencedaily.com"
]

SCIENTIFIC_BLACKLIST = [
    "contentfarm.com",
    "dailymail.co.uk",
    "nypost.com",
    "thesun.co.uk",
    "huffpost.com",
    "buzzfeed.com",
    "reddit.com",
    "wikipedia.org"
]

CREDIBILITY_SCORES = {
    "nature.com": 3,
    "science.org": 3,
    "cell.com": 3,
    "sciencedaily.com": 2,
    "phys.org": 2,
    "nationalgeographic.com": 2,
    "default": 1
}

# ─── Brave Search API 預算控制 ───
BRAVE_SCIENCE_QUERIES = 3      # 每次執行最多 3 次科學動態檢索
BRAVE_RETRY_MAX = 3            # 重試次數上限
BRAVE_RETRY_BACKOFF = [1, 2, 4]  # 重試延遲（秒）

import os

# ─── 資料庫 ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "articles.db")

# ─── ChromaDB ───
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
CHROMA_COLLECTION_NAME = "mechanisms"
