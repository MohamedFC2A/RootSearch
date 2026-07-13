import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.mojeek.com/search?q=python', headers=headers) as r:
            print("Mojeek Status:", r.status)
            html = await r.text()
            print("Length:", len(html))
            soup = BeautifulSoup(html, 'html.parser')
            print("Title:", soup.title.text if soup.title else "No Title")
            results = soup.select('.results li, li.result')
            print("Found result elements:", len(results))
            if results:
                print("First element text:")
                print(results[0].get_text(separator=' | ')[:500])

asyncio.run(main())
