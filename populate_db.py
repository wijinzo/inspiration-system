import sys
sys.stdout.reconfigure(encoding='utf-8')

from crawlers.trend_crawler import run_trend_pipeline
from crawlers.science_crawler import run_science_pipeline
from crawlers.social_crawler import run_social_pipeline
from db.store import get_connection

def get_table_counts():
    """Get the number of records in each table"""
    conn = get_connection()
    c = conn.cursor()
    counts = {}
    for table in ['trend_items', 'science_articles', 'social_items', 'anime_memes']:
        try:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = c.fetchone()[0]
        except:
            counts[table] = 0
    conn.close()
    return counts

def main():
    print("=" * 50)
    print("  Initial Database Population (populate_db)")
    print("=" * 50)
    
    print("\nStarting crawlers and saving to local database...\n")
    
    run_trend_pipeline()
    run_social_pipeline()
    run_science_pipeline()
    
    # Final summary
    counts = get_table_counts()
    print("\n" + "=" * 50)
    print("  📊 Database Summary Statistics")
    print("=" * 50)
    print(f"  News & Trends   : {counts['trend_items']} items")
    print(f"  Science Articles: {counts['science_articles']} items")
    print(f"  Social Items    : {counts['social_items']} items")
    print(f"  Anime Memes     : {counts['anime_memes']} items")
    print("=" * 50)
    print("[OK] Population complete!")

if __name__ == "__main__":
    main()
