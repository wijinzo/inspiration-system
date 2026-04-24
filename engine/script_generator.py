import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from config import MODEL_NAME, TEMPERATURE_CREATIVE, TEMPERATURE_FILTER

def run_dual_agent_script_generation(science_text: str, meme_context: str, hook_text: str, template_text: str, article_title: str = "", article_url: str = "") -> str:
    """
    執行雙大腦腳本生成工作流
    Agent 1 (The Analyst): 提取6大段落並產出比喻
    Agent 2 (The Script Writer): 根據範本語氣與6大段落編排腳本
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("缺少 GOOGLE_API_KEY")

    # -----------------------------------------------------
    # Agent 1 (The Analyst)
    # -----------------------------------------------------
    llm_analyst = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)
    analyst_prompt = PromptTemplate.from_template("""
你是一位頂級的「科學解構分析師」。你的任務是將冗長、複雜的英文科學論文，解構為具備「起承轉合」的六大區塊，並將生澀的科學機制，轉化為大眾秒懂的生動比喻。

[Science Article Full Text]: 
{science_text}

[Meme Context]: 
{meme_context}

(Task & Rules)
1. 提取並翻譯：將文章拆解為 1.研究背景, 2.現況或痛點, 3.研究核心問題, 4.研究方法, 5.研究結果, 6.未來展望。
2. 轉譯機制：針對這六大區塊中出現的專業術語、複雜的實驗機制（研究方法）、或抽象的時空背景、現象（研究背景與痛點），不用轉換為白話文，請顯示原文描述的現況、現象、研究方法或專有名詞，並在後面句子加入比喻。同時，從傳入的 Meme Context 中尋找關聯，為這些機制或術語配上生動的比喻。
   * 重點規則：如果有相關 Meme Context 的梗可以連結，請寫出生動的比喻；如果概念差距太遠，絕對不要硬塞，請改用 AI 內建的「通用趣味比喻」（如動漫梗、生活化比喻）。

3. 輸出為嚴格的 JSON 格式 (不可使用 ```json 包裹)：
{{
  "研究背景": "...",
  "現況或痛點": "...",
  "研究核心問題": "...",
  "研究方法": "...",
  "研究結果": "...",
  "未來展望": "...",
  "original_english_text": "請原封不動保留原始英文科學完整文章"
}}
""")
    
    print("[Agent 1] 正在解構科學文獻與產生比喻...")
    analyst_response = (analyst_prompt | llm_analyst).invoke({
        "science_text": science_text,
        "meme_context": meme_context
    })
    
    # 嘗試清理與解析 JSON
    analyst_content = analyst_response.content
    if isinstance(analyst_content, list):
        analyst_content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in analyst_content])
    
    raw_json_str = analyst_content.strip()
    if raw_json_str.startswith("```json"):
        raw_json_str = raw_json_str.split("```json")[-1].split("```")[0].strip()
    elif raw_json_str.startswith("```"):
        raw_json_str = raw_json_str.split("```")[-1].split("```")[0].strip()

    try:
        analyst_data = json.loads(raw_json_str)
    except json.JSONDecodeError:
        print("[Warning] Agent 1 輸出的 JSON 解析失敗，將以純文字傳遞。")
        analyst_data = {"raw_content": raw_json_str}

    # 顯示 Agent 1 的產出在終端機
    print("\n" + "="*50)
    print("🤖 [Agent 1 輸出結果]")
    print(json.dumps(analyst_data, ensure_ascii=False, indent=2))
    print("="*50 + "\n")

    # -----------------------------------------------------
    # Agent 2 (The Script Writer)
    # -----------------------------------------------------
    llm_writer = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_CREATIVE)
    writer_prompt = PromptTemplate.from_template("""
你現在是台灣頂尖的知識型 YouTuber (如泛科學) 的首席腳本作家。你需要將靜態資訊轉化為動態「腳本流」。不要只是將六大區塊生硬地拼湊在一起。

[原文章標題]: 
{article_title}

[原文章連結]: 
{article_url}

[Hook 開場]: 
{hook_text}

[Analyst JSON Data (6大區塊與比喻)]: 
{analyst_json}

[Style Reference (請嚴格學習其語氣)]: 
{template_text}

(Task & Rules)
【核心任務：將靜態資訊轉化為動態「腳本流」】
請遵循以下指導原則進行創作：

1. 嚴格學習範本語氣與標題設計：
   * 在腳本最開頭，以 `#` 標記產生一個「創意標題」。請參考[原文章標題]與 `腳本範本.md` 的標題風格，將其修改為通俗易懂、有趣且吸引人的標題。
   * 模仿範本中生動的動詞（如「猛烈降溫」、「破壞力強卻能精準控血」）。
   * 適時使用對話感、括號內心 OS(例如:蛤?沒看過啊?算了。)。
   * 確保用詞符合台灣 YouTuber 的口語習慣，避免過於書面化。
   * 全文字數請盡量控制在【1300字上下】。

2. 實作「懸念式」段落銜接：
   * 每個區塊結尾與下一個區塊開始時，必須主動拋出問題或有趣的議題點，引誘觀眾繼續看下去。
   * 範例：「好，那既然必須切換溫度，為什麼之前的機器不做呢？」 或 「非鎳不可？Why?」

3. 深度整合大腦 1 的比喻：
   * 將大腦 1 產出的動漫梗或生活比喻無縫織入敘述中。
   * 如果大腦 1 提供的比喻過於生硬，你有權利根據 `腳本範本.md` 的風格進行微調，使其更符合動態腳本流的節奏。

4. 科學細節的精準嵌入：
   * 在講述「研究方法」或「研究結果」時，適時帶入原始文章中的具體數據或專有名詞（如特定名稱或單位），並保留描述，確保「硬核科學」與「趣味娛樂」的完美平衡。

【腳本結構要求】
* 標題：基於原文章標題發想的創意 YT 標題。
* 開頭 (The Hook)：使用傳入的 Hook 抓住觀眾，並迅速帶入「研究背景」。
* 鋪陳 (The Conflict)：描述目前的「現況或痛點」與「研究核心問題」。
* 核心 (The Solution)：生動地解說「研究方法」，這是你最需要發揮比喻能力的段落。
* 高潮 (The Findings)：揭曉「研究結果」，並展現其震撼人心之處。
* 結尾與展望 (The Future)：談論「未來展望」。【絕對禁止】產生常見的 YouTube 結尾廢話（例如：將影片分享出去、按讚訂閱、記得開啟小鈴鐺、下次見、掰掰等）。請著重於研究背後的省思。
* 參考文獻：在腳本的最尾端（不要有其他文字），附上原始文章的引導與連結：
  > 原始研究與參考文獻：[{article_title}]({article_url})

直接輸出 Markdown 格式的完整腳本。不要用 ```markdown 包著，直接輸出內容。
""")
    
    print("[Agent 2] 正在編寫動態腳本...")
    writer_response = (writer_prompt | llm_writer).invoke({
        "article_title": article_title,
        "article_url": article_url,
        "hook_text": hook_text,
        "analyst_json": json.dumps(analyst_data, ensure_ascii=False, indent=2),
        "template_text": template_text
    })

    writer_content = writer_response.content
    if isinstance(writer_content, list):
        writer_content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in writer_content])
        
    script_content = writer_content.strip()
    return script_content
