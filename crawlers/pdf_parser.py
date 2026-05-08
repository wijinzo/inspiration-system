"""
PDF Parser — 使用 PyMuPDF 解析 PDF 檔案為純文字
用於 build_script 生成腳本時讀取本地 PDF 全文，已過濾無用資訊
"""

import fitz  # PyMuPDF
import re

def clean_pdf_text(doc: fitz.Document) -> str:
    text_parts = []
    
    # 預先編譯正則表達式，用來匹配參考資料標題 (可能帶有數字或羅馬數字標號)
    ref_pattern = re.compile(r'^(?:\d+\.?\s*|[IVX]+\.?\s*)?(references|bibliography|參考文獻|參考資料)\s*$', re.IGNORECASE)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        
        for b in blocks:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            if b[6] != 0:  # block_type != 0 表示這不是純文字區塊（例如圖片），直接跳過
                continue
                
            text = b[4].strip()
            if not text:
                continue
                
            # 1. 遇到參考資料提早結束 (通常在文章後半部)
            # 檢查區塊的第一行是否為 References 等字眼
            first_line = text.split('\n')[0].strip()
            if page_num >= len(doc) * 0.5:
                if ref_pattern.match(first_line):
                    # 偵測到參考資料標題，直接回傳目前為止累積的文字
                    return "\n\n".join(text_parts).strip()
                    
            # 2. 過濾掉圖表數據 (如果區塊中數字比例過高，通常是表格裡的數據或座標軸標籤)
            # 這能有效過濾掉無意義的圖表內容，但保留正常的段落文字
            digit_count = sum(c.isdigit() for c in text)
            if len(text) > 0 and (digit_count / len(text)) > 0.4:
                continue # 跳過疑似表格或圖表數據
                
            # 清理文字中的多餘換行，讓段落更連貫
            # 處理換行連字符 (hyphenation)
            text = text.replace("-\n", "")
            text = text.replace("- \n", "")
            # 將區塊內的其他換行轉為空格
            text = text.replace("\n", " ")
            
            # 清理多餘空白
            text = re.sub(r'\s+', ' ', text).strip()
            
            if text:
                text_parts.append(text)
            
    return "\n\n".join(text_parts).strip()


class UnreadablePDFError(Exception):
    """當 PDF 是掃描檔、純圖片或是亂碼時拋出的錯誤"""
    pass

def check_pdf_readability(text: str) -> bool:
    """檢查 PDF 萃取出的文字是否有效 (字數太少或亂碼過多)"""
    text_strip = text.strip()
    if len(text_strip) < 50:
        return False
        
    # 檢查亂碼：有效字元 (字母、中文字、數字) 比例
    valid_chars = sum(c.isalpha() or c.isdigit() for c in text_strip)
    if valid_chars / len(text_strip) < 0.4:
        return False
        
    return True

def extract_text_from_pdf(file_path: str) -> str:
    """
    從 PDF 檔案路徑讀取全文文字，並過濾掉無用的圖表與參考資料。
    若發現為無法閱讀的掃描檔或亂碼，會拋出 UnreadablePDFError。
    回傳: 純文字字串
    """
    try:
        doc = fitz.open(file_path)
        text = clean_pdf_text(doc)
        doc.close()
    except Exception as e:
        print(f"⚠️ PDF 解析失敗 ({file_path}): {e}")
        return ""
        
    if not check_pdf_readability(text):
        raise UnreadablePDFError("這是一份純影像或掃描檔，AI 無法直接閱讀。")
        
    return text


def extract_text_from_bytes(file_bytes: bytes) -> str:
    """
    從 bytes 解析 PDF 文字（用於直接處理上傳的檔案），並過濾掉無用的圖表與參考資料。
    若發現為無法閱讀的掃描檔或亂碼，會拋出 UnreadablePDFError。
    回傳: 純文字字串
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = clean_pdf_text(doc)
        doc.close()
    except Exception as e:
        print(f"⚠️ PDF bytes 解析失敗: {e}")
        return ""
        
    if not check_pdf_readability(text):
        raise UnreadablePDFError("這是一份純影像或掃描檔，AI 無法直接閱讀。")
        
    return text

