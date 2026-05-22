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
            current_hook_json = _run_proposer(proposer_llm, context_str, science_item['mechanism'], critic_comment)
        except Exception as e:
            print(f"!! Proposer 生成失敗: {e}")
            break
            
        # Critic 審查 (單一 Agent 完成細節與整體審查)
        try:
            critic_result = _run_critic(critic_llm, current_hook_json, science_item['mechanism'])
            
            evals = critic_result.get("evaluations", [])
            
            # 找出三個 Hook 中得分最高的一個作為本次生成的代表分數
            best_score = 0
            best_breakdown = {}
            for ev in evals:
                score = ev.get("science_first_score", 0) + ev.get("hook_appeal_score", 0) + ev.get("format_score", 0)
                if score >= best_score:
                    best_score = score
                    best_breakdown = ev
                    
            current_score = best_score
            breakdown = best_breakdown
            critic_comment = critic_result.get("critic_comment", "無評論")
            hook_evaluations = evals
            
            print(f"   => 最高 Hook 評分: {current_score}/10")
            print(f"      - Science-First: {breakdown.get('science_first_score', 0)}/4")
            print(f"      - Hook Appeal: {breakdown.get('hook_appeal_score', 0)}/3")
            print(f"      - Format: {breakdown.get('format_score', 0)}/3")
            
            if current_score >= CRITIC_THRESHOLD:
                print("   [OK] 成功通過審查標準！(至少一組 Hook 達標)")
                break
            else:
                print(f"   [FAIL] 所有 Hook 均未達標。總評: {critic_comment}")
                print(f"   => 將把 Critic 意見回饋給下一輪 Proposer 重新生成。")
        except Exception as e:
            print(f"!! Critic 審查失敗: {e}")
            break

    # 解析 JSON
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
        "hook_evaluations": hook_evaluations,
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
    
    if locked_items.get("science_url"):
        # 精確查詢，不受分頁 limit 限制（修正：舊文章超出前15筆導致找不到的問題）
        result["science"] = store.get_science_by_url(locked_items["science_url"])
    else:
        # 預設：選分數最高、最新的（前 50 筆裡找）
        science_db = store.fetch_latest_science(limit=50).get("data", [])
        if science_db:
            result["science"] = sorted(science_db, key=lambda x: x.get('credibility_score', 1), reverse=True)[0]
        
    if locked_items.get("trend_url"):
        result["trend"] = store.get_trend_by_url(locked_items["trend_url"])
        
    if locked_items.get("social_url"):
        result["social"] = store.get_social_by_url(locked_items["social_url"])
        
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

def _run_proposer(llm, context_str: str, core_mechanism: str, critic_feedback: str = "") -> str:
    prompt_template = """你是一位 YouTube 百萬級科普與動漫解說頻道的主筆。你的核心價值是「硬核科學與娛樂情緒的完美焊死」。你信奉 "Science-First, Hook-Last"，沒有紮實的科學因果，就沒有優質的腦洞。
        
Input Strategy
- 原始素材: {context_str}
- 絕對鎖定核心機制（絕對不能偏題）: {core_mechanism}

Learning Loop (自我修正機制)
若下方提供【前次審查意見】，你必須執行以下步驟：
1. 破敗分析 (Audit)：在思考時，先明確指出前次內容在「替換測試」或「邏輯斷層」上的具體敗點。
2. 差異化重構 (Pivot)：這一次的生成必須與前次有顯著的邏輯提升，嚴禁重複已被否決的修辭。

"""

    if critic_feedback:
        safe_feedback = critic_feedback.replace('{', '{{').replace('}', '}}')
        prompt_template += f"\n【前次審查意見（請必須根據此嚴格意見修正您的內容，找出問題並改進）Learning Loop (自我修正機制)若下方提供【前次審查意見】，你必須執行以下步驟：1. 破敗分析 (Audit)：在思考時，先明確指出前次內容在「替換測試」或「邏輯斷層」上的具體敗點。2. 差異化重構 (Pivot)：這一次的生成必須與前次有顯著的邏輯提升，嚴禁重複已被否決的修辭。】\n{safe_feedback}\n\n"

    prompt_template += """任務要求：
1. 先寫出【科學核心分析】(Science Core) - 約 300 字
- 禁止堆砌術語：必須使用「動作」與「結果」來解釋 {core_mechanism}。
- 因果鏈條：必須清晰交代 A 如何導致 B，B 如何引發現象 C。若將科學術語換成魔法後邏輯依然成立，即為失敗。
- 可見度：用文字描述出科學運作的「畫面感」。
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
    
    prompt = PromptTemplate.from_template(prompt_template)
    
    response = (prompt | llm).invoke({"context_str": context_str, "core_mechanism": core_mechanism})
    raw = _extract_text(response.content)
    return _parse_json(raw)


def _run_critic(llm, generated_json_str: str, core_mechanism: str) -> dict:
    prompt = PromptTemplate.from_template(
        """你是一位極度挑剔的 YouTube 科普頻道總編輯。你的審查邏輯是「先懷疑，後驗證」，專門拆解那些試圖用科學名詞包裝空洞內容的腳本。
這是他回傳的三個不同視角（幽默/迷因/懸疑）的 Hook 開場白：
- 待審查 JSON: {generated_json_str}
- 科學底層機制: {core_mechanism}

Critical Audit Standards (對三個 Hook 單獨進行評分)：
1. 科學先決 (0-4 分) - 「魔法/科幻替換測試」：
   - 如果換掉科學名詞後邏輯依然通順（代表只是在堆砌名詞，未解釋機制），給 0-1 分。
   - 提及了部分機制，但因果關係跳躍，觀眾無法理解「為什麼」，給 2-3 分。
   - 科學機制與情節發展有「不可替代的強耦合」，具備明確且具視覺感的因果鏈條，給 4 分。
2. Hook 吸引力 (0-3 分) - 「情緒與痛點」：
   - 是否精準觸發各自該有的情緒（幽默、迷因、懸疑）？有強烈反差感給 2-3 分，平鋪直敘 0-1 分。
3. 格式與完整度 (0-3 分)：
   - 作為短影音開場是否足夠吸睛且不拖泥帶水？

Output Requirement
- 必須且只能輸出純 JSON 格式，嚴禁包含 ```json 標籤。
- 分數屬性請填寫整數。
請回傳以下結構：
{{
  "evaluations": [
    {{
      "type": "Humor",
      "title": "幽默 (Humor)",
      "science_first_score": 0,
      "hook_appeal_score": 0,
      "format_score": 0,
      "comment": "對【生活幽默】Hook 的犀利點評及修改建議"
    }},
    {{
      "type": "Meme",
      "title": "迷因 (Meme/Relatability)",
      "science_first_score": 0,
      "hook_appeal_score": 0,
      "format_score": 0,
      "comment": "對【動漫迷因】Hook 的犀利點評及修改建議"
    }},
    {{
      "type": "Suspense",
      "title": "懸疑 (Suspense)",
      "science_first_score": 0,
      "hook_appeal_score": 0,
      "format_score": 0,
      "comment": "對【獵奇懸疑】Hook 的犀利點評及修改建議"
    }}
  ],
  "critic_comment": "總編給作者的一句話總評（指出最嚴重的致命傷或誇獎最大的亮點）"
}}"""
    )
    
    response = (prompt | llm).invoke({"generated_json_str": generated_json_str, "core_mechanism": core_mechanism})
    raw = _extract_text(response.content)
    content = _parse_json(raw)
    try:
        result = json.loads(content)
        if isinstance(result, dict) and "evaluations" in result:
            return result
    except Exception as e:
        print(f"   ⚠️ Critic JSON 解析失敗: {e}")
        print(f"   Raw: {content[:200]}")
    return {"evaluations": [], "critic_comment": "Critic 輸出格式錯誤"}


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