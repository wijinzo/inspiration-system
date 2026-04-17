import requests
from bs4 import BeautifulSoup

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
        
        # 尋找內文區塊
        text_container = soup.find('div', id='text')
        if not text_container:
            # 備用：有時候長篇報導會放在 id="story_text"
            text_container = soup.find('div', id='story_text')
            
        if not text_container:
            return {"success": False, "error": "網頁結構變更或非標準 Science Daily 格式，找不到 <div id='text'>", "text": ""}
            
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
        return {"success": True, "text": raw_text, "error": None}
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"連線錯誤或超時: {str(e)}", "text": ""}
    except Exception as e:
        return {"success": False, "error": f"未知的解析錯誤: {str(e)}", "text": ""}
