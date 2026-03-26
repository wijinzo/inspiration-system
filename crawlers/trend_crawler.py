"""
Module 1: Trend Crawler — 台灣時事新聞 + 機制抽象化

流程（V3 解耦版）：
  1. RSS (LTN, PTS) 拉取台灣即時新聞
  2. LLM 過濾政治/無效內容 + 提取底層運作機制
"""

import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import urllib.parse
from googleapiclient.discovery import build

load_dotenv()

# ─── 將專案根目錄加入 path ───
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    MODEL_NAME, TEMPERATURE_FILTER,
    TAIWAN_NEWS_RSS
)


# ═══════════════════════════════════════════════
#  Step 1: RSS — 台灣新聞
# ═══════════════════════════════════════════════

def fetch_news_rss():
    """
    從 LTN、PTS RSS 抓取台灣即時新聞。
    回傳: [{"title": str, "summary": str, "url": str, "source": str}]
    """
    articles = []
    print("正在抓取台灣新聞 RSS...")

    for feed_url in TAIWAN_NEWS_RSS:
        try:
            feed = feedparser.parse(feed_url)
            source = _identify_source(feed_url)

            for entry in feed.entries[:30]:  # 每個 feed 最多 30 篇
                title = entry.get("title", "").strip()
                if not title:
                    continue

                # 清洗 HTML
                raw_summary = entry.get("summary", entry.get("description", ""))
                summary = BeautifulSoup(raw_summary, "html.parser").get_text().strip()

                url = entry.get("link", "")

                articles.append({
                    "title": title,
                    "summary": summary[:300] if summary else "",
                    "url": url,
                    "source": source,
                })
            print(f"  {source}: 取得 {min(len(feed.entries), 30)} 篇")
        except Exception as e:
            print(f"  ⚠️ RSS 抓取失敗 ({feed_url}): {e}")

    print(f"RSS 共取得 {len(articles)} 篇台灣新聞")
    return articles


def _identify_source(url: str) -> str:
    if "ltn" in url:
        return "自由時報"
    elif "pts" in url:
        return "公視新聞"
    return "其他"

# ═══════════════════════════════════════════════
#  Step 2: LLM 過濾 + 機制抽象化
# ═══════════════════════════════════════════════

def filter_and_extract_mechanisms(articles: list, trends_keywords: list = None) -> list:
    """
    使用 gemini-3-flash-preview：
    1. 過濾純政治謾罵 / 無延伸性八卦
    2. 提取每篇新聞的「底層運作機制」
    3. 回傳 Top 5 最有科普延伸潛力的時事

    回傳: [{title, summary, mechanism, keywords, url, source, heat_score}]
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("請設定 GOOGLE_API_KEY")

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    # 取前 15 篇（含熱度排序）送 LLM 過濾
    candidates = articles[:15]
    articles_text = "\n".join([
        f"[{i+1}] 標題: {a['title']}\n    摘要: {a['summary'][:150]}\n    熱度關鍵字: {', '.join(a.get('matched_keywords', []))}"
        for i, a in enumerate(candidates)
    ])


    prompt = PromptTemplate.from_template(
        """你是一位科普節目的資深企劃。以下是今天的台灣即時新聞：
        
{articles_text}

請執行以下任務：
1. 【過濾】剔除純政治口水戰、無科學延伸價值的八卦（例如：選舉攻防、藝人緋聞、純體育比分）
2. 【篩選】從中挑出最具「科普延伸潛力」的 Top 5 則新聞
3. 【抽象化】為每則新聞提取「底層運作機制」— 不是關鍵字，而是驅動這個事件的底層原理
   好的例子：「資源分配不均導致的系統過載」「群體認知偏差造成的恐慌放大」「反饋迴路失控」
   壞的例子：「少子化」「棒球」「政治」（太表面）

請以 JSON 格式回傳，不要包含 markdown 標記：
[
  {{
    "index": 原始編號,
    "title": "新聞標題",
    "summary": "一句話白話摘要",
    "mechanism": "底層運作機制（10-30字）",
    "keywords": ["關鍵字1", "關鍵字2", "關鍵字3"]
  }}
]

只回傳 JSON，不要加任何其他文字。"""
    )

    chain = prompt | llm

    try:
        print("LLM 過濾中：剔除政治八卦 + 提取底層機制...")
        response = chain.invoke({
            "articles_text": articles_text
        })

        content = _parse_llm_response(response.content)
        results = json.loads(content)

        # 補回原始資料
        for item in results:
            idx = item.get("index", 1) - 1
            if 0 <= idx < len(candidates):
                item["url"] = candidates[idx].get("url", "")
                item["source"] = candidates[idx].get("source", "")

        print(f"LLM 過濾完成：Top {len(results)} 則有科普潛力的時事")
        return results[:5]

    except (json.JSONDecodeError, TypeError) as e:
        print(f"⚠️ LLM 回傳格式異常: {e}")
        # 降級：回傳排名前 5 的原始資料（不含機制）
        return [
            {
                "title": a["title"],
                "summary": a["summary"][:100],
                "mechanism": "（LLM 解析失敗，無機制資料）",
                "url": a.get("url", ""),
                "source": a.get("source", "")
            }
            for a in candidates[:5]
        ]
    except Exception as e:
        print(f"⚠️ LLM 呼叫失敗: {e}")
        return []


def _parse_llm_response(content) -> str:
    """統一處理 Gemini 回傳內容，提取純 JSON 字串。"""
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

    # 從 markdown code block 擷取
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    # 找 JSON 陣列或物件
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1 and end > start:
        content = content[start:end + 1]
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end + 1]

    return content


# ═══════════════════════════════════════════════
#  主函式
# ═══════════════════════════════════════════════

def run_trend_pipeline() -> dict:
    """
    執行完整新聞時事爬取流程。
    回傳: {
        "trends": [Top 5 時事 with mechanisms]
    }
    """
    print("\n" + "=" * 50)
    print("Module 1: 台灣新聞時事爬取")
    print("=" * 50)

    # Step 1: RSS
    news_articles = fetch_news_rss()

    if not news_articles:
        print("⚠️ RSS 無法取得新聞")
        return {
            "trends": [],
            "error": "無法取得台灣新聞 RSS"
        }

    # Step 2: LLM 過濾 + 機制抽象化
    top_trends = filter_and_extract_mechanisms(news_articles)

    result_data = {
        "trends": top_trends
    }

    print(f"\nModule 1 完成：取得 {len(top_trends)} 則有科普潛力的新聞時事")
    
    from db.store import save_trend
    if top_trends:
        save_trend(top_trends)
        print("✅ 新聞時事已寫入資料庫")
        
    return result_data


if __name__ == "__main__":
    result = run_trend_pipeline()
    print("\n─── 最近趨勢結果 ───")
    for i, t in enumerate(result["trends"]):
        print(f"\n{i+1}. {t['title']}")
        print(f"   機制: {t['mechanism']}")
