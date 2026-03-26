import asyncio
from crawlers.trend_crawler import run_trend_pipeline
from crawlers.science_crawler import run_science_pipeline
from crawlers.social_crawler import run_social_pipeline

def main():
    print("開始爬取資料並存入本地資料庫...")
    run_trend_pipeline()
    run_social_pipeline()
    run_science_pipeline()
    print("爬取完成！")

if __name__ == "__main__":
    main()
