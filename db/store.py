"""
Database Persistence Layer (V3)
定義 6 張核心資料表並提供 CRUD 操作，取代原本 V2 的 JSON 檔案與單純 deduplication
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import DB_PATH


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化資料庫與 6 張表"""
    conn = get_connection()
    cursor = conn.cursor()

    # 原有的去重表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_articles (
            url TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 1. 科學文獻表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS science_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT UNIQUE NOT NULL,
            source TEXT,
            pipeline TEXT,
            mechanism TEXT,
            credibility_score INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. 社群時事表 (YouTube/Dcard等)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS social_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT UNIQUE NOT NULL,
            source TEXT,
            category TEXT,
            is_short BOOLEAN DEFAULT 0,
            mechanism TEXT,
            matched_keywords TEXT,
            thumbnail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add thumbnail column if not exists (migration)
    try:
        cursor.execute("ALTER TABLE social_items ADD COLUMN thumbnail TEXT DEFAULT ''")
    except:
        pass  # Column already exists
    
    # 3. 動漫梗獨立表 (一對多綁定 social_item_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anime_memes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            social_item_id INTEGER,
            anime_name TEXT,
            meme_content TEXT,
            related_topics_json TEXT DEFAULT '[]',
            FOREIGN KEY(social_item_id) REFERENCES social_items(id)
        )
    ''')
    
    # Add related_topics_json column if not exists (migration)
    try:
        cursor.execute("ALTER TABLE anime_memes ADD COLUMN related_topics_json TEXT DEFAULT '[]'")
    except:
        pass  # Column already exists

    # 4. 新聞時事表 (RSS)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trend_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT UNIQUE NOT NULL,
            source TEXT,
            mechanism TEXT,
            heat_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. 生成歷史記錄表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selected_science TEXT,
            selected_trend TEXT,
            selected_social TEXT,
            science_core TEXT,
            mechanism TEXT,
            hooks_json TEXT,
            critic_score INTEGER,
            critic_breakdown_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


# ─── Data Saving (Crawlers) ───

def save_science(articles: list):
    """保存或更新科學文獻"""
    conn = get_connection()
    c = conn.cursor()
    for a in articles:
        c.execute('''
            INSERT INTO science_articles 
            (title, summary, url, source, pipeline, mechanism, credibility_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET 
            mechanism=excluded.mechanism,
            credibility_score=excluded.credibility_score
        ''', (
            a["title"], a.get("summary", ""), a["url"], 
            a.get("source", ""), a.get("pipeline", ""),
            a.get("mechanism", ""), a.get("credibility_score", 1)
        ))
    conn.commit()
    conn.close()


def save_social(items: list):
    """保存社群資料與關聯動漫梗"""
    conn = get_connection()
    c = conn.cursor()
    for item in items:
        # 1. 插入 Social Item
        c.execute('''
            INSERT INTO social_items 
            (title, summary, url, source, category, is_short, mechanism, matched_keywords, thumbnail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET 
            mechanism=excluded.mechanism,
            thumbnail=excluded.thumbnail
        ''', (
            item["title"], item.get("summary", ""), item["url"],
            item.get("source", ""), item.get("category", ""), 
            item.get("is_short", False), item.get("mechanism", ""),
            json.dumps(item.get("matched_keywords", [])),
            item.get("thumbnail", "")
        ))
        
        # Always query by URL to get the correct social_id.
        # lastrowid is unreliable with ON CONFLICT DO UPDATE — it may
        # return the rowid from a *previous* INSERT in this loop when
        # the current row already existed, causing meme data to be
        # saved against the wrong social item.
        c.execute("SELECT id FROM social_items WHERE url=?", (item["url"],))
        row = c.fetchone()
        social_id = row[0] if row else None
        
        if not social_id:
            continue
            
        # 2. 若有新的 Meme 資料，直接新增（保留所有歷史梗解釋）
        if "anime_meme" in item:
            meme = item["anime_meme"]
            related_topics = json.dumps(meme.get("related_topics", []), ensure_ascii=False)
            c.execute('''
                INSERT INTO anime_memes (social_item_id, anime_name, meme_content, related_topics_json)
                VALUES (?, ?, ?, ?)
            ''', (social_id, meme["anime"], meme["meme"], related_topics))
            
    conn.commit()
    conn.close()


def save_trend(items: list):
    """保存新聞時事資料"""
    conn = get_connection()
    c = conn.cursor()
    for item in items:
        c.execute('''
            INSERT INTO trend_items 
            (title, summary, url, source, mechanism, heat_score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET 
            mechanism=excluded.mechanism,
            heat_score=excluded.heat_score
        ''', (
            item["title"], item.get("summary", ""), item["url"],
            item.get("source", ""), item.get("mechanism", ""), 
            item.get("heat_score", 0)
        ))
    conn.commit()
    conn.close()
    
def save_history(payload: dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO generation_history 
        (selected_science, selected_trend, selected_social, science_core, mechanism, hooks_json, critic_score, critic_breakdown_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        payload.get("matched_science_url", ""),
        payload.get("matched_trend_url", ""),
        "", # 未來若支援直接選擇 social 的 URL 可以補上
        payload.get("science_core", ""),
        payload.get("mechanism", ""),
        payload.get("hooks_json", "[]"),
        payload.get("critic_score", 0),
        payload.get("critic_breakdown_json", "{}")
    ))
    conn.commit()
    conn.close()

# ─── Data Fetching (Frontend API) ───

def fetch_latest_science(limit=15):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM science_articles ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    
    c.execute("SELECT MAX(created_at) FROM science_articles")
    last_updated = c.fetchone()[0]
    conn.close()
    
    data = [dict(r) for r in rows]
    return {"data": data, "last_updated": last_updated}

def fetch_latest_social(limit=15):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Left join 只取每個 social_item 最新的一筆 meme（DB 中全部保留）
    c.execute('''
        SELECT s.*, a.anime_name, a.meme_content, a.related_topics_json
        FROM social_items s
        LEFT JOIN anime_memes a ON a.id = (
            SELECT MAX(a2.id) FROM anime_memes a2 WHERE a2.social_item_id = s.id
        )
        ORDER BY s.created_at DESC LIMIT ?
    ''', (limit,))
    
    rows = c.fetchall()
    
    c.execute("SELECT MAX(created_at) FROM social_items")
    last_updated = c.fetchone()[0]
    conn.close()
    
    data = []
    for r in rows:
        d = dict(r)
        d["matched_keywords"] = json.loads(d["matched_keywords"]) if d["matched_keywords"] else []
        d["is_short"] = bool(d["is_short"])
        if d.get("anime_name"):
            related_topics = []
            try:
                related_topics = json.loads(d.get("related_topics_json", "[]") or "[]")
            except:
                pass
            d["anime_meme"] = {
                "anime": d["anime_name"],
                "meme": d["meme_content"],
                "related_topics": related_topics
            }
        data.append(d)
        
    return {"data": data, "last_updated": last_updated}

def fetch_latest_trends(limit=15):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trend_items ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    
    c.execute("SELECT MAX(created_at) FROM trend_items")
    last_updated = c.fetchone()[0]
    conn.close()
    
    data = [dict(r) for r in rows]
    return {"data": data, "last_updated": last_updated}

def fetch_generation_history(limit=50):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM generation_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return {"history": [dict(r) for r in rows]}

# 建立表格
init_db()
