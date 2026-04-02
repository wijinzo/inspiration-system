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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    MODEL_NAME, TEMPERATURE_FILTER, TARGET_SOCIAL_CHANNELS,
    DAILYVIEW_API, WATTBROTHER_URL
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

    print(f"正在抓取指定頻道資料 (共 {len(TARGET_SOCIAL_CHANNELS)} 個頻道)...")
    results = []
    try:
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        for channel in TARGET_SOCIAL_CHANNELS:
            cid = channel.get("id")
            name = channel.get("name", cid)
            category = channel.get("category", "social_trend")
            shorts_only = channel.get("fetch_shorts_only", False)
            
            if not cid: continue

            print(f"  正在抓取: {name} ({category}) -> Shorts Only: {shorts_only}")
            
            # 使用 search.list
            kwargs = {
                "part": "snippet",
                "channelId": cid,
                "type": "video",
                "order": "date",  # 改抓最新
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


def fetch_dailyview_trends() -> list:
    """使用 DailyView API 抓取熱門話題"""
    print(f"正在抓取網路溫度計 (DailyView) API...")
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://dailyview.tw/"
    }
    try:
        resp = requests.get(DAILYVIEW_API, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("article", [])
        
        for a in articles[:10]:
            results.append({
                "title": a.get("title", ""),
                "summary": a.get("description", ""),
                "url": a.get("url", ""),
                "source": "網路溫度計",
                "category": "social_trend",
                "is_short": False,
                "matched_keywords": ["網路溫度計", "DailyView"],
                "thumbnail": a.get("image_url", "")
            })
        print(f"  網路溫度計: 取得 {len(results)} 篇熱門話題")
    except Exception as e:
        print(f"⚠️ DailyView API 抓取失敗: {e}")
    return results


def fetch_wattbrother_memes() -> list:
    """從 瓦特兄弟 (WattBrother) 官網抓取遊戲迷因"""
    print(f"正在爬取瓦特兄弟官網 ({WATTBROTHER_URL})...")
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
        for item in items[:10]:
            links = item.select("a")
            if len(links) < 2: continue
            
            title = links[1].get_text(strip=True)
            url = links[1].get("href", "")
            if url and not url.startswith("http"):
                url = "https://wattbrother.com" + url
            
            # 摘要
            summary_div = item.select_one("div:nth-of-type(2)") # 或根據內容查找
            summary = summary_div.get_text(strip=True) if summary_div else ""
            
            # 圖片 (CSS 屬性，可能需要 re 提取)
            # <div class="thumbnail" style="background-image:url('...')">
            img_div = item.select_one("div.thumbnail")
            thumbnail = ""
            if img_div and "background-image" in img_div.get("style", ""):
                style = img_div.get("style", "")
                match = re.search(r"url\('?([^'()]+)'?\)", style)
                if match:
                    thumbnail = match.group(1)
            
            results.append({
                "title": title,
                "summary": summary[:200],
                "url": url,
                "source": "瓦特兄弟 (WEB)",
                "category": "gaming_meme",
                "is_short": False,
                "matched_keywords": ["瓦特兄弟", "遊戲迷因"],
                "thumbnail": thumbnail
            })
        print(f"  瓦特兄弟 (WEB): 取得 {len(results)} 篇遊戲迷因")
    except Exception as e:
        print(f"⚠️ 瓦特兄弟網頁爬取失敗: {e}")
    return results


def filter_and_extract_social_mechanisms(items: list) -> list:
    """使用 LLM 過濾日常廢片，並為有潛力的影片提取「底層機制」與「動漫梗」"""
    if not items:
        return []

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        return items

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    # 批次處理
    items_text = "\n".join([
        f"[ID: {i}] | 頻道:{item['source']} | 標題: {item['title']} | 摘要: {item['summary']}"
        for i, item in enumerate(items[:30])
    ])

    prompt = PromptTemplate.from_template(
        """你是一位熱愛上網的社群觀察家與動漫達人。以下是各大 YouTube 頻道最新影片：
        
{items_text}

請從中篩選出「有潛力的話題或迷因」。
**注意：我不是要你找出科學機制！我要的是你幫我詳細解釋這個梗或話題！**

對於每個入選的項目，請務必：
1. 提取與解釋「話題梗」：
   - 辨識影片背後引用的動漫、迷因、現象或網路流行語。
   - 請根據你的網路知識，**詳細解釋這個梗的來源、意思、以及為什麼好笑/有共鳴**。
   - 如果光看標題不確定，請推測最可能在討論什麼現象，並講述其背景。
2. 提供 2~3 個「延伸話題」(related_topics)：
   - **絕對不要給我科學概念**。我需要的是「這個梗還可以怎麼玩」、「網路上還有哪些類似的迷因或黑話」、「這件事還能延伸出怎樣的笑料」。

⚠️ **最重要的規則**：你必須在每個回傳的物件中包含 "id" 欄位，值為上方列表中的 [ID: N] 的數字 N。
這是用來對應原始項目的唯一方式，不可省略也不可亂填！

回傳格式（嚴格遵守）：
[
  {{
    "id": 0,
    "title": "原始標題（直接從上方列表複製貼上，不要修改）",
    "anime_meme": {{
      "anime": "作品名 / 梗來源",
      "meme": "超詳細的梗解釋（至少50字，把你當下想到的網路笑話或來源講清楚）",
      "related_topics": [
        {{"title": "延伸的搞笑或迷因話題", "description": "一句話說明怎麼玩這個梗"}}
      ]
    }}
  }}
]"""
    )

    try:
        print("LLM 正在分析社群話題梗...")
        response = (prompt | llm).invoke({"items_text": items_text})
        content = _parse_llm_response(response.content)
        extracted_data = json.loads(content)
        
        results = []
        # 標題對應查找表 (小寫化以增加匹配率)
        title_map = {item["title"].lower(): item for item in items}
        used_urls = set()
        
        for d in extracted_data:
            matched_item = None
            
            # 1. 最優先：使用 ID 匹配（最可靠）
            idx = d.get("id", -1)
            if isinstance(idx, int) and 0 <= idx < len(items):
                matched_item = items[idx]
            
            # 2. 次優先：精確標題匹配
            if not matched_item:
                llm_title = d.get("title", "").lower().strip()
                if llm_title:
                    matched_item = title_map.get(llm_title)
                
                    # 3. 局部匹配 (如果 LLM 回傳了部分標題)
                    if not matched_item:
                        best_match = None
                        best_overlap = 0
                        for full_title, item_obj in title_map.items():
                            # 計算雙向包含的字元重疊比例
                            if llm_title in full_title or full_title in llm_title:
                                overlap = min(len(llm_title), len(full_title))
                                if overlap > best_overlap:
                                    best_overlap = overlap
                                    best_match = item_obj
                        matched_item = best_match
            
            if not matched_item:
                print(f"  ⚠️ LLM 回傳的項目無法匹配 (id={idx}, title={d.get('title', '')[:30]})")
                continue
            
            if matched_item["url"] in used_urls:
                continue  # 避免重複
                
            if "anime_meme" in d:
                new_item = matched_item.copy()
                new_item["anime_meme"] = d["anime_meme"]
                results.append(new_item)
                used_urls.add(new_item["url"])
                print(f"  ✅ 匹配成功: [{idx}] {matched_item['title'][:40]}")
                
        print(f"  LLM 回傳 {len(extracted_data)} 筆, 成功匹配 {len(results)} 筆")
        
        # 為了避免過分過濾導致畫面太空，如果 results 太少（< 3），我們原原本本地把剩下的補上
        if len(results) < 3:
            for item in items:
                if item["url"] not in used_urls:
                    results.append(item)
                    if len(results) >= 10:
                        break
                        
        return results
    except Exception as e:
        print(f"⚠️ 社群話題梗分析失敗: {e}")
        
    return items


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
    """執行完整社群抓取流程"""
    print("\n" + "=" * 50)
    print("Module 3: 特定社群與動漫頻道檢索")
    print("=" * 50)
    
    raw_items = fetch_social_channels()
    
    # 新增: 官網爬蟲
    raw_items += fetch_dailyview_trends()
    raw_items += fetch_wattbrother_memes()
    
    # 隨機打亂，以便 LLM 看到不同來源的內容 (否則前 20 則可能全是 YouTube)
    import random
    random.shuffle(raw_items)
    
    if not raw_items:
        return []
        
    processed_items = filter_and_extract_social_mechanisms(raw_items)
    
    print(f"Module 3 完成：取得 {len(processed_items)} 則具潛力的社群/動漫話題")
    
    from db.store import save_social
    if processed_items:
        save_social(processed_items)
        print("✅ 社群與動漫話題已寫入資料庫")
        
    return processed_items


if __name__ == "__main__":
    results = run_social_pipeline()
    for i, r in enumerate(results):
        print(f"\n{i+1}. [{r['source']}] {r['title']} { '(Shorts)' if r.get('is_short') else ''}")
        print(f"   機制: {r.get('mechanism')}")
        if "anime_meme" in r:
            print(f"   動漫梗: {r['anime_meme']['anime']} - {r['anime_meme']['meme']}")
