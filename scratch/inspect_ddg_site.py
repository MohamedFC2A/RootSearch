import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://html.duckduckgo.com/html/?q=site:reddit.com+python', headers=headers) as r:
            html = await r.text()
            soup = BeautifulSoup(html, 'html.parser')
            print("Title:", soup.title.text if soup.title else "No Title")
            # print all link texts or some elements
            links = soup.find_all('a')
            print("Total links:", len(links))
            for l in links[:15]:
                print(f"Link: href={l.get('href')}, text={l.get_text(strip=True)[:50]}")

asyncio.run(main())
