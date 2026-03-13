"""
SQLite3 去重模組：追蹤已處理過的文章 URL，避免重複處理。
"""
import sqlite3
from datetime import datetime
from config import DB_PATH


def init_db():
    """建立去重資料表（若不存在）。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_articles (
            url TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            processed_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def is_duplicate(url: str) -> bool:
    """檢查該 URL 是否已經處理過。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_articles WHERE url = ?", (url,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def mark_processed(url: str, title: str = "", source: str = ""):
    """將 URL 標記為已處理。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO processed_articles (url, title, source, processed_at) VALUES (?, ?, ?, ?)",
        (url, title, source, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_processed_count() -> int:
    """取得已處理文章數量。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM processed_articles")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# 模組載入時自動初始化資料庫
init_db()
