"""
Module 2: Science Retriever — RSS + 動態 Brave 檢索 + 機制抽象化

流程：
  管道 A: RSS (7 國際科學 feed) → feedparser → BeautifulSoup 清洗 → sqlite3 去重
  管道 B: Module 1 關鍵字 → LLM 生成英文 Query → Brave Search → sqlite3 去重
  最後: LLM 提取科學底層機制
"""

import os
import json
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    MODEL_NAME, TEMPERATURE_FILTER,
    SCIENCE_RSS_FEEDS, BRAVE_SCIENCE_QUERIES,
    BRAVE_RETRY_MAX, BRAVE_RETRY_BACKOFF,
    SCIENTIFIC_WHITELIST, SCIENTIFIC_BLACKLIST, CREDIBILITY_SCORES
)
from db.dedup import is_duplicate, mark_processed

# ═══════════════════════════════════════════════
#  輔助判斷：信譽評分 & 過濾 (V3)
# ═══════════════════════════════════════════════

def _is_valid_source(url: str) -> bool:
    """根據白名單或黑名單過濾連結"""
    url_lower = url.lower()
    
    # 若在黑名單，無條件拒絕
    for bl in SCIENTIFIC_BLACKLIST:
        if bl in url_lower:
            return False
            
    # 只抓取可信賴的來源 (嚴格模式可強制要求 Whitlist)
    # 這裡實作成：只要不在黑名單就「勉強」可以，但若在白名單會有較高分數
    return True

def _assign_credibility_score(url: str, source_name: str) -> int:
    """依據設定檔指派星級 (1-3)"""
    url_lower = url.lower()
    for domain, score in CREDIBILITY_SCORES.items():
        if domain != "default" and domain in url_lower:
            return score
    return CREDIBILITY_SCORES.get("default", 1)


# ═══════════════════════════════════════════════
#  管道 A: RSS 科學文獻
# ═══════════════════════════════════════════════

def fetch_science_rss() -> list:
    """
    從 7 個國際科學 RSS feed 抓取文獻。
    自動去重（sqlite3），回傳新文章列表。
    """
    articles = []
    print("正在抓取科學 RSS feeds...")

    for feed_url in SCIENCE_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source = _identify_science_source(feed_url)
            count = 0

            for entry in feed.entries[:20]:  # 每 feed 最多 20 篇
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()

                if not title or not url:
                    continue
                    
                if not _is_valid_source(url):
                    continue

                # sqlite3 去重
                if is_duplicate(url):
                    continue

                raw_summary = entry.get("summary", entry.get("description", ""))
                summary = BeautifulSoup(raw_summary, "html.parser").get_text().strip()

                articles.append({
                    "title": title,
                    "summary": summary[:400] if summary else "",
                    "url": url,
                    "source": source,
                    "pipeline": "RSS",
                    "credibility_score": _assign_credibility_score(url, source)
                })
                mark_processed(url, title, source)
                count += 1

            if count > 0:
                print(f"  {source}: {count} 篇新文章")
        except Exception as e:
            print(f"  ⚠️ RSS 失敗 ({feed_url}): {e}")

    print(f"管道 A 共取得 {len(articles)} 篇新科學文獻")
    return articles


def _identify_science_source(url: str) -> str:
    if "sciencedaily" in url:
        return "ScienceDaily"
    elif "nature.com" in url:
        return "Nature"
    elif "newscientist" in url:
        return "New Scientist"
    elif "phys.org" in url:
        return "Phys.org"
    elif "arstechnica" in url:
        return "Ars Technica"
    return "Science RSS"


# ═══════════════════════════════════════════════
#  管道 B: Brave Search 動態檢索
# ═══════════════════════════════════════════════

def generate_science_queries(trend_keywords: list) -> list:
    """
    使用 LLM 將中文趨勢關鍵字轉換為 3 組英文科學搜尋 Query。
    """
    if not trend_keywords:
        return ["latest science breakthrough 2026", "neuroscience psychology discovery", "technology innovation research"]

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        return ["latest science news", "psychology research", "technology breakthrough"]

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    prompt = PromptTemplate.from_template(
        """你是科學文獻檢索專家。以下是今天台灣的熱門關鍵字與時事：
{keywords}

請生成 {count} 組「英文科學搜尋 Query」，每組 Query 要：
1. 從不同的科學切入點（心理學、神經科學、物理學、社會學、生物學等）
2. 嘗試找到與這些時事「底層機制」相關的科學研究
3. 用學術英文，適合搜尋 Google Scholar / Science News

回傳純 JSON 陣列，不要 markdown：
["query 1", "query 2", "query 3"]"""
    )

    try:
        response = (prompt | llm).invoke({
            "keywords": ", ".join(trend_keywords[:10]),
            "count": BRAVE_SCIENCE_QUERIES,
        })
        content = _parse_json(response.content)
        queries = json.loads(content)
        if isinstance(queries, list):
            print(f"LLM 生成 {len(queries)} 組英文 Query: {queries}")
            return queries[:BRAVE_SCIENCE_QUERIES]
    except Exception as e:
        print(f"⚠️ Query 生成失敗: {e}")

    return ["latest science breakthrough", "psychology neuroscience research", "technology innovation 2026"]


def fetch_brave_science(queries: list) -> list:
    """
    使用 Brave Web Search API 搜尋科學文獻。
    最多 3 次呼叫，含 retry + 去重。
    """
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        print("⚠️ BRAVE_API_KEY 未設定，跳過管道 B")
        return []

    articles = []
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": brave_api_key,
    }
    url = "https://api.search.brave.com/res/v1/web/search"

    for i, query in enumerate(queries[:BRAVE_SCIENCE_QUERIES]):
        print(f"  Brave 搜尋 [{i+1}/{BRAVE_SCIENCE_QUERIES}]: {query}")

        params = {"q": query, "count": 10, "freshness": "pw"}
        data = _brave_request_with_retry(url, headers, params)

        if not data:
            continue

        # 解析結果
        results = []
        if "web" in data and "results" in data["web"]:
            results = data["web"]["results"]
        elif "news" in data and "results" in data["news"]:
            results = data["news"]["results"]

        for item in results:
            item_url = item.get("url", "")
            if not item_url or is_duplicate(item_url):
                continue
                
            if not _is_valid_source(item_url):
                continue

            articles.append({
                "title": item.get("title", ""),
                "summary": item.get("description", ""),
                "url": item_url,
                "source": "Brave Search",
                "pipeline": "BraveSearch",
                "credibility_score": _assign_credibility_score(item_url, "Brave")
            })
            mark_processed(item_url, item.get("title", ""), "Brave")

    print(f"管道 B 共取得 {len(articles)} 篇新科學文獻")
    return articles


def _brave_request_with_retry(url: str, headers: dict, params: dict) -> dict | None:
    """Brave API 請求，含指數退避重試。"""
    for attempt in range(BRAVE_RETRY_MAX):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 429:
                wait = BRAVE_RETRY_BACKOFF[attempt] if attempt < len(BRAVE_RETRY_BACKOFF) else 8
                print(f"    ⚠️ 429 Too Many Requests，等待 {wait}s 後重試...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < BRAVE_RETRY_MAX - 1:
                wait = BRAVE_RETRY_BACKOFF[attempt] if attempt < len(BRAVE_RETRY_BACKOFF) else 4
                print(f"    ⚠️ 請求失敗 ({e})，{wait}s 後重試...")
                time.sleep(wait)
            else:
                print(f"    ❌ Brave API 請求最終失敗: {e}")
    return None


# ═══════════════════════════════════════════════
#  機制抽象化
# ═══════════════════════════════════════════════

def extract_science_mechanisms(articles: list) -> list:
    """
    使用 LLM 為每篇科學文獻提取「科學底層機制」。
    回傳: 帶有 mechanism 欄位的 articles list
    """
    if not articles:
        return []

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        for a in articles:
            a["mechanism"] = "（未設定 API Key）"
        return articles

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    # 把所有文章合併送 LLM 一次處理（省 API 呼叫）
    articles_text = "\n".join([
        f"[{i+1}] 標題: {a['title']}\n    摘要: {a['summary'][:200]}"
        for i, a in enumerate(articles[:15])
    ])

    prompt = PromptTemplate.from_template(
        """你是科學普及專家。以下是科學文獻清單：

{articles_text}

請為每篇文獻提取「科學底層機制」— 這篇研究揭示了什麼底層原理？

好的例子：「多巴胺獎勵回路的短路效應」「蛋白質摺疊錯誤引發的連鎖降解」
壞的例子：「AI 很厲害」「新藥物」（太模糊）

回傳 JSON，不要 markdown：
[
  {{
    "index": 編號,
    "mechanism": "科學底層機制（10-30字）",
    "plain_summary": "一句話白話摘要（讓高中生能懂）"
  }}
]"""
    )

    try:
        print("LLM 提取科學底層機制中...")
        response = (prompt | llm).invoke({"articles_text": articles_text})
        content = _parse_json(response.content)
        mechanisms = json.loads(content)

        for item in mechanisms:
            idx = item.get("index", 1) - 1
            if 0 <= idx < len(articles):
                articles[idx]["mechanism"] = item.get("mechanism", "")
                if item.get("plain_summary"):
                    articles[idx]["summary"] = item["plain_summary"]

        print(f"成功提取 {len(mechanisms)} 篇的科學機制")
    except Exception as e:
        print(f"⚠️ 機制提取失敗: {e}")
        for a in articles:
            if "mechanism" not in a:
                a["mechanism"] = "（提取失敗）"

    return articles


def _parse_json(content) -> str:
    """統一處理 LLM 回傳，提取純 JSON。"""
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
            else:
                parts.append(str(part))
        content = "".join(parts)

    content = str(content).strip()

    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1 and end > start:
        return content[start:end + 1]

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        return content[start:end + 1]

    return content


# ═══════════════════════════════════════════════
#  主函式：完整 Module 2 流程
# ═══════════════════════════════════════════════

def run_science_pipeline() -> list:
    """
    執行完整科學文獻抓取流程。 (V3 解耦版，無需吃 trends 參數)

    回傳: [{title, summary, mechanism, url, source, pipeline, credibility_score}]
    """
    print("\n" + "=" * 50)
    print("Module 2: 科學文獻檢索")
    print("=" * 50)

    # 管道 A: RSS
    rss_articles = fetch_science_rss()

    # 管道 B: Brave 動態 (不提供 keywords, 改要通用的)
    queries = generate_science_queries([])
    brave_articles = fetch_brave_science(queries)

    # 合併
    all_articles = rss_articles + brave_articles
    print(f"\n總計 {len(all_articles)} 篇科學文獻（RSS: {len(rss_articles)}, Brave: {len(brave_articles)}）")

    if not all_articles:
        return []

    # 機制抽象化
    all_articles = extract_science_mechanisms(all_articles)

    print(f"Module 2 完成：{len(all_articles)} 篇科學文獻 with mechanisms")
    
    from db.store import save_science
    if all_articles:
        save_science(all_articles)
        print("✅ 科學文獻已寫入資料庫")
        
    return all_articles


if __name__ == "__main__":
    articles = run_science_pipeline()
    print("\n─── 結果 ───")
    for i, a in enumerate(articles[:5]):
        print(f"\n{i+1}. [{a.get('pipeline', '?')}] {a['title']}")
        print(f"   星級: {'★'*a.get('credibility_score', 1)}{'☆'*(3-a.get('credibility_score', 1))}")
        print(f"   機制: {a.get('mechanism', '無')}")
        print(f"   摘要: {a['summary'][:80]}...")
