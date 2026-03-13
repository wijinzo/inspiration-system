"""
Module 1: Trend Crawler — 台灣社群趨勢 + 機制抽象化

流程：
  1. pytrends 拉取 Google Trends 台灣熱門關鍵字 + 關聯詞
  2. RSS (LTN, PTS) 拉取台灣即時新聞
  3. 交叉比對：如果新聞標題包含熱門關鍵字 → 標記為「高熱度」
  4. LLM 過濾政治/無效內容 + 提取底層運作機制
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
    TAIWAN_NEWS_RSS, PYTRENDS_REGION, PYTRENDS_GEO,
    BRAVE_RETRY_MAX, BRAVE_RETRY_BACKOFF,
    TARGET_YOUTUBE_CHANNELS
)


# ═══════════════════════════════════════════════
#  Step 1: pytrends — Google Trends 台灣熱門關鍵字
# ═══════════════════════════════════════════════

def fetch_google_trends():
    """
    使用 pytrends 抓取台灣 Google Trends 熱門搜尋詞 + 關聯關鍵字。
    回傳: {"keywords": [...], "related": {...}}
    """
    try:
        from pytrends.request import TrendReq
        print("正在透過 pytrends 抓取 Google Trends 台灣熱門關鍵字...")

        pytrends = TrendReq(hl='zh-TW', tz=480)

        # 每日熱門搜尋
        trending_df = pytrends.trending_searches(pn=PYTRENDS_REGION)
        keywords = trending_df[0].tolist()[:20]  # 取前 20 個
        print(f"  取得 {len(keywords)} 個熱門關鍵字")

        # 為前 5 個關鍵字取得關聯詞
        related = {}
        for kw in keywords[:5]:
            try:
                pytrends.build_payload([kw], geo=PYTRENDS_GEO, timeframe='now 1-d')
                related_queries = pytrends.related_queries()
                if kw in related_queries and related_queries[kw].get("top") is not None:
                    top_related = related_queries[kw]["top"]["query"].tolist()[:5]
                    related[kw] = top_related
                    print(f"  '{kw}' 關聯詞: {top_related[:3]}...")
            except Exception:
                continue

        return {"keywords": keywords, "related": related}

    except ImportError:
        print("⚠️ pytrends 未安裝，跳過 Google Trends")
        return {"keywords": [], "related": {}}
    except Exception as e:
        print(f"⚠️ pytrends 抓取失敗 ({e})，將降級使用 RSS")
        return {"keywords": [], "related": {}}


# ═══════════════════════════════════════════════
#  Step 2: RSS — 台灣新聞
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
#  Step 2.5: 標靶式時事捕捉 (Targeted Trend Crawler)
# ═══════════════════════════════════════════════

def fetch_youtube_trends(keywords: list) -> list:
    """
    透過 YouTube Data API (v3) 搜尋 regionCode="TW" 且近期高觀看數的影片標題。
    """
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        print("⚠️ 未設定 YOUTUBE_API_KEY，跳過 YouTube 趨勢抓取")
        return []

    print(f"正在透過 YouTube API 搜尋關鍵字: {keywords[:3]}...")
    results = []
    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        for kw in keywords[:3]: # 限制搜尋次數避免爆 quota
            request = youtube.search().list(
                part="snippet",
                q=kw,
                regionCode="TW",
                type="video",
                order="viewCount",
                maxResults=3
            )
            response = request.execute()
            for item in response.get("items", []):
                title = item["snippet"]["title"]
                vid = item["id"]["videoId"]
                results.append({
                    "title": title,
                    "summary": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "source": "YouTube",
                    "matched_keywords": [kw]
                })
        print(f"  YouTube 關鍵字階段完成，取得 {len(results)} 筆結果")
    except Exception as e:
        print(f"⚠️ YouTube API 抓取失敗: {e}")
    return results

def fetch_youtube_channel_videos(max_results: int = 5) -> list:
    """
    抓取 config 中指定的特定 YouTube 頻道的高觀看影片。
    """
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key or not TARGET_YOUTUBE_CHANNELS:
        return []

    print(f"正在抓取指定頻道的熱門影片 (共 {len(TARGET_YOUTUBE_CHANNELS)} 個頻道)...")
    results = []
    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        for channel in TARGET_YOUTUBE_CHANNELS:
            cid = channel.get("id")
            name = channel.get("name", cid)
            category = channel.get("category", "general")
            if not cid: continue

            print(f"  正在抓取頻道: {name} ({category})...")
            request = youtube.search().list(
                part="snippet",
                channelId=cid,
                type="video",
                order="viewCount",
                maxResults=max_results
            )
            response = request.execute()
            for item in response.get("items", []):
                results.append({
                    "title": item["snippet"]["title"],
                    "summary": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    "source": f"YouTube ({name})",
                    "category": category,
                    "matched_keywords": ["指定通道"]
                })
    except Exception as e:
        print(f"⚠️ YouTube 頻道抓取失敗: {e}")
    return results

def extract_anime_tropes(social_items: list) -> list:
    """
    針對標記為 'anime' 的社群資料，使用 LLM 提取該動作或時事的「熱門梗」或「機制」。
    """
    anime_items = [item for item in social_items if item.get("category") == "anime"]
    if not anime_items:
        return social_items

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        return social_trends

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    titles_text = "\n".join([f"[{i+1}] {item['title']}" for i, item in enumerate(anime_items)])
    
    prompt = PromptTemplate.from_template(
        """你是一位熱愛動漫、通曉日本與台灣 ACG 次文化的資深宅男。
以下是最近熱門的動漫影片標題：
{titles_text}

請針對每一部動漫，識別出它最核心的「熱門梗 (Meme)」、「特殊機制」或「經典設定」，並思考如何將其「抽象化」成一個可以跟科學結合的邏輯。

例如：
- 《葬送的芙莉蓮》：機制是「跨越長久時間的記憶與孤獨」，可結合「失智症」或「恆星壽命」。
- 《我推的孩子》：機制是「演藝圈的瞳孔謊言」，可結合「視覺心理學」或「虹膜識別」。

回傳 JSON，不要 markdown：
[
  {{
    "index": 編號,
    "trope": "動漫梗/機制 (10-30字)",
    "keywords": ["關鍵字1", "關鍵字2"]
  }}
]"""
    )
    
    try:
        print("LLM 正在分析動漫梗與機制...")
        response = (prompt | llm).invoke({"titles_text": titles_text})
        content = _parse_llm_response(response.content)
        trope_data = json.loads(content)
        
        for item in trope_data:
            idx = item.get("index", 1) - 1
            if 0 <= idx < len(anime_items):
                anime_items[idx]["mechanism"] = item.get("trope", "")
                anime_items[idx]["matched_keywords"] = item.get("keywords", [])
                
    except Exception as e:
        print(f"⚠️ 動漫梗提取失敗: {e}")
        
    return social_items

def _brave_search_social_fallback(query: str, site: str, max_results: int = 3) -> list:
    """
    使用 Brave Search API 作為社群網站 (Dcard/PTT) 的輔助抓取手段。
    """
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        return []

    print(f"  Brave 輔助搜尋 [{site}]: {query}")
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": brave_api_key,
    }
    url = "https://api.search.brave.com/res/v1/web/search"
    full_query = f"site:{site} {query}"
    params = {"q": full_query, "count": max_results, "freshness": "pw"}
    
    results = []
    try:
        # 簡單請求，若要 retry 可參考 science_crawler 的實作
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            web_results = data.get("web", {}).get("results", [])
            for item in web_results:
                results.append({
                    "title": item.get("title", ""),
                    "summary": item.get("description", ""),
                    "url": item.get("url", ""),
                    "source": "Dcard" if "dcard.tw" in site else "PTT",
                    "matched_keywords": [query]
                })
    except Exception as e:
        print(f"  ⚠️ Brave 輔助搜尋失敗: {e}")
    return results

def fetch_dcard_trends(keywords: list) -> list:
    """
    透過 Dcard API 搜尋相關文章 (年輕世代話題)。
    若 API 被擋 (403)，則降級使用 Brave Search 輔助。
    """
    print(f"正在抓取 Dcard 相關趨勢: {keywords[:3]}...")
    results = []
    # 模擬更真實的 UA 避免 403
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.dcard.tw/search"
    }

    for kw in keywords[:3]:
        try:
            # 嘗試直接 API
            encoded_kw = urllib.parse.quote(kw)
            url = f"https://www.dcard.tw/service/api/v2/search/posts?query={encoded_kw}&limit=3"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    results.append({
                        "title": item.get("title", ""),
                        "summary": item.get("excerpt", ""),
                        "url": f"https://www.dcard.tw/f/{item.get('forumAlias', 'all')}/p/{item.get('id', '')}",
                        "source": "Dcard",
                        "matched_keywords": [kw]
                    })
            elif response.status_code == 403:
                print(f"  ⚠️ Dcard API (直接) 被擋 (403)，啟動 Brave 輔助...")
                results.extend(_brave_search_social_fallback(kw, "dcard.tw"))
        except Exception as e:
            print(f"  ⚠️ Dcard API 請求異常: {e}，嘗試 Brave 輔助...")
            results.extend(_brave_search_social_fallback(kw, "dcard.tw"))
            
    print(f"  Dcard 階段完成，取得 {len(results)} 篇趨勢")
    return results

def fetch_ptt_trends(keywords: list) -> list:
    """
    透過 Brave Search 精準搜尋 PTT 爆文 (site:ptt.cc)。
    """
    print(f"正在抓取 PTT 相關趨勢: {keywords[:3]}...")
    results = []
    for kw in keywords[:3]:
        # PTT 難以直接 API 搜尋，直接交給 Brave site:ptt.cc 處理
        results.extend(_brave_search_social_fallback(kw, "ptt.cc"))
    
    print(f"  PTT 階段完成，取得 {len(results)} 篇趨勢")
    return results


# ═══════════════════════════════════════════════
#  Step 3: 交叉比對 — 關鍵字 × 新聞
# ═══════════════════════════════════════════════

def cross_reference(trends_data: dict, news_articles: list) -> list:
    """
    將 Google Trends 關鍵字與 RSS 新聞交叉比對。
    關鍵字出現在新聞標題中 → 標記為高熱度。

    回傳: 排序後的新聞 list，高熱度排前面。
    每篇新聞增加 "matched_keywords" 和 "heat_score" 欄位。
    """
    keywords = trends_data.get("keywords", [])
    related_flat = []
    for kw, related_list in trends_data.get("related", {}).items():
        related_flat.extend(related_list)

    all_keywords = list(set(keywords + related_flat))

    for article in news_articles:
        title = article["title"]
        summary = article.get("summary", "")
        text = title + " " + summary

        matched = []
        for kw in all_keywords:
            if kw in text:
                matched.append(kw)

        article["matched_keywords"] = matched
        article["heat_score"] = len(matched)

    # 高熱度排前面
    news_articles.sort(key=lambda x: x["heat_score"], reverse=True)

    hot_count = sum(1 for a in news_articles if a["heat_score"] > 0)
    print(f"交叉比對：{hot_count}/{len(news_articles)} 篇新聞命中熱門關鍵字")

    return news_articles


# ═══════════════════════════════════════════════
#  Step 4: LLM 過濾 + 機制抽象化
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

    keywords_context = ""
    if trends_keywords:
        keywords_context = f"\n今日 Google Trends 台灣熱門關鍵字：{', '.join(trends_keywords[:10])}"

    prompt = PromptTemplate.from_template(
        """你是一位科普節目的資深企劃。以下是今天的台灣即時新聞：
{keywords_context}

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
            "articles_text": articles_text,
            "keywords_context": keywords_context,
        })

        content = _parse_llm_response(response.content)
        results = json.loads(content)

        # 補回原始資料
        for item in results:
            idx = item.get("index", 1) - 1
            if 0 <= idx < len(candidates):
                item["url"] = candidates[idx].get("url", "")
                item["source"] = candidates[idx].get("source", "")
                item["heat_score"] = candidates[idx].get("heat_score", 0)
                item["matched_keywords"] = candidates[idx].get("matched_keywords", [])

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
                "keywords": a.get("matched_keywords", []),
                "url": a.get("url", ""),
                "source": a.get("source", ""),
                "heat_score": a.get("heat_score", 0),
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
#  主函式：完整 Module 1 + Module 3 流程
# ═══════════════════════════════════════════════

def run_trend_pipeline() -> dict:
    """
    執行完整時事爬取流程。
    回傳: {
        "trends": [Top 5 時事 with mechanisms],
        "all_keywords": [所有熱門關鍵字],
        "google_trends": {raw pytrends data},
        "social_trends": [YouTube, Dcard, PTT 綜合結果]
    }
    """
    print("\n" + "=" * 50)
    print("Module 1 & 3: 台灣社群趨勢爬取")
    print("=" * 50)

    # Step 1: pytrends
    trends_data = fetch_google_trends()

    # Step 2: RSS
    news_articles = fetch_news_rss()

    if not news_articles:
        print("⚠️ RSS 無法取得新聞，嘗試僅用 Google Trends 關鍵字")
        return {
            "trends": [],
            "all_keywords": trends_data.get("keywords", []),
            "google_trends": trends_data,
            "social_trends": [],
            "error": "無法取得台灣新聞 RSS"
        }

    # Step 3: 交叉比對
    ranked_articles = cross_reference(trends_data, news_articles)

    # Step 4: LLM 過濾 + 機制抽象化
    top_trends = filter_and_extract_mechanisms(
        ranked_articles,
        trends_keywords=trends_data.get("keywords", [])
    )

    # 彙整所有關鍵字（pytrends + LLM 提取）
    all_keywords = list(set(
        trends_data.get("keywords", []) +
        [kw for t in top_trends for kw in t.get("keywords", [])]
    ))
    
    # Module 3: 標靶式時事捕捉
    print("\n" + "-" * 50)
    print("Module 3: 啟動標靶式社群捕捉 (YouTube, Dcard, PTT)")
    print("-" * 50)
    
    social_trends = []
    # 1. 關鍵字標靶抓取
    target_kws = all_keywords[:5] 
    if target_kws:
        yt_results = fetch_youtube_trends(target_kws)
        dcard_results = fetch_dcard_trends(target_kws)
        ptt_results = fetch_ptt_trends(target_kws)
        
        social_trends.extend(yt_results)
        social_trends.extend(dcard_results)
        social_trends.extend(ptt_results)
    
    # 2. 指定頻道抓取
    yt_channel_results = fetch_youtube_channel_videos()
    social_trends.extend(yt_channel_results)
    
    # 3. 針對動漫類別進行梗與機制提取
    social_trends = extract_anime_tropes(social_trends)

    if not social_trends:
        print("⚠️ 未抓取到任何社群時事資料")

    result_data = {
        "trends": top_trends,
        "all_keywords": all_keywords,
        "google_trends": trends_data,
        "social_trends": social_trends
    }
    
    # 儲存到本地
    save_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "trending_results.json")
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 趨勢資料已儲存至: {save_path}")
    except Exception as e:
        print(f"\n⚠️ 趨勢資料儲存失敗: {e}")

    print(f"\nModule 1+3 完成：{len(top_trends)} 則時事 + {len(social_trends)} 則社群貼文")
    return result_data


if __name__ == "__main__":
    result = run_trend_pipeline()
    print("\n─── 最近趨勢結果 ───")
    for i, t in enumerate(result["trends"]):
        print(f"\n{i+1}. {t['title']}")
        print(f"   機制: {t['mechanism']}")
        print(f"   關鍵字: {t.get('keywords', [])}")
    
    print("\n─── 社群捕捉結果 (YouTube/Dcard/PTT) ───")
    for i, s in enumerate(result["social_trends"][:5]): # 只印前 5 筆預覽
        print(f"\n{i+1}. [{s['source']}] {s['title']}")
        print(f"   連結: {s['url']}")
        print(f"   匹配關鍵字: {s.get('matched_keywords', [])}")

    print(f"\n總結: {len(result['social_trends'])} 筆社群資料已落檔。")
