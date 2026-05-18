import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from config import MODEL_NAME, TEMPERATURE_CREATIVE, TEMPERATURE_FILTER

def run_dual_agent_script_generation(science_text: str, meme_context: str, hook_text: str, template_text: str, article_title: str = "", article_url: str = "", web_article_text: str = "") -> str:
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

[Style Reference (腳本範本)]: 
{template_text}

(Task & Rules)
1. 提取並翻譯：將文章拆解為 1.研究背景, 2.現況或痛點, 3.研究核心問題, 4.研究方法, 5.研究結果, 6.未來展望。
2. 全面深度榨取與轉譯機制：
   * 【全面保留細節】針對所有區塊，嚴禁使用一筆帶過的籠統摘要！請務必詳述原文的現象與內容。特別在「研究方法」與「研究結果」中，必須保留「具體量化數據（如樣本數、實驗過程數據、百分比、倍數、統計數據等）」、「實驗流程設計」、「對照組差異(若有)」與「特殊的實驗儀器或化學物質(若有)」。
   * 【全面比喻轉換】在保留原文細節的同時，請為各個區塊的現象、痛點、機制與結果加上生動的比喻。請參考 [Style Reference] 中的用語風格（例如生活化比喻、動漫梗比喻、幽默口語化），並優先從 [Meme Context] 尋找關聯。若差距太遠，請模仿範本自行發想最吸睛的趣味比喻。

[比喻範例 (Few-Shot Examples)]
請仔細觀察 [Style Reference] 中「將生硬科學名詞，精準對應到日常具象事物」的技巧。
- 優秀範例1.：將「酵素」比喻為「電鑽」，而裡面的「金屬離子」就是負責破壞與加工的「金屬鑽頭」。
- 優秀範例2.:接著，當氧氣分子靠近，鎳離子會把自身的一顆電子塞給氧氣。這瞬間，帶兩個正電的鎳離子 Ni2+ 變成了帶三個正電的鎳離子 Ni3+；而收到電子的氧氣，則變成「超氧自由基」，化身為破壞力極強的狂戰士。 
- 優秀範例3.:這還不夠。記憶不能只存在快取裡，得寫進硬碟。研究團隊採用「振幅加權相位鎖定值 (awPLV)」這個指標，來測量海馬迴跟大腦皮質的同步率。看這兩個腦區的神經波形「節奏」是否對拍，波峰對波峰、波谷對波谷，就像初號機跟二號機的完美同步。
請務必學習這種精準且生活化的對應方式，不要給出空泛的比喻。

3. 輸出為嚴格的巢狀 JSON 格式 (不可使用 ```json 包裹)，並嚴格遵守最低字數要求：
{{
  "研究背景": {{
    "現象與時空背景": "詳細提取原文描述的時空背景與現象細節 (至少 100 字)",
    "生動比喻": "將此背景轉化為生活化或動漫化的比喻"
  }},
  "現況或痛點": {{
    "問題與挑戰": "提取目前科學界或人類面臨的問題細節 (至少 100 字)",
    "生動比喻": "用生活化的情境或動漫化比喻這個痛點"
  }},
  "研究核心問題": "本篇論文試圖解決的終極問題 (至少 50 字)",
  "研究方法與實驗設計": {{
    "核心技術與特殊儀器": "詳細保留原文的特殊專有名詞、儀器名稱或化學物質 (至少 100 字)",
    "實驗步驟與對照組設計": "挖掘原文中的實驗組/對照組差異，並列出具體實驗流程 (至少 150 字)",
    "生動比喻": "將上述專有名詞、化學物質、實驗流程轉化為生活化或動漫化的比喻"
  }},
  "研究結果與數據": {{
    "關鍵量化數據": "強制從原文提取具體數據，如存活率、精準度提升倍數等硬核指標 (至少 100 字)",
    "突破性結論": "這項結果帶來的震撼或改變 (至少 100 字)",
    "生動比喻": "用生活化的場景或動漫化的比喻這個結果"
  }},
  "未來展望": {{
    "應用潛力與省思": "後續的應用潛力與省思 (至少 50 字)",
    "生動比喻": "用生活化的場景或動漫化的比喻未來展望"
  }}
}}
""")
    
    print("[Agent 1] 正在解構科學文獻與產生比喻...")
    analyst_response = (analyst_prompt | llm_analyst).invoke({
        "science_text": science_text,
        "meme_context": meme_context,
        "template_text": template_text
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

[Analyst JSON Data (6大區塊與深度數據/比喻)]: 
{analyst_json}

[Science Article Full Text (原始科學文獻 PDF)]:
{science_text}

[科學新聞稿 (News Release - 供敘事與抓重點參考)]:
{web_article_text}

[Style Reference (請嚴格學習其語氣)]: 
{template_text}

(Task & Rules)
【核心任務：將靜態資訊轉化為動態「腳本流」】
請遵循以下指導原則進行創作：

⚠️ 【關鍵警告：嚴格職責分離】 ⚠️
* 核心亮點萃取：你必須從 [科學新聞稿 (News Release)] 中萃取出「這項研究為什麼重要」、「最吸睛的新聞亮點」，以及「一定要講到的核心重點」，並確保這些重點成為故事鋪陳的骨架。
* 硬核數據要求：但是，在講述詳細的「研究方法」、「研究過程」與「實證數據」時，**絕對不可只使用科學新聞稿中簡略、籠統的敘述**！
* 你必須 100% 採用 [Analyst JSON Data] 與 [Science Article Full Text] 裡的實證數據、具體量化指標與深度分析來撰寫硬核段落！

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

4. 深度榨取長篇文獻的硬核細節 (Deep Extraction)：
   * 當你發現傳入的 [Science Article Full Text] 是一篇極長的 PDF 論文時，請不要只依賴大腦 1 的摘要！
   * 請主動去原文中挖掘大腦 1 可能漏掉的「具體實驗數據」、「特殊的實驗儀器」或「對比強烈的對照組結果」，適時帶入腳本中。
   * 確保「硬核科學」與「趣味娛樂」的完美平衡，讓觀眾覺得「雖然充滿專業名詞，但比喻超生動聽得懂」。

【腳本結構要求】
* 標題：基於原文章標題發想的創意 YT 標題。
* 開頭 (The Hook)：使用傳入的 Hook 抓住觀眾，並迅速帶入「研究背景」。
* 鋪陳 (The Conflict)：描述目前的「現況或痛點」與「研究核心問題」。
* 核心 (The Solution)：生動地解說「研究方法與實驗設計」，這是你最需要發揮比喻能力的段落，並請帶入真實的硬核細節。
* 高潮 (The Findings)：揭曉「研究結果與數據」，用真實數據展現其震撼人心之處。
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
        "science_text": science_text,
        "web_article_text": web_article_text,
        "template_text": template_text
    })

    writer_content = writer_response.content
    if isinstance(writer_content, list):
        writer_content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in writer_content])
        
    script_content = writer_content.strip()
    return script_content
