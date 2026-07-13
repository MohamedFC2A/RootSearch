import asyncio, aiohttp

async def main():
    async with aiohttp.ClientSession() as session:
        try:
            print("Fetching searx.space...")
            async with session.get("https://searx.space/data/instances.json", timeout=10) as r:
                print("Status:", r.status)
                data = await r.json(content_type=None)
                print("Instances found:", len(data.get("instances", {})))
        except Exception as e:
            print("Error:", e)

asyncio.run(main())
