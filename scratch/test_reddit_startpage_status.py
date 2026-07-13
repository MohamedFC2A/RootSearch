import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession() as session:
        url = 'https://www.startpage.com/search?q=site:reddit.com+python&language=en&cat=web'
        async with session.get(url, headers=headers) as r:
            html = await r.text()
            soup = BeautifulSoup(html, 'html.parser')
            print("Title:", soup.title.text if soup.title else "No Title", "Length:", len(html))

asyncio.run(main())
