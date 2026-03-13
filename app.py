import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from crawlers.trend_crawler import run_trend_pipeline
from crawlers.science_crawler import run_science_pipeline
from engine.vector_matching import run_matching_pipeline

app = FastAPI(title="雙軌科普腳本自動化引擎 V2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveRequest(BaseModel):
    trend_data: str
    science_data: str
    generated_hook: str


@app.post("/api/generate")
async def generate_script():
    """
    執行完整 V2 流程：
    1. pytrends + RSS → 台灣時事 + 機制抽象化
    2. 科學 RSS + Brave → 科學文獻 + 機制抽象化
    3. ChromaDB 配對 + Multi-Agent Debate → Hook
    """
    try:
        # Step 1: 台灣時事
        trend_result = run_trend_pipeline()
        trends = trend_result.get("trends", [])
        all_keywords = trend_result.get("all_keywords", [])

        if trend_result.get("error"):
            return {
                "status": "error",
                "message": f"時事抓取失敗：{trend_result['error']}",
                "trends": [],
                "science": [],
                "hook": "",
                "reasoning": "",
            }

        # Step 2: 科學文獻
        science_docs = run_science_pipeline(trend_keywords=all_keywords)

        if not trends and not science_docs:
            return {
                "status": "error",
                "message": "無法取得時事與科學文獻。請檢查網路連線與 API Key。",
                "trends": [],
                "science": [],
                "hook": "",
                "reasoning": "",
            }

        if not trends:
            return {
                "status": "error",
                "message": "無法取得今日時事。RSS 和 Google Trends 均無回應。",
                "trends": [],
                "science": science_docs[:5],
                "hook": "",
                "reasoning": "",
            }

        if not science_docs:
            return {
                "status": "error",
                "message": "無法取得科學文獻。請檢查 RSS 或 Brave API Key。",
                "trends": trends,
                "science": [],
                "hook": "",
                "reasoning": "",
            }

        # Step 3: 配對 + Multi-Agent Debate
        result = run_matching_pipeline(trends, science_docs)

        # 品質警告
        quality_warning = ""
        if not result.get("passed", False):
            quality_warning = f"⚠️ 品質未達門檻（{result.get('critic_score', 0)}/{8}），以下為最佳結果"

        return {
            "status": "success",
            "trends": trends,
            "social_trends": trend_result.get("social_trends", []),
            "science": science_docs[:10],
            "hook": result.get("hook", "生成失敗"),
            "reasoning": result.get("reasoning", ""),
            "critic_score": result.get("critic_score", 0),
            "critic_comment": result.get("critic_comment", ""),
            "critic_breakdown": result.get("critic_breakdown", {}),
            "quality_warning": quality_warning,
            "matched_trend": result.get("matched_trend", {}),
            "matched_science": result.get("matched_science", {}),
            "all_pairs": result.get("all_pairs", []),
            "attempts": result.get("attempts", 0),
            "google_trends_keywords": all_keywords[:10],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"引擎內部錯誤：{str(e)}")


@app.post("/api/save")
async def save_inspiration(request: SaveRequest):
    """將生成的靈感儲存至本地 CSV。"""
    try:
        if not request.generated_hook:
            raise HTTPException(status_code=400, detail="沒有可以保存的腳本！")

        os.makedirs("saved_hooks", exist_ok=True)
        filename = f"saved_hooks/hook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        import csv
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Trend_Data", "Science_Data", "Generated_Hook"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                request.trend_data,
                request.science_data,
                request.generated_hook,
            ])

        return {"status": "success", "message": f"成功儲存靈感至 {filename}", "filename": filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存失敗：{str(e)}")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    print("啟動 V2 引擎伺服器...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
