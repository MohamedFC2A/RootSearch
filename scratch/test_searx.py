import asyncio, sys
sys.path.insert(0, '.')
from core.search_engine import SearchEngine

async def main():
    engine = SearchEngine()
    try:
        print("Testing SearXNG...")
        r = await engine.search_searx('python programming', num_results=5)
        print(f"SearXNG results: {len(r)}")
        for idx, res in enumerate(r[:5]):
            print(f"Result {idx}: title={res.title}, url={res.url}, source={res.source}")
    finally:
        await engine.close()

asyncio.run(main())
