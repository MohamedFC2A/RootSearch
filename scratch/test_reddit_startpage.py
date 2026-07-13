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
            results = soup.select('.result')
            print("Startpage site:reddit.com results:", len(results))
            for idx, item in enumerate(results[:3]):
                title_el = item.select_one("a.result-title h2, .wgl-title, a.result-title")
                link_el = item.select_one("a.result-title")
                if title_el and link_el:
                    print(f"  Result {idx}: title={title_el.get_text(strip=True)}, url={link_el.get('href')}")

asyncio.run(main())
