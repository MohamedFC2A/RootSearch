import asyncio, aiohttp

async def main():
    # Wikidata guidelines suggest declaring a User-Agent with contact info
    headers = {
        'User-Agent': 'FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)',
        'Accept': 'application/json',
    }
    async with aiohttp.ClientSession() as session:
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": "python language",
            "language": "en",
            "limit": "3",
            "format": "json",
            "type": "item",
        }
        try:
            async with session.get(url, headers=headers, params=params) as r:
                print("Wikidata Status:", r.status)
                if r.status == 200:
                    data = await r.json(content_type=None)
                    search_results = data.get("search", [])
                    print(f"Wikidata results: {len(search_results)}")
                    for item in search_results:
                        print(f"  ID: {item.get('id')}, Label: {item.get('label')}, Description: {item.get('description')}")
                else:
                    text = await r.text()
                    print("Error text:", text[:300])
        except Exception as e:
            print("Error:", e)

asyncio.run(main())
