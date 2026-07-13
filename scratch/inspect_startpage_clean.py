import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.startpage.com/search?q=python&language=en&cat=web', headers=headers) as r:
            html = await r.text()
            soup = BeautifulSoup(html, 'html.parser')
            results = soup.select('.result')
            if results:
                # Remove style tags for readability
                for style in results[0].find_all('style'):
                    style.decompose()
                print("Clean HTML:")
                print(results[0].prettify())
            else:
                print("No results")

asyncio.run(main())
