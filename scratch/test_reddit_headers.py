import asyncio, aiohttp

async def main():
    test_cases = [
        # Case 1: Browser-like Headers
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        # Case 2: Custom bot User-Agent
        {
            "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com)",
        },
        # Case 3: Minimal python header
        {
            "User-Agent": "python-requests/2.31.0",
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for idx, headers in enumerate(test_cases):
            url = "https://www.reddit.com/search.json?q=python&limit=3"
            try:
                async with session.get(url, headers=headers) as r:
                    print(f"Case {idx}: Status={r.status}")
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        print(f"  Success! Found: {len(data.get('data', {}).get('children', []))} posts")
                        break
                    else:
                        txt = await r.text()
                        print(f"  Failed: {txt[:100]}")
            except Exception as e:
                print(f"Case {idx} Error: {e}")

asyncio.run(main())
