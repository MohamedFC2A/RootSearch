import asyncio, aiohttp

async def main():
    headers = {
        'User-Agent': 'FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)',
        'Accept': 'application/json',
    }
    async with aiohttp.ClientSession() as session:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": "deep learning",
            "limit": "3",
            "fields": "title,abstract,url,externalIds,year",
        }
        try:
            async with session.get(url, headers=headers, params=params) as r:
                print("Semantic Scholar Status:", r.status)
                if r.status == 200:
                    data = await r.json(content_type=None)
                    print(f"Results count: {len(data.get('data', []))}")
                else:
                    text = await r.text()
                    print("Error:", text[:300])
        except Exception as e:
            print("Error:", e)

asyncio.run(main())
