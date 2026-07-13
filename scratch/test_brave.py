import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://search.brave.com/search?q=python', headers=headers) as r:
            print("Brave Status:", r.status)
            html = await r.text()
            print("Length:", len(html))
            soup = BeautifulSoup(html, 'html.parser')
            print("Title:", soup.title.text if soup.title else "No Title")
            # print first 500 chars of body to see if there's a captcha
            print(html[:1000])

asyncio.run(main())
