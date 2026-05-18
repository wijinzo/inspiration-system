import requests
from bs4 import BeautifulSoup
import os
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import MODEL_NAME, TEMPERATURE_FILTER
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

def scrape_sciencedaily_article(url: str) -> dict:
    """
    抓取 Science Daily 文章全文 (針對 <div id="text">)
    回傳: {"success": True, "text": "...", "error": None}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        print(f"[Scraper] 正在抓取 Science Daily 全文: {url}")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 尋找文章標題
        title = ""
        title_h1 = soup.find('h1', id='headline')
        if not title_h1:
            title_h1 = soup.find('h1')
        if title_h1:
            title = title_h1.get_text(strip=True)

        # 尋找內文區塊
        text_container = soup.find('div', id='text')
        if not text_container:
            # 備用：有時候長篇報導會放在 id="story_text"
            text_container = soup.find('div', id='story_text')
            
        if not text_container:
            return {"success": False, "error": "網頁結構變更或非標準 Science Daily 格式，找不到 <div id='text'>", "text": "", "title": title}
            
        # 準備收集所有提取的文字段落
        extracted_parts = []
        
        # 1. 抓取 <p id="first" class="lead"> 的導讀段落
        lead_p = soup.find('p', id='first', class_='lead')
        if lead_p:
            extracted_parts.append(lead_p.get_text(strip=True))
            
        # 2. 抓取 <div id="featured"> 中的 <figcaption> 內容 (例如圖片說明或研究重點)
        featured_div = soup.find('div', id='featured')
        if featured_div:
            figcaption = featured_div.find('figcaption')
            if figcaption:
                extracted_parts.append(figcaption.get_text(separator=' ', strip=True))
                
        # 3. 抓取主要區域內的所有段落 <p>
        paragraphs = text_container.find_all('p')
        main_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        if main_text:
            extracted_parts.append(main_text)
            
        # 合併全部內容
        raw_text = "\n\n".join(extracted_parts)
        
        if not raw_text or len(raw_text) < 100:
             return {"success": False, "error": "找到節點，但提取的文字過短，疑似抓取失敗。", "text": ""}
             
        print(f"[Scraper] 成功提取！擷取到 {len(raw_text)} 字的純文字。首段預覽：{raw_text[:50]}...")
        return {"success": True, "text": raw_text, "title": title, "error": None}
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"連線錯誤或超時: {str(e)}", "text": "", "title": ""}
    except Exception as e:
        return {"success": False, "error": f"未知的解析錯誤: {str(e)}", "text": "", "title": ""}

def _parse_metadata_with_llm(text: str) -> dict:
    """使用 LLM 從純文字中精準擷取論文標題與 DOI"""
    if not text or len(text.strip()) < 10:
        return {"paper_title": "", "doi": ""}
        
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("⚠️ 缺少 GOOGLE_API_KEY，無法使用 LLM 擷取論文標題與 DOI")
        return {"paper_title": "", "doi": ""}
        
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=TEMPERATURE_FILTER)
    prompt = PromptTemplate.from_template(
        """請從以下文字中擷取出學術論文的標題 (paper_title) 與 DOI (doi)。
如果找不到請留空字串。嚴格輸出為純 JSON 格式，不要包含 ```json 標籤：

文字內容:
{text}

回傳格式:
{{
  "paper_title": "論文完整標題",
  "doi": "例如 10.1038/s41467..."
}}"""
    )
    
    try:
        from crawlers.science_crawler import _parse_json
        response = (prompt | llm).invoke({"text": text[:2000]}) # 限制字數避免超載
        content = _parse_json(response.content)
            
        data = json.loads(content)
        return {
            "paper_title": data.get("paper_title", ""),
            "doi": data.get("doi", "")
        }
    except Exception as e:
        print(f"⚠️ LLM 擷取論文資訊失敗: {e}")
        return {"paper_title": "", "doi": ""}

def extract_paper_metadata(url: str) -> dict:
    """
    動態抓取網頁，尋找參考文獻區塊，並透過 LLM 擷取標題與 DOI。
    回傳: {"paper_title": "...", "doi": "..."}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        print(f"[Scraper] 正在即時爬取論文 Metadata: {url}")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        target_text = ""
        
        if "sciencedaily.com" in url:
            ref_div = soup.find('div', id='journal_references')
            if ref_div:
                target_text = ref_div.get_text(separator=' ', strip=True)
        elif "nature.com" in url:
            # Nature News or articles
            ref_ol = soup.find('ol', class_='bibliography')
            if ref_ol:
                target_text = ref_ol.get_text(separator=' ', strip=True)
            else:
                ref_div = soup.find('div', id='references')
                if ref_div:
                    target_text = ref_div.get_text(separator=' ', strip=True)
        elif "phys.org" in url:
            # Find paragraph containing "More information:" or "Journal information:"
            for p in soup.find_all('p'):
                strong = p.find('strong')
                if strong and ("More information:" in strong.text or "Journal information:" in strong.text):
                    target_text = p.get_text(separator=' ', strip=True)
                    break
                    
        # Fallback 1: if no specific block found, grab all paragraphs near the end or just body text
        if not target_text:
            paragraphs = soup.find_all('p')
            # Usually references are at the bottom, grab last 10 paragraphs
            last_ps = [p.get_text(separator=' ', strip=True) for p in paragraphs[-10:]]
            target_text = "\n".join(last_ps)
            
        result = _parse_metadata_with_llm(target_text)
        
        # Fallback 2: 若 LLM 或前述方法沒抓到 DOI，使用正則表達式掃描整個網頁 HTML 原始碼
        if not result.get("doi"):
            import re
            # 修改正則表達式，加入 a-z 且支援 IGNORECASE，涵蓋 s41550 等帶有小寫的 DOI
            doi_pattern = r'\b(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\b'
            match = re.search(doi_pattern, resp.text, re.IGNORECASE)
            if match:
                result["doi"] = match.group(1)
                print(f"[Scraper] LLM 未找到 DOI，但透過全網頁正則掃描找到: {result['doi']}")
                
        return result
        
    except Exception as e:
        print(f"⚠️ 爬取論文 Metadata 失敗: {e}")
        return {"paper_title": "", "doi": ""}
