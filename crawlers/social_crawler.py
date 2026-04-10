"""
Module 3: Social/Anime Crawler
負責特定社群頻道 (木棉花 Shorts, 瓦特兄弟, 日常溫度計等) 的資料抓取
"""

import os
import json
import re
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

import sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    MODEL_NAME, TEMPERATURE_FILTER, TARGET_SOCIAL_CHANNELS,
    DAILYVIEW_URL, WATTBROTHER_URL
)
import requests
from bs4 import BeautifulSoup


def _clean_youtube_description(text: str) -> str:
    """清理 YouTube 說明欄位的贊助、社群連結等雜訊"""
    if not text:
        return ""
    
    # 移除常見的贊助、訂閱、社群連結黑名單字眼之後的內容
    stop_markers = [
        "加入會員", "訂閱頻道", "Instagram", "Facebook", "TikTok", "Twitch",
        "合作邀約", "贊助", "Bilibili", "Twitter", "追蹤我們", "相關連結"
    ]
    
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        if any(marker in line for marker in stop_markers):
            continue  # 跳過這些行
        # 去除 url
        line = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', line)
        line = line.strip()
        if line:
            cleaned_lines.append(line)
            
    # 只取前 4 行當摘要，避免太長
    return " ".join(cleaned_lines[:4])


def fetch_social_channels() -> list:
    """抓取 config.py 中設定的指定頻道影片"""
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key or not TARGET_SOCIAL_CHANNELS:
        print("⚠️ 缺少 YOUTUBE_API_KEY 或無目標社群")
        return []

    print(f"Fetching from target channels ({len(TARGET_SOCIAL_CHANNELS)} channels)...")
    results = []
    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        for channel in TARGET_SOCIAL_CHANNELS:
            cid = channel.get("id")
            name = channel.get("name", cid)
            category = channel.get("category", "social_trend")
            shorts_only = channel.get("fetch_shorts_only", False)
            
            if not cid: continue

            print(f"  Fetching: {name} ({category}) -> Shorts Only: {shorts_only}")
            
            # 1 週內的日期過濾 (RFC 3339 格式)
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            
            # 使用 search.list
            kwargs = {
                "part": "snippet",
                "channelId": cid,
                "type": "video",
                "order": "date",
                "publishedAfter": cutoff_date,
                "maxResults": 15
            }
            
            response = youtube.search().list(**kwargs).execute()
            
            items_found = 0
            for item in response.get("items", []):
                if items_found >= 5: # 每個頻道最多取 5 個有效結果
                    break
                    
                vid = item['id']['videoId']
                title = item["snippet"]["title"]
                
                # Check for Shorts if required
                is_short = False
                if shorts_only:
                    # 判斷是否為 Shorts 的一個簡單方法：
                    # 1. 標題有 #shorts
                    if "#shorts" in title.lower():
                        is_short = True
                    else:
                        # 2. 檢查長度是否小於 60 秒 (需要額外呼叫 videos API，為了省 Quota 我們直接跳過如果沒有 #shorts)
                        # 在這裡偷懶，若規定只抓 shorts 且標題沒有 #shorts，我們還是放行，但標記為 False
                        pass
                        
                    # 木棉花策略: 嚴格過濾非 Shorts 的長影片片頭
                    if "Muse木棉花" in name and not is_short and "第" in title and "話" in title:
                        continue # 跳過正片
                
                desc = _clean_youtube_description(item["snippet"]["description"])
                
                # Capture thumbnail
                thumbnails = item["snippet"].get("thumbnails", {})
                thumbnail_url = (thumbnails.get("medium") or thumbnails.get("high") or thumbnails.get("default") or {}).get("url", "")
                
                results.append({
                    "title": title,
                    "summary": desc[:150],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "source": f"YouTube ({name})",
                    "category": category,
                    "is_short": is_short,
                    "matched_keywords": [name],
                    "thumbnail": thumbnail_url
                })
                items_found += 1
                
    except Exception as e:
        print(f"⚠️ YouTube 頻道抓取失敗: {e}")
        
    return results


def _fetch_dailyview_article_content(url: str) -> str:
    """進入網路溫度計文章詳情頁，提取完整正文內容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        content_div = soup.select_one('article, .content, .entry-content, .post-content, main')
        if content_div:
            # 濾除選單、頁尾等雜訊
            for nav in content_div.select('nav, footer, .sidebar, script, style'):
                nav.decompose()
            text = content_div.get_text('\n', strip=True)
            return text[:1000] if text else ""
        
        # fallback
        paragraphs = soup.select('p')
        text = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 5])
        return text[:1000] if text else ""
    except Exception as e:
        print(f"  ⚠️ 網路溫度計詳情抓取失敗 ({url}): {e}")
        return ""


def fetch_dailyview_trends() -> list:
    """從 DailyView 網頁直接爬取熱門話題（舊 API 已失效）"""
    print(f"Scraping DailyView ({DAILYVIEW_URL})...")
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9"
    }
    try:
        resp = requests.get(DAILYVIEW_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # DailyView 熱門話題頁結構：每篇文章是一個 <a> 連結，
        # 包含分類標籤和標題文字，href 格式為 /popular/detail/{id}
        articles = soup.select('a[href*="/popular/detail/"]')
        
        seen_urls = set()
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for a in articles:
            # 獲取容器文字以搜尋日期 (格式如 2024.04.10)
            parent_text = a.parent.get_text(" ", strip=True)
            date_match = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", parent_text)
            
            if date_match:
                item_date = datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
                if item_date < cutoff_date:
                    print(f"  [Skip] Stopping: Date exceeds 7 days ({item_date.strftime('%Y-%m-%d')})")
                    break

            href = a.get("href", "")
            if not href or "/popular/detail/" not in href:
                continue
            
            url = href if href.startswith("http") else f"https://dailyview.tw{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # 提取標題：取 <a> 內的文字，排除分類標籤
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            
            # 嘗試提取分類標籤（如「生活」「時事」等）
            category_tag = ""
            for child in a.children:
                text = child.string if hasattr(child, 'string') and child.string else ""
                if text and len(text) <= 4:
                    category_tag = text.strip()
                    break
            
            # 清理標題（移除開頭的分類標籤）
            if category_tag and title.startswith(category_tag):
                title = title[len(category_tag):].strip()
            
            # 嘗試提取摘要（從 img 的 alt 或附近文字）
            summary = ""
            img = a.select_one("img")
            if img:
                summary = img.get("alt", "")
            
            # 嘗試提取圖片
            thumbnail = ""
            if img:
                raw_src = img.get("src", "") or img.get("data-src", "")
                if raw_src:
                    if raw_src.startswith("//"):
                        thumbnail = "https:" + raw_src
                    elif raw_src.startswith("/"):
                        thumbnail = "https://dailyview.tw" + raw_src
                    else:
                        thumbnail = raw_src
            
            # Enter detail page to get full content for LLM Analysis
            print(f"  [Detail] Reading DailyView content: {title[:30]}...")
            full_content = _fetch_dailyview_article_content(url)
            if full_content:
                summary = full_content
            
            results.append({
                "title": title,
                "summary": summary[:1000] if summary else "",
                "url": url,
                "source": "DailyView",
                "category": "social_trend",
                "is_short": False,
                "matched_keywords": ["DailyView"],
                "thumbnail": thumbnail
            })
            
            if len(results) >= 10:
                break
                
        print(f"  DailyView (WEB): Found {len(results)} trending topics")
    except Exception as e:
        print(f"⚠️ DailyView 網頁爬取失敗: {e}")
    return results


def _fetch_wattbrother_article_content(url: str) -> str:
    """進入瓦特兄弟文章詳情頁，提取完整正文內容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 文章正文結構：主要內容在 <article> 或文章主體區域
        # 嘗試多種選擇器以確保抓取成功
        content_parts = []
        
        # 方法 1: 尋找文章主體的 <p> 和 <h2>/<h3> 標題
        # 排除導航、側邊欄、頁尾等非正文區域
        for selector in ['article', '.post-content', '.entry-content', '.article-content']:
            article_el = soup.select_one(selector)
            if article_el:
                for el in article_el.select('p, h2, h3, li'):
                    text = el.get_text(strip=True)
                    if text and len(text) > 5:
                        content_parts.append(text)
                break
        
        # 方法 2: 若方法 1 失敗，直接取所有 <p> 標籤（排除導航區域）
        if not content_parts:
            # 移除導航和頁尾區域
            for nav in soup.select('nav, footer, header, .sidebar, .menu'):
                nav.decompose()
            
            for p in soup.select('p'):
                text = p.get_text(strip=True)
                # 過濾過短或是聯絡/廣告資訊
                if text and len(text) > 10:
                    skip_markers = ['邀約', '來信', '@gmail', '追蹤我們', '版權', 'Copyright']
                    if not any(m in text for m in skip_markers):
                        content_parts.append(text)
        
        full_text = '\n'.join(content_parts)
        return full_text[:800] if full_text else ""
        
    except Exception as e:
        print(f"  [Error] Detail fetch failed ({url}): {e}")
        return ""


def fetch_wattbrother_memes() -> list:
    """Scrape gaming memes from WattBrother and fetch full content"""
    print(f"Scraping WattBrother ({WATTBROTHER_URL})...")
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(WATTBROTHER_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 根據瀏覽器 subagent 提供的結構: div.item
        items = soup.select("div.item")
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for item in items[:20]: # 擴大掃描範圍以補齊一週資料
            # 解析日期 (格式如 2024-04-10)
            item_text = item.get_text(" ", strip=True)
            date_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", item_text)
            
            if date_match:
                item_date = datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
                if item_date < cutoff_date:
                    print(f"  [Skip] Stopping: WattBrother date exceeds 7 days ({item_date.strftime('%Y-%m-%d')})")
                    break

            links = item.select("a")
            if len(links) < 2: continue
            
            title = links[1].get_text(strip=True)
            url = links[1].get("href", "")
            if url.startswith("//"):
                url = "https:" + url
            elif url and not url.startswith("http"):
                url = "https://wattbrother.com" + (url if url.startswith("/") else "/" + url)
            
            # 摘要：先從列表頁取得簡短摘要
            summary_div = item.select_one("div:nth-of-type(2)")
            summary = summary_div.get_text(strip=True) if summary_div else ""
            
            # Enter article detail for full explanation
            if url:
                print(f"  [Detail] Reading WattBrother content: {title[:30]}...")
                full_content = _fetch_wattbrother_article_content(url)
                if full_content:
                    summary = full_content  # 用完整內容取代簡短摘要
            
            # 圖片 (CSS 屬性，可能需要 re 提取)
            img_div = item.select_one("div.thumbnail")
            thumbnail = ""
            if img_div and "background-image" in img_div.get("style", ""):
                style = img_div.get("style", "")
                match = re.search(r"url\('?([^'()]+)'?\)", style)
                if match:
                    raw_src = match.group(1)
                    if raw_src.startswith("//"):
                        thumbnail = "https:" + raw_src
                    elif raw_src.startswith("/"):
                        thumbnail = "https://wattbrother.com" + raw_src
                    else:
                        thumbnail = raw_src
            
            results.append({
                "title": title,
                "summary": summary[:500],
                "url": url,
                "source": "WattBrother (WEB)",
                "category": "gaming_meme",
                "is_short": False,
                "matched_keywords": ["WattBrother", "Gaming Meme"],
                "thumbnail": thumbnail
            })
        print(f"  WattBrother (WEB): Found {len(results)} memes with full content")
    except Exception as e:
        print(f" [Error] WattBrother scrape failed: {e}")
    return results


def filter_and_extract_social_mechanisms(items: list) -> tuple[list, list]:
    """使用 LLM 過濾，並分類為「動漫迷因」還是「一般新聞」，廣告廢片直接拋棄。"""
    if not items:
        return [], []

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        return items, []

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    # 批次處理
    items_text = "\n".join([
        f"[ID: {i}] | 頻道:{item['source']} | 標題: {item['title']} | 摘要: {item['summary']}"
        for i, item in enumerate(items[:30])
    ])

    prompt = PromptTemplate.from_template(
        """你是一位熱愛上網、擅長分析網路流行趨勢、現象、動漫、迷因與話題的社會學家。以下是各種來源的最新熱門文章或影片：
        
{items_text}

請從中篩選並分類出「**符合人類興趣的話題**」。
🚨 **過濾規則**：
1. 如果內容只是「純粹的廣告代言、無聊的商業宣傳」，請**直接捨棄不要留**。
2. 如果內容是「一般的新聞時事（例如：政治、財經發佈、在地社會新聞）」，請保留並分類為 `news`。
3. 如果是「網路迷因、有趣的時事現象（例如：爆紅流行語）、動漫梗或是能引起強烈共鳴的好笑話題」，請保留並分類為 `meme`。

對於 `meme` 分類的項目，你需要額外填寫 "anime_meme" 區塊：
1. 提取與解釋「話題梗」：詳細解釋這個現象的涵義、為何爆紅、網友的反應。
2. 提供 2~3 個「延伸話題」(related_topics)：這件事還能延伸出怎樣的好笑觀點。

這對於 `news` 分類則不需要填寫 "anime_meme"。

⚠️ **最重要的規則**：必須在每個回傳物件中包含 "id" 欄位，值為上方列表中的 [ID: N] 數字 N。

回傳格式（嚴格遵守）：
[
  {{
    "id": 0,
    "classification": "meme", // 或 "news"
    "title": "原始標題",
    "anime_meme": {{
      "anime": "話題類型 / 梗來源",
      "meme": "超詳細的話題/迷因解釋（至少50字）",
      "related_topics": [
        {{"title": "延伸話題", "description": "一句話說明"}}
      ]
    }} // 如果 classification 是 news，此欄位可以直接省略或為 null
  }}
]"""
    )

    try:
        print("LLM is analyzing and classifying social/meme topics...")
        response = (prompt | llm).invoke({"items_text": items_text})
        content = _parse_llm_response(response.content)
        extracted_data = json.loads(content)
        
        social_results = []
        trend_results = []
        
        # Title mapping table
        title_map = {item["title"].lower(): item for item in items}
        used_urls = set()
        
        for d in extracted_data:
            matched_item = None
            
            # ID Match
            idx = d.get("id", -1)
            if isinstance(idx, int) and 0 <= idx < len(items):
                matched_item = items[idx]
            
            # Title Match
            if not matched_item:
                llm_title = d.get("title", "").lower().strip()
                if llm_title:
                    matched_item = title_map.get(llm_title)
                    if not matched_item:
                        for full_title, item_obj in title_map.items():
                            if llm_title in full_title or full_title in llm_title:
                                matched_item = item_obj
                                break
            
            if not matched_item or matched_item["url"] in used_urls:
                continue
                
            new_item = matched_item.copy()
            used_urls.add(new_item["url"])
            
            cls_type = d.get("classification", "meme")
            
            if cls_type == "news":
                # Rewrite category for trend_items
                new_item["category"] = "social_news" 
                trend_results.append(new_item)
                print(f"  [News] Classification: [{idx}] {matched_item['title'][:40]}")
            else:
                if "anime_meme" in d and d["anime_meme"]:
                    new_item["anime_meme"] = d["anime_meme"]
                social_results.append(new_item)
                print(f"  [Meme] Classification: [{idx}] {matched_item['title'][:40]}")
                
        print(f"  LLM returned {len(extracted_data)} items, successfully matched {len(social_results) + len(trend_results)} items")
                        
        return social_results, trend_results
    except Exception as e:
        print(f"[Error] Social analysis failed: {e}")
        
    return items, []


def _parse_llm_response(content) -> str:
    """簡單的 JSON 提取工具"""
    if isinstance(content, list):
        content = "".join([str(p.get("text", p)) if isinstance(p, dict) else str(p) for p in content])
    content = str(content).strip()
    
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
        
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1 and end > start:
        return content[start:end+1]
    return content


def run_social_pipeline() -> list:
    """Execute complete social crawl pipeline"""
    print("\n" + "=" * 50)
    print("Module 3: Social & Anime Channel Analysis")
    print("=" * 50)
    
    raw_items = fetch_social_channels()
    raw_items += fetch_wattbrother_memes()
    raw_items += fetch_dailyview_trends()
    
    # Shuffle for source diversity
    import random
    random.shuffle(raw_items)
    
    social_items = []
    trend_items = []
    if raw_items:
        social_items, trend_items = filter_and_extract_social_mechanisms(raw_items)
        
    print(f"Module 3 Complete: Collected {len(social_items)} memes, Routed {len(trend_items)} news items")
    
    from db.store import save_social, save_trend
    if social_items:
        stats = save_social(social_items)
        print(f"[OK] Social/Anime topics written to database (Added {stats['inserted']} / Updated {stats['updated']})")
        
    if trend_items:
        stats = save_trend(trend_items)
        print(f"[OK] News items routed to trend database (Added {stats['inserted']} / Updated {stats['updated']})")
        
    return social_items + trend_items


if __name__ == "__main__":
    results = run_social_pipeline()
    for i, r in enumerate(results):
        print(f"\n{i+1}. [{r['source']}] {r['title']} { '(Shorts)' if r.get('is_short') else ''}")
        print(f"   機制: {r.get('mechanism')}")
        if "anime_meme" in r:
            print(f"   動漫梗: {r['anime_meme']['anime']} - {r['anime_meme']['meme']}")
