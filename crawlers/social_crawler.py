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
    MODEL_NAME, TEMPERATURE_FILTER, TARGET_SOCIAL_CHANNELS
)


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
        f"[{i+1}] 頻道:{item['source']} | 種類:{item['category']} | 標題: {item['title']} | 摘要: {item['summary']}"
        for i, item in enumerate(items[:20])
    ])

    prompt = PromptTemplate.from_template(
        """你是一位社群觀察家、動漫達人、也熟悉各種網路迷因。以下是各大 YouTube 頻道最新影片：
        
{items_text}

請篩選出「有潛力與科學結合」的話題，並去除純粹的遊戲實況廢片或是無意義的預告片。

對於每個入選的項目，請務必：
1. 提取「話題梗」：
   - 動漫類(anime)：提取經典名言、場景或現象
   - 迷因類(meme, gaming_meme)：辨識影片背後引用的迷因、梗圖或網路流行語。如果光看標題不確定是什麼梗，請用你的知識去推測這個影片最可能在討論什麼迷因或現象
   - 社群趨勢類(social_trend)：提取核心話題的文化現象
2. 提供 2~3 個「相關話題」(related_topics)：該梗的延伸文化現象、類似的梗、或可結合的科學概念

回傳純 JSON 陣列，不要 markdown：
[
  {{
    "index": 輸入時的編號,
    "anime_meme": {{
      "anime": "作品名 / 迷因名 / 話題名",
      "meme": "對應的名言、梗或現象描述",
      "related_topics": [
        {{"title": "相關話題標題", "description": "一句話描述為什麼相關"}}
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
        for d in extracted_data:
            idx = d.get("index", 1) - 1
            if 0 <= idx < len(items):
                item = items[idx]
                if "anime_meme" in d:
                    item["anime_meme"] = d["anime_meme"]
                results.append(item)
                
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
