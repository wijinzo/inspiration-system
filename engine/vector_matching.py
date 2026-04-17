"""
Module 3: Isomorphic Matching & Multi-Agent Debate Engine

流程：
  1. ChromaDB: 將時事機制 & 科學機制 Embedding → 餘弦相似度配對
  2. Proposer Agent: 生成 YouTube 腳本 Hook (150-300 字)
  3. Critic Agent: 嚴格審查 + 評分 (≥8/10 通過)
  4. Debate Loop: 否決 → 改進建議 → 重寫，最多 3 輪
"""

import os
import json
import re
import chromadb
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    MODEL_NAME, TEMPERATURE_FILTER, TEMPERATURE_CREATIVE,
    CRITIC_THRESHOLD, MAX_DEBATE_RETRIES,
    CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME,
)


# ═══════════════════════════════════════════════
#  ChromaDB 向量配對
# ═══════════════════════════════════════════════

def embed_and_match(trends: list, science_docs: list, top_k: int = 3) -> list:
    """
    將時事 mechanism 和 科學 mechanism 做 Embedding，
    找出餘弦相似度最高的配對。

    回傳: [(trend, science, similarity_score), ...]
    """
    if not trends or not science_docs:
        print("⚠️ 趨勢或科學文獻為空，無法配對")
        return []

    print("ChromaDB: 建立向量索引並計算相似度...")

    try:
        client = chromadb.Client()  # 使用暫時性 client（每次重新計算）

        # 建立科學文獻 collection
        collection = client.get_or_create_collection(
            name="science_mechanisms",
            metadata={"hnsw:space": "cosine"}
        )

        # 清空舊資料
        try:
            existing = collection.get()
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

        # 存入科學文獻的 mechanism
        sci_docs = []
        sci_ids = []
        sci_metas = []
        for i, doc in enumerate(science_docs):
            mechanism = doc.get("mechanism", "")
            if mechanism and mechanism not in ("（提取失敗）", "（未設定 API Key）"):
                sci_docs.append(f"{doc.get('title', '')} | {mechanism}")
                sci_ids.append(f"sci_{i}")
                sci_metas.append({"index": i, "title": doc.get('title', ''), "mechanism": mechanism})

        if not sci_docs:
            print("⚠️ 沒有有效的科學機制可供配對")
            return _fallback_matching(trends, science_docs)

        collection.add(documents=sci_docs, ids=sci_ids, metadatas=sci_metas)
        print(f"  已索引 {len(sci_docs)} 篇科學文獻的機制")

        # 用每個趨勢的 mechanism 去查詢最相似的科學文獻
        pairs = []
        for trend in trends:
            trend_mechanism = trend.get("mechanism", "")
            if not trend_mechanism:
                continue

            query_text = f"{trend.get('title', '')} | {trend_mechanism}"
            results = collection.query(
                query_texts=[query_text],
                n_results=min(top_k, len(sci_docs)),
            )

            if results and results["ids"] and results["ids"][0]:
                for j, sci_id in enumerate(results["ids"][0]):
                    sci_idx = results["metadatas"][0][j]["index"]
                    distance = results["distances"][0][j] if results.get("distances") else 0
                    similarity = 1 - distance  # cosine distance → similarity

                    pairs.append({
                        "trend": trend,
                        "science": science_docs[sci_idx],
                        "similarity": round(similarity, 4),
                    })

        # 依相似度排序
        pairs.sort(key=lambda x: x["similarity"], reverse=True)
        print(f"  找到 {len(pairs)} 組配對，最高相似度: {pairs[0]['similarity'] if pairs else 'N/A'}")
        return pairs

    except Exception as e:
        print(f"⚠️ ChromaDB 配對失敗: {e}")
        return _fallback_matching(trends, science_docs)


def _fallback_matching(trends: list, science_docs: list) -> list:
    """降級方案：簡單輪替配對。"""
    print("  降級為簡單配對模式...")
    pairs = []
    for i, trend in enumerate(trends):
        sci_idx = i % len(science_docs)
        pairs.append({
            "trend": trend,
            "science": science_docs[sci_idx],
            "similarity": 0.0,
        })
    return pairs


# ═══════════════════════════════════════════════
#  Proposer Agent
# ═══════════════════════════════════════════════

def proposer_agent(trend: dict, science: dict, feedback: str = "") -> dict:
    """
    生成 YouTube 腳本 Hook（150-300 字繁體中文）。
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("請設定 GOOGLE_API_KEY")

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_CREATIVE)

    feedback_section = ""
    if feedback:
        feedback_section = f"\n⚠️ 上次的 Hook 被 Critic 否決，請根據以下建議改進：\n{feedback}\n"

    prompt = PromptTemplate.from_template(
        """你是一位具備嚴謹科學思維，同時深諳台灣網路次文化、精通動漫與遊戲迷因的頂尖 YouTube 科普頻道企劃。你的任務是將【硬核科學文獻】與【今日台灣網路時事/迷因】進行無縫且具備深度的結合。

【核心鐵律：科學本位 (Science-First)】
絕對禁止「名詞空投 (Term-dropping)」。你不能只是在文中塞入一個科學專有名詞，你必須用一句話具體且精準地解釋該科學機制的「物理、化學、生物學或社會學實際運作過程」。次文化與時事只是用來解釋這個過程的「載具」，科學知識本身才是「主體」。

【今日時事】
標題：{trend_title}
摘要：{trend_summary}
底層機制：{trend_mechanism}

【科學文獻】
標題：{science_title}
摘要：{science_summary}
科學機制：{science_mechanism}

{feedback_section}

【思考路徑 (Chain of Thought) - 強制優先輸出】
在撰寫腳本前，你必須先在 <thinking> 標籤內寫下你的邏輯推演：
1. 【科學機制解構】：用白話文精準定義該科學現象的 A 導致 B 運作過程。
2. 【同構映射綁定】：尋找今日時事中，與上述科學機制達到 1:1 邏輯吻合的次文化元素或社會現象。**（若時事本身已提供動漫梗/機制，請直接深化利用該設定作為關鍵橋樑）**。
3. 【視覺化轉換】：將所有艱澀的科學專有名詞，替換為日常生活中具備相同物理/邏輯特性的「實體物件」或「遊戲機制」。

【腳本產出約束】
- 【長度】：嚴格限制每種角度不超過 150 字的短影音 Hook 逐字稿。
- 【多視角產出】：請在 <script> 標籤內同時提供 3 種切入角度的草稿：
  - [角度一：黑色幽默/社畜梗]：運用自嘲、主管壓榨或台灣年輕世代的無奈來包裝科學。
  - [角度二：動漫/遊戲機制]：利用 RPG 術語、轉生、魔法系統或遊戲 Bug 來比喻機制。
  - [角度三：懸疑/反常識]：以一宗謎團、都市傳說或打破常人直覺的敘事起手。

【輸出格式約束】
<thinking>
1. 科學機制：...
2. 同構映射：...
3. 視覺化：...
</thinking>
<script>
【角度一：黑色幽默/社畜梗】
(腳本內容)

【角度二：動漫/遊戲機制】
(腳本內容)

【角度三：懸疑/反常識】
(腳本內容)
</script>"""
    )

    response = (prompt | llm).invoke({
        "trend_title": trend.get("title", ""),
        "trend_summary": trend.get("summary", ""),
        "trend_mechanism": trend.get("mechanism", ""),
        "science_title": science.get("title", ""),
        "science_summary": science.get("summary", ""),
        "science_mechanism": science.get("mechanism", ""),
        "feedback_section": feedback_section,
    })

    content = response.content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
            else:
                parts.append(str(part))
        text = "".join(parts)
    else:
        text = str(content)

    thinking = _extract_tag(text, "thinking")
    script = _extract_tag(text, "script")

    return {
        "hook": script if script else text,
        "reasoning": thinking if thinking else "（未生成思考過程）"
    }


def _extract_tag(text: str, tag: str) -> str:
    """提取 XML-style tag 中的內容。"""
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


# ═══════════════════════════════════════════════
#  Critic Agent
# ═══════════════════════════════════════════════

def critic_agent(hook: str, reasoning: str, trend: dict, science: dict) -> dict:
    """
    嚴格審查 Proposer 的 Hook 品質。
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        return {"score": 7, "passed": False, "comment": "API Key 未設定", "improvement": ""}

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)

    prompt = PromptTemplate.from_template(
        """你是一位極度挑剔、對「內容農場味」高度過敏的 YouTube 內容審查總監。你的任務是擔任腳本的「壓力測試員」，摧毀任何邏輯鬆散、硬蹭熱度或包裝偽科學的內容。針對給定的腳本、思考過程與素材，執行嚴格的 Veto（否決）審查。你必須假設該腳本是失敗的，除非它能通過以下三個死亡測試。

【待審核腳本】
{hook}

【Proposer 的思考過程】
{reasoning}

【原始素材】
科學文獻：{science_title}（機制：{science_mechanism}）
時事/迷因：{trend_title}（機制：{trend_mechanism}）

Critical Tests (必須逐一執行)
1. 抽換詞面測試 (Substitution Test):
   - 動作：將腳本中的科學名詞（如 {science_title}）換成「量子魔法」或「賽博能量」。
   - 判定：若語句依然通順且不影響劇情，代表科學元素僅是裝飾（Buzzword），必須 Fail。

2. 硬湊熱度檢索 (Trend-Cringe Audit):
   - 動作：對比 {trend_title} 與腳本核心邏輯。
   - 判定：若該元素移除後對劇情推進、邏輯解釋毫無影響，判定為「硬湊熱度」。

3. 因果深度檢查 (Causality Check):
   - 動作：檢查是否詳細解釋了 {science_mechanism} 的具體運作，而非僅將其作為形容詞。
   - 判定：缺乏機制解釋、因果倒置或邏輯跳躍，一律扣分。

Output Format
必須回傳純 JSON，不得包含 Markdown 代碼塊或任何前導文字。
結構：
{{
  "substitution_test": "Pass/Fail (附帶簡短理由)",
  "scientific_substance": "分析機制解釋的深度與精準度",
  "score": 1-10 的整數,
  "passed": boolean (score >= {threshold}),
  "comment": "指出最致命的破綻，不要客氣",
  "improvement": "針對邏輯斷層或偽科學點的具體重寫建議"
}}"""
    )

    try:
        response = (prompt | llm).invoke({
            "hook": hook,
            "reasoning": reasoning,
            "trend_title": trend.get("title", ""),
            "trend_mechanism": trend.get("mechanism", ""),
            "science_title": science.get("title", ""),
            "science_mechanism": science.get("mechanism", ""),
            "threshold": CRITIC_THRESHOLD,
        })

        content = _parse_json(response.content)
        result = json.loads(content)
        result["passed"] = result.get("score", 0) >= CRITIC_THRESHOLD
        return result

    except Exception as e:
        print(f"⚠️ Critic 審查失敗: {e}")
        return {"score": 5, "passed": False, "comment": f"審查失敗: {e}", "improvement": ""}


# ═══════════════════════════════════════════════
#  Debate 主循環
# ═══════════════════════════════════════════════

def generate_hook_with_debate(trend: dict, science: dict) -> dict:
    """
    Proposer → Critic 辯論循環。
    最多 MAX_DEBATE_RETRIES 輪，不過就回傳最高分的。

    回傳: {hook, reasoning, critic_score, critic_comment, passed, attempts}
    """
    print(f"\n--- Multi-Agent Debate ---")
    print(f"時事: {trend.get('title', '')[:40]}")
    print(f"科學: {science.get('title', '')[:40]}")

    best_result = None
    feedback = ""

    for attempt in range(1, MAX_DEBATE_RETRIES + 1):
        print(f"\n[Round {attempt}/{MAX_DEBATE_RETRIES}]")

        # Proposer
        try:
            print(f"  Proposer 生成 Hook...")
            proposal = proposer_agent(trend, science, feedback)
            hook = proposal.get("hook", "")
            reasoning = proposal.get("reasoning", "")
            print(f"  Hook: {hook[:50]}...")
        except Exception as e:
            print(f"  ⚠️ Proposer 失敗: {e}")
            continue

        # Critic
        try:
            print(f"  Critic 審查中...")
            critique = critic_agent(hook, reasoning, trend, science)
            score = critique.get("score", 0)
            passed = critique.get("passed", False)
            print(f"  評分: {score}/10 {'✅ PASS' if passed else '❌ VETO'}")
        except Exception as e:
            print(f"  ⚠️ Critic 失敗: {e}")
            critique = {"score": 5, "passed": False, "comment": str(e), "improvement": ""}
            score = 5
            passed = False

        result = {
            "hook": hook,
            "reasoning": reasoning,
            "critic_score": score,
            "critic_comment": critique.get("comment", ""),
            "passed": passed,
            "attempts": attempt,
            "matched_trend": trend,
            "matched_science": science,
        }

        # 記錄最高分
        if best_result is None or score > best_result.get("critic_score", 0):
            best_result = result

        if passed:
            print(f"  ✅ Hook 通過審查！")
            return result

        # 下一輪
        feedback = critique.get("improvement", "請改進 Hook 的邏輯連貫性和吸引力")
        print(f"  改進建議: {feedback[:60]}...")

    # 都沒過，回傳最高分的
    if best_result:
        print(f"\n⚠️ {MAX_DEBATE_RETRIES} 輪後仍未達 {CRITIC_THRESHOLD} 分，回傳最高分結果 ({best_result.get('critic_score', 0)}/10)")
        best_result["passed"] = False
        return best_result
    else:
        print(f"\n❌ 所有輪次皆失敗，無法生成結果。")
        return {
            "hook": "生成失敗",
            "reasoning": "所有嘗試均發生錯誤",
            "critic_score": 0,
            "passed": False,
            "attempts": MAX_DEBATE_RETRIES
        }


# ═══════════════════════════════════════════════
#  主函式
# ═══════════════════════════════════════════════

def run_matching_pipeline(trends: list, science_docs: list) -> dict:
    """
    完整 Module 3 流程。

    回傳: {
        hook, reasoning, critic_score, critic_comment,
        matched_trend, matched_science, all_pairs
    }
    """
    print("\n" + "=" * 50)
    print("Module 3: 同構映射 + Multi-Agent Debate")
    print("=" * 50)

    # Step 1: 向量配對
    pairs = embed_and_match(trends, science_docs)

    if not pairs:
        return {
            "hook": "無法生成 — 找不到合適的時事-科學配對",
            "reasoning": "",
            "critic_score": 0,
            "critic_comment": "無配對結果",
            "passed": False,
            "matched_trend": {},
            "matched_science": {},
            "all_pairs": [],
            "error": "沒有可用的配對組合",
        }

    # Step 2: 對最佳配對進行 Debate
    # 如果第一組被完全否決（3 輪都 < 門檻），嘗試第二組
    for i, pair in enumerate(pairs[:3]):  # 最多試 3 組配對
        print(f"\n嘗試配對 #{i+1}（相似度: {pair['similarity']}）")
        result = generate_hook_with_debate(pair["trend"], pair["science"])

        if result.get("passed", False) or i == 2:  # 通過或最後一組
            result["all_pairs"] = [
                {"trend_title": p["trend"].get("title", ""),
                 "science_title": p["science"].get("title", ""),
                 "similarity": p["similarity"]}
                for p in pairs[:5]
            ]
            return result

        print(f"配對 #{i+1} 未達標，嘗試下一組...")

    # 不應該到這裡，但安全起見
    return result


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

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        return content[start:end + 1]

    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1:
        return content[start:end + 1]

    return content


if __name__ == "__main__":
    trend = {
        "title": "少子化危機加劇",
        "summary": "2月新生兒跌破7千人",
        "mechanism": "社會回饋迴路失控：養育成本上升→生育意願下降→社會支撐系統萎縮→成本再上升",
    }
    sci = {
        "title": "Feedback loops in ecological collapse",
        "summary": "Study shows how positive feedback loops accelerate ecosystem decline",
        "mechanism": "正向回饋迴路驅動的臨界點崩潰效應",
    }
    result = run_matching_pipeline([trend], [sci])
    print(f"\nHook: {result['hook']}")
    print(f"Score: {result.get('critic_score', 0)}/10")
