import os
import time
import hashlib
import requests
import trafilatura
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin, urlparse

# 確保 data/pdfs 資料夾存在
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PDF_DIR = os.path.join(BASE_DIR, "data", "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ---------------------------------------------------
# 核心輔助：透過 Landing Page 取得 PDF URL 或全文
# ---------------------------------------------------

def _get_pdf_url_from_landing_page(landing_url: str) -> str | None:
    """
    嘗試從論文 Landing Page 找到 PDF 連結。
    使用 cloudscraper 繞過 Cloudflare 等 bot 防護。
    
    各期刊 citation_pdf_url 值的格式差異：
    - Oxford Academic: .../article-pdf/xxx.pdf  (含 .pdf)
    - Frontiers:       .../pdf  (以 /pdf 結尾，非 .pdf)
    - APS:             link.aps.org/pdf/10.xxx  (含 /pdf)
    - Science.org:     無此 meta tag，但頁面有 /doi/pdf/... 連結
    → 只要含 'pdf' 字樣就視為有效 PDF 連結
    """
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(browser='chrome')
        resp = scraper.get(landing_url, timeout=20, allow_redirects=True)
        if resp.status_code != 200:
            print(f"  Warning: Landing page returned {resp.status_code}, skipping.")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 策略 1：citation_pdf_url meta tag（Oxford, Frontiers, APS 均支援）
        # 只需包含 'pdf' 字樣即視為有效（涵蓋 /pdf 結尾的 Frontiers 與 APS 格式）
        meta = soup.find("meta", {"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            val = meta["content"]
            if "pdf" in val.lower():
                print(f"  [citation_pdf_url] Found PDF link: {val}")
                return val
            else:
                print(f"  [citation_pdf_url] Found but not a PDF link: {val}")

        # 策略 2：ScienceDirect 專屬 URL 構造（使用跳轉後的最終網址 resp.url）
        # ScienceDirect PDF URL 規律：文章頁 URL + /pdfft 或 /pdf
        final_url = resp.url
        if "sciencedirect.com" in final_url.lower():
            for pdf_suffix in ["/pdfft?isDTMRedir=true", "/pdfft", "/pdf"]:
                candidate = final_url.rstrip("/") + pdf_suffix
                print(f"  [ScienceDirect] 嘗試從最終網址構造 PDF URL: {candidate}")
                try:
                    # 注意：ScienceDirect 可能擋 HEAD 請求，這裡改用 GET 但只取 header 比較保險
                    test_resp = scraper.get(candidate, headers=HEADERS, timeout=10, stream=True, allow_redirects=True)
                    if test_resp.status_code == 200:
                        ct = test_resp.headers.get("Content-Type", "")
                        if "pdf" in ct or "octet-stream" in ct:
                            print(f"  [ScienceDirect] PDF URL 有效: {candidate}")
                            return candidate
                except Exception:
                    pass

        # 策略 3：針對特定結構優先搜尋（ViewPDF class 等），再掃全頁 <a>
        base = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"

        # 先優先搜尋已知含 PDF 連結的結構
        priority_selectors = [
            {"class_": "ViewPDF"},       # ScienceDirect (靜態版)
            {"class_": "pdf-download"},  # 通用
            {"id": "pdfLink"},           # 某些期刊
        ]
        for sel in priority_selectors:
            container = soup.find(["li", "a", "div", "button"], **sel)
            if container:
                a_tag = container.find("a", href=True) or (container if container.name == "a" else None)
                if a_tag:
                    href = a_tag["href"]
                    if "pdf" in href.lower():
                        full_url = urljoin(base, href)
                        print(f"  [priority selector] Found PDF link: {full_url}")
                        return full_url

        # 最後：掃描全頁所有 <a>，找含 /pdf 或 .pdf 的連結
        for a in soup.find_all("a", href=True):
            href = a["href"]
            href_lower = href.lower()
            if "/pdf" in href_lower or href_lower.endswith(".pdf"):
                full_url = urljoin(base, href)
                print(f"  [href scan] Found PDF link: {full_url}")
                return full_url

        print(f"  No PDF link found on landing page.")
        return None

    except Exception as e:
        print(f"  Warning: Landing page parse error: {e}")
        return None


def _extract_fulltext_from_landing_page(landing_url: str) -> str | None:
    """
    使用 trafilatura 從論文 Landing Page 擷取全文內容。
    適用於有網站 PDF 檢視器但無直接 PDF 下載連結的期刊
    (如 Science.org, ScienceDirect 的部分文章)。
    結果存為 .txt 檔案。
    """
    try:
        print(f"  🔍 [trafilatura] 嘗試直接從 Landing Page 擷取全文: {landing_url}")
        downloaded = trafilatura.fetch_url(landing_url)
        if not downloaded:
            print(f"  ⚠️ trafilatura 無法取得頁面內容。")
            return None

        text = trafilatura.extract(downloaded, include_tables=True, include_comments=False)
        if not text or len(text) < 500:
            print(f"  ⚠️ trafilatura 擷取的內容過少（{len(text) if text else 0} 字元），可能被付費牆擋住。")
            return None

        # 存為 .txt（偽 PDF 路徑，app.py 中的 extract_text_from_pdf 會透過 try/except 處理）
        url_hash = hashlib.md5(landing_url.encode()).hexdigest()[:8]
        safe_name = f"{int(time.time())}_{url_hash}_fulltext.txt"
        save_path = os.path.join(PDF_DIR, safe_name)

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"  ✅ [trafilatura] 全文擷取成功，已存為: {save_path} ({len(text)} 字元)")
        return save_path

    except Exception as e:
        print(f"  ⚠️ trafilatura 擷取全文時發生錯誤: {e}")
        return None


def _download_pdf_from_url(pdf_url: str) -> str | None:
    """下載 PDF 並存檔，回傳本地路徑，失敗回傳 None。"""
    try:
        print(f"  ⬇️ 正在下載 PDF: {pdf_url}")
        resp = requests.get(pdf_url, headers=HEADERS, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
                # 如果回傳的不是 PDF 而是 HTML，可能被擋了
                if "<html" in resp.text[:500].lower():
                    print(f"  ⚠️ 下載到的不是 PDF（可能是付費牆 HTML）。")
                    return None

            safe_name = f"{int(time.time())}_auto_download.pdf"
            save_path = os.path.join(PDF_DIR, safe_name)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            print(f"  ✅ PDF 下載成功: {save_path}")
            return save_path
        else:
            print(f"  ⚠️ 下載 PDF 失敗，HTTP 狀態碼: {resp.status_code}")
            return None
    except Exception as e:
        print(f"  ⚠️ 下載 PDF 時發生錯誤: {e}")
        return None


# ---------------------------------------------------
# 主要對外介面
# ---------------------------------------------------

def fetch_pdf_from_openalex(title: str, doi: str) -> str | None:
    """
    透過 OpenAlex API 自動下載論文 PDF 並儲存到本地。

    三層 Fallback 策略：
    Layer 1: OpenAlex 直接提供 pdf_url → 直接下載
    Layer 2: 用 landing_page_url 找 citation_pdf_url meta tag → 下載 PDF
    Layer 3: 用 trafilatura 從 landing page 擷取全文 → 存為 .txt

    回傳儲存的絕對路徑 (可能是 .pdf 或 .txt)，若完全失敗回傳 None。
    """
    api_key = "G2hWAW0ImADwmQcDKVLyS1"

    pdf_url = None
    landing_url = None

    # === OpenAlex 查詢 (取得 pdf_url 和 landing_page_url) ===
    openalex_data = None

    if doi:
        try:
            print(f"[OpenAlex] 正在使用 DOI 查詢: {doi}")
            url = f"https://api.openalex.org/works/doi:{doi}?api_key={api_key}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                openalex_data = resp.json()
        except Exception as e:
            print(f"⚠️ OpenAlex DOI 查詢發生錯誤: {e}")

    if not openalex_data and title:
        try:
            print(f"[OpenAlex] 正在使用標題查詢: {title}")
            encoded_title = quote(title)
            url = f"https://api.openalex.org/works?search={encoded_title}&api_key={api_key}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    openalex_data = results[0]
                    print(f"⚠️ 警告：使用論文名稱查詢取得資料 (第 1 筆結果)，請確認內容是否吻合！")
        except Exception as e:
            print(f"⚠️ OpenAlex 標題查詢發生錯誤: {e}")

    # 從 OpenAlex 結果萃取 pdf_url 和 landing_page_url
    if openalex_data:
        best_oa = openalex_data.get("best_oa_location") or {}
        pdf_url = best_oa.get("pdf_url")
        landing_url = best_oa.get("landing_page_url")

        # 若 best_oa_location 沒有，也嘗試從 open_access 拿 oa_url
        if not landing_url:
            landing_url = openalex_data.get("open_access", {}).get("oa_url")
        # doi 對應的最原始 landing page
        if not landing_url and doi:
            landing_url = f"https://doi.org/{doi}"

        print(f"[OpenAlex] pdf_url: {pdf_url}")
        print(f"[OpenAlex] landing_page_url: {landing_url}")

    # === Layer 1：直接下載 OpenAlex 提供的 pdf_url ===
    if pdf_url:
        result = _download_pdf_from_url(pdf_url)
        if result:
            return result

    # === Layer 2：從 Landing Page 尋找 PDF 連結 ===
    if landing_url:
        print(f"[Layer 2] 嘗試從 Landing Page 尋找 PDF: {landing_url}")
        found_pdf_url = _get_pdf_url_from_landing_page(landing_url)
        if found_pdf_url:
            result = _download_pdf_from_url(found_pdf_url)
            if result:
                return result

    # === Layer 3：用 trafilatura 擷取全文 ===
    if landing_url:
        print(f"[Layer 3] 嘗試用 trafilatura 直接擷取全文...")
        result = _extract_fulltext_from_landing_page(landing_url)
        if result:
            return result

    print(f"[OpenAlex] ❌ 三層策略均失敗，無法取得論文內容。")
    return None
