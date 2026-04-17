"""
Module 4: Generation Pipeline (V3 Science-First Architecture)

流程：
1. 確認 Science Core (從前端傳入 locked item，或從 DB 自動挑最新、Credit 最高的)
2. 將 Science Core 投入 ChromaDB (若需要)，或者透過字面 keyword 配對 Social / Trend
3. Multi-Agent Debate: 
   - Proposer (負責生成 Science-First 的深度內容)
   - Critic (負責審查 Science 是否為裝飾品、是否包含 3 種 Hook)
4. 輸出前端所需要的結構化 JSON
"""

import os
import json
import chromadb
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    MODEL_NAME, TEMPERATURE_CREATIVE, TEMPERATURE_FILTER,
    CRITIC_THRESHOLD, MAX_DEBATE_RETRIES, CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME
)
from db import store


# ─── V3 核心生成管線 ───

def run_v3_pipeline(locked_items: dict = None) -> dict:
    """
    執行 V3 Science-First 生成流程。
    locked_items: {"science_url": "...", "trend_url": "...", "social_url": "..."}
    """
    print("\n" + "=" * 50)
    print("Module 4: V3 Science-First 生成引擎")
    print("=" * 50)
    
    # 1. 取得目標資料 (Science, Trend, Social)
    target_data = _gather_target_data(locked_items or {})
    science_item = target_data.get("science")
    trend_item = target_data.get("trend")
    social_item = target_data.get("social")
    
    if not science_item:
        return {"error": "缺乏科學文獻作為核心，V3 引擎無法執行。"}
        
    print(f"* [Science Core]: {science_item['title']} (Credibility: {science_item.get('credibility_score', 1)})")
    
    # 2. 準備給 LLM 的 Context
    context_str = _build_context_string(science_item, trend_item, social_item)
    
    # 3. 執行 Proposer-Critic Debate 迴圈
    proposer_llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_CREATIVE)
    critic_llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)
    
    current_hook_json = ""
    current_score = 0
    breakdown = {}
    critic_comment = ""
    attempts = 0
    
    while attempts < MAX_DEBATE_RETRIES:
        attempts += 1
        print(f"\n>> [Debate] 第 {attempts} 回合...")
        
        # Proposer 生成
        try:
            current_hook_json = _run_proposer(proposer_llm, context_str, science_item['mechanism'])
        except Exception as e:
            print(f"!! Proposer 生成失敗: {e}")
            break
            
        # Critic 審查
        try:
            critic_result = _run_critic(critic_llm, current_hook_json, science_item['mechanism'])
            current_score = critic_result.get("total_score", 0)
            breakdown = critic_result.get("breakdown", {})
            critic_comment = critic_result.get("comment", "")
            
            print(f"   => Critic 評分: {current_score}/10")
            print(f"      - Science-First: {breakdown.get('science_first_score', 0)}/4")
            print(f"      - Hook Appeal: {breakdown.get('hook_appeal_score', 0)}/3")
            print(f"      - Format: {breakdown.get('format_score', 0)}/3")
            
            if current_score >= CRITIC_THRESHOLD:
                print("   [OK] 成功通過審查標準！")
                break
            else:
                print(f"   [FAIL] 分數不足。評論: {critic_result.get('comment', '無')}")
                # 將 Comment 放入下一輪 (這裡簡化處理，直接重新生成，實際可將 comment 餵回 proposer)
        except Exception as e:
            print(f"!! Critic 審查失敗: {e}")
            break

    # 解析 최종 JSON
    hooks = ["生成失敗", "生成失敗", "生成失敗"]
    science_core_text = "無核心分析"
    reasoning_text = "無企劃屬性邏輯"
    try:
        if current_hook_json:
            parsed = json.loads(current_hook_json)
            science_core_text = parsed.get("science_core", science_core_text)
            reasoning_text = parsed.get("reasoning", reasoning_text)
            hooks = parsed.get("hooks", hooks)
    except:
        pass
        
    return {
        "passed": current_score >= CRITIC_THRESHOLD,
        "critic_score": current_score,
        "critic_breakdown": breakdown,
        "critic_comment": critic_comment,
        "science_core": science_core_text,
        "reasoning": reasoning_text,
        "hooks": hooks,
        "mechanism": science_item.get("mechanism", ""),
        "matched_science": science_item,
        "matched_trend": trend_item,
        "matched_social": social_item,
        "attempts": attempts
    }


def _gather_target_data(locked_items: dict) -> dict:
    """從資料庫獲取目標項目（如果 locked 則抓精準目標，否則自動挑選最好的）"""
    result = {"science": None, "trend": None, "social": None}
    
    science_db = store.fetch_latest_science().get("data", [])
    if locked_items.get("science_url"):
        result["science"] = next((item for item in science_db if item["url"] == locked_items["science_url"]), None)
    elif science_db:
        # 預設：選分數最高、最新的
        result["science"] = sorted(science_db, key=lambda x: x.get('credibility_score', 1), reverse=True)[0]
        
    trend_db = store.fetch_latest_trends().get("data", [])
    if locked_items.get("trend_url"):
        result["trend"] = next((item for item in trend_db if item["url"] == locked_items["trend_url"]), None)
        
    social_db = store.fetch_latest_social().get("data", [])
    if locked_items.get("social_url"):
        result["social"] = next((item for item in social_db if item["url"] == locked_items["social_url"]), None)
        
    return result


def _build_context_string(science, trend, social) -> str:
    ctx = f"【科學核心 (必須為主體)】\n標題：{science['title']}\n摘要：{science['summary'][:300]}\n機制：{science.get('mechanism', '')}\n\n"
    
    if trend:
        ctx += f"【時事包裝 (用於降低門檻/找共鳴)】\n標題：{trend['title']}\n摘要：{trend['summary'][:200]}\n\n"
        
    if social:
        anime_meme = social.get('anime_meme', {})
        meme_str = f"\n動漫梗/迷因：{anime_meme.get('anime', '')} - {anime_meme.get('meme', '')}" if anime_meme else ""
        ctx += f"【社群/動漫包裝 (用於提供獵奇感)】\n標題：{social['title']}\n摘要：{social['summary'][:200]}{meme_str}\n"
        
    return ctx

def _run_proposer(llm, context_str: str, core_mechanism: str) -> str:
    prompt = PromptTemplate.from_template(
        """你是 YouTube 百萬科普及動漫解說頻道的主筆。我們現在採用「Science-First, Hook-Last」架構。
        
輸入素材：
{context_str}

核心機制（絕對不能偏題）：{core_mechanism}

任務要求：
1. 先寫出一段紮實的【科學核心分析】(Science Core) 約 300 字，必須解釋 {core_mechanism} 到底是如何運作的，不能只有空殼。
2. 基於這套科學邏輯，產出三個對應不同受眾的【Hook 引入視角】（純腦洞及有吸引力的腳本開場口白，約1000字）。
   - Hook 1 (Humor/Daily): 結合時事或生活日常的有趣幽默視角
   - Hook 2 (Anime/Meme): 結合動漫梗或網路迷因的獨特視角
   - Hook 3 (Mystery/Curiosity): 提供強烈反差感、懸疑感的視角
3. 【企劃底層邏輯】(Reasoning) 約 100 字，說明你為何選擇這三個 Hook，以及科學如何轉化為內容的思考。

以精確的 JSON 格式回傳，絕對不要包含任何 Markdown 標記，只需要以下結構：
{{
  "science_core": "科學核心分析的內容...",
  "reasoning": "企劃底層邏輯的內容...",
  "hooks": [
    "【生活幽默】Hook 1 的開場白...",
    "【動漫迷因】Hook 2 的開場白...",
    "【獵奇懸疑】Hook 3 的開場白..."
  ]
}}"""
    )
    
    response = (prompt | llm).invoke({"context_str": context_str, "core_mechanism": core_mechanism})
    raw = _extract_text(response.content)
    return _parse_json(raw)


def _run_critic(llm, generated_json_str: str, core_mechanism: str) -> dict:
    prompt = PromptTemplate.from_template(
        """你是 YouTube 科普及內容主編。你要審查 Proposer 撰寫的腳本初稿。
這是他回傳的內容：
{generated_json_str}

本次的科學底層機制是：{core_mechanism}

請執行「替換測試 (Substitution Test)」與評分迴圈：
1. 科學先決 (0-4 分)：Science Core 是否紮實？如果把科學術語換成魔法，文章是否瞬間不合理？如果一樣合理 = 0 分。
2. Hook 吸引力 (0-3 分)：3 個 Hook 是否分別達到了幽默、迷因、懸疑的效果？每個HOOK有達成加一分
3. 格式正確性 (0-3 分)：是否有 3 個 Hook？

請嚴格且客觀地審查，並根據上述標準給予實際分數（切勿無腦給滿分）。
你必須且只能回傳以下格式的純 JSON（分數欄位請直接輸出數字，不要加 markdown 標記）：
{{"total_score": 總分, "breakdown": {{"science_first_score": 科學先決分數, "hook_appeal_score": 吸引力分數, "format_score": 格式分數}}, "comment": "請提供具體且嚴苛的評語，並說明為何得分或扣分"}}"""
    )
    
    response = (prompt | llm).invoke({"generated_json_str": generated_json_str, "core_mechanism": core_mechanism})
    raw = _extract_text(response.content)
    content = _parse_json(raw)
    try:
        result = json.loads(content)
        if isinstance(result, dict) and "total_score" in result:
            return result
    except Exception as e:
        print(f"   ⚠️ Critic JSON 解析失敗: {e}")
        print(f"   Raw: {content[:200]}")
    return {"total_score": 0, "breakdown": {}, "comment": "Critic 輸出格式錯誤"}


def _extract_text(content) -> str:
    """將 LangChain Gemini 的 .content 統一轉為純文字字串"""
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


def _parse_json(content: str) -> str:
    """從 LLM 回傳文字中提取純 JSON 字串"""
    content = content.strip()
    
    # 移除 markdown code fences
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    # 嘗試找 JSON 物件
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start:end+1]
    
    # 嘗試找 JSON 陣列
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1 and end > start:
        return content[start:end+1]
        
    return content
