import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict

from crawlers.trend_crawler import run_trend_pipeline
from crawlers.science_crawler import run_science_pipeline
from crawlers.social_crawler import run_social_pipeline
from engine.pipeline import run_v3_pipeline
from db import store

app = FastAPI(title="雙軌科普腳本自動化引擎 V3", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# ─── Data API (獲取資料庫內容) ───

@app.get("/api/data/trends")
def get_trends():
    return store.fetch_latest_trends()

@app.get("/api/data/social")
def get_social():
    return store.fetch_latest_social()

@app.get("/api/data/science")
def get_science():
    return store.fetch_latest_science()

@app.get("/api/history")
def get_history():
    return store.fetch_generation_history()

# ─── Crawl API (觸發爬蟲) ───

@app.post("/api/crawl/trends")
def crawl_trends():
    run_trend_pipeline()
    return {"status": "success", "message": "時事爬取完成"}

@app.post("/api/crawl/social")
def crawl_social():
    run_social_pipeline()
    return {"status": "success", "message": "社群爬取完成"}

@app.post("/api/crawl/science")
def crawl_science():
    run_science_pipeline()
    return {"status": "success", "message": "科學爬取完成"}

@app.post("/api/crawl/all")
async def crawl_all():
    # 這裡可以改成 async/await 並發執行以加速
    run_trend_pipeline()
    run_social_pipeline()
    run_science_pipeline()
    return {"status": "success", "message": "全平台爬取完成"}


# ─── Generate API (觸發引擎配對與生成) ───

class GenerateRequest(BaseModel):
    locked_items: Optional[Dict[str, Optional[str]]] = None

@app.post("/api/generate")
async def generate_script(req: GenerateRequest):
    """
    執行 V3 流程：
    1. 呼叫 pipeline 進行 [科普核心] → [配對] → [3視角 Hook] → [Critic 審查]。
    """
    try:
        # 直接執行 V3 pipeline，傳入使用者鎖定的 URL 字典
        result = run_v3_pipeline(req.locked_items if req.locked_items else {})
        
        if result.get("error"):
            return {"status": "error", "message": result["error"]}

        quality_warning = ""
        if not result.get("passed", False):
            quality_warning = f"⚠️ 品質未達門檻（{result.get('critic_score', 0)}/{8}），以下為最佳結果"

        return {
            "status": "success",
            "science_core": result.get("science_core", "無科學核心內容"),
            "reasoning": result.get("reasoning", "無企劃屬性邏輯"),
            "mechanism": result.get("mechanism", "未知機制"),
            "hooks": result.get("hooks", ["", "", ""]),
            "critic_score": result.get("critic_score", 0),
            "critic_breakdown": result.get("critic_breakdown", {}),
            "critic_comment": result.get("critic_comment", ""),
            "quality_warning": quality_warning,
            "matched_trend": result.get("matched_trend", {}),
            "matched_science": result.get("matched_science", {}),
            "matched_social": result.get("matched_social", {})
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"引擎內部錯誤：{str(e)}")


# ─── Save API (儲存至資料庫) ───

class SaveRequest(BaseModel):
    science_core: str
    mechanism: str
    hooks_json: Optional[str] = "[]"
    critic_score: Optional[int] = 0
    critic_breakdown_json: Optional[str] = "{}"
    matched_trend_url: Optional[str] = ""
    matched_science_url: Optional[str] = ""

@app.post("/api/save")
async def save_inspiration(req: SaveRequest):
    """將生成的靈感儲存至 SQLite history 表。"""
    try:
        if not req.science_core:
            raise HTTPException(status_code=400, detail="沒有可以保存的腳本！")

        store.save_history(req.dict())
        return {"status": "success", "message": "成功儲存靈感至資料庫"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存失敗：{str(e)}")

# ─── Surprise API (隨機挑選科學文章生成) ───

@app.post("/api/surprise")
async def surprise_generate():
    """隨機從 DB 中挑選一篇科學文獻，自動配對時事/社群後生成 Hook。"""
    try:
        import random
        science_data = store.fetch_latest_science(limit=30).get("data", [])
        if not science_data:
            return {"status": "error", "message": "資料庫無科學文獻，請先執行爬取！"}
        
        chosen = random.choice(science_data)
        result = run_v3_pipeline({"science_url": chosen["url"]})
        
        if result.get("error"):
            return {"status": "error", "message": result["error"]}

        return {
            "status": "success",
            "science_core": result.get("science_core", ""),
            "reasoning": result.get("reasoning", "無企劃屬性邏輯"),
            "mechanism": result.get("mechanism", ""),
            "hooks": result.get("hooks", ["", "", ""]),
            "critic_score": result.get("critic_score", 0),
            "critic_breakdown": result.get("critic_breakdown", {}),
            "critic_comment": result.get("critic_comment", ""),
            "matched_science": result.get("matched_science", {}),
            "matched_trend": result.get("matched_trend", {}),
            "matched_social": result.get("matched_social", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Surprise 生成失敗：{str(e)}")


# ─── Science Evaluate API (評估科學文章可信度) ───

class EvaluateRequest(BaseModel):
    url: str

@app.post("/api/science/evaluate")
async def evaluate_science(req: EvaluateRequest):
    """根據 URL 回傳該科學來源的可信度星級與白/黑名單狀態。"""
    from config import SCIENTIFIC_WHITELIST, SCIENTIFIC_BLACKLIST, CREDIBILITY_SCORES
    
    url_lower = req.url.lower()
    
    # 黑名單檢查
    is_blacklisted = any(bl in url_lower for bl in SCIENTIFIC_BLACKLIST)
    
    # 白名單檢查
    is_whitelisted = any(wl in url_lower for wl in SCIENTIFIC_WHITELIST)
    
    # 可信度分數
    score = 1
    for domain, s in CREDIBILITY_SCORES.items():
        if domain != "default" and domain in url_lower:
            score = s
            break

    return {
        "url": req.url,
        "credibility_score": score,
        "is_whitelisted": is_whitelisted,
        "is_blacklisted": is_blacklisted,
        "stars": "★" * score + "☆" * (3 - score)
    }


if __name__ == "__main__":
    import uvicorn
    print("啟動 V3 引擎伺服器...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
