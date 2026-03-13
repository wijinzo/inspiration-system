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

# ─── 台灣時事 RSS (已驗證可用) ───
TAIWAN_NEWS_RSS = [
    "https://news.ltn.com.tw/rss/all.xml",          # 自由時報 - 即時全部
    "https://news.pts.org.tw/xml/newsfeed.xml",      # 公視新聞
]

# ─── 指定 YouTube 頻道 (靈感來源) ───
TARGET_YOUTUBE_CHANNELS = [
    # 您可以在此處加入感興趣的頻道 ID 與名稱
    {"id": "UCCvg26UqC_pXNq0uS9L8_5w", "name": "泛科學", "category": "science"},
    {"id": "UCgdwtyqBunlRb-i-7PnCssQ", "name": "木棉花", "category": "anime"},
]

# ─── 科學文獻 RSS ───
SCIENCE_RSS_FEEDS = [
    "https://www.sciencedaily.com/rss/top/science.xml",
    "https://www.sciencedaily.com/rss/top/technology.xml",
    "https://www.sciencedaily.com/rss/strange_offbeat.xml",
    "https://www.nature.com/nature.rss",
    "https://www.newscientist.com/section/news/feed/",
    "https://phys.org/rss-feed/",
    "https://feeds.arstechnica.com/arstechnica/science",
]

# ─── Brave Search API 預算控制 ───
BRAVE_SCIENCE_QUERIES = 3      # 每次執行最多 3 次科學動態檢索
BRAVE_RETRY_MAX = 3            # API 失敗重試次數
BRAVE_RETRY_BACKOFF = [1, 2, 4]  # 重試延遲（秒）

# ─── 資料庫 ───
DB_PATH = "articles.db"

# ─── ChromaDB ───
CHROMA_PERSIST_DIR = "./chroma_db"
CHROMA_COLLECTION_NAME = "mechanisms"

# ─── pytrends ───
PYTRENDS_REGION = "taiwan"     # trending_searches 區域
PYTRENDS_GEO = "TW"           # realtime_trending_searches 區域
PYTRENDS_LANGUAGE = "zh-TW"
