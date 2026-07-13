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
            results = []
            for item in soup.select('.result'):
                title_el = item.select_one("a.result-title h2, .wgl-title, a.result-title")
                link_el = item.select_one("a.result-title")
                snippet_el = item.select_one("p.description")
                if title_el and link_el:
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': link_el.get('href'),
                        'snippet': snippet_el.get_text(strip=True) if snippet_el else ""
                    })
            print(f"Found {len(results)} Startpage results:")
            for idx, res in enumerate(results[:3]):
                print(f"Result {idx}: title={res['title']}, url={res['url']}, snippet={res['snippet'][:100]}")

asyncio.run(main())
