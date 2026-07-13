import asyncio, aiohttp
from bs4 import BeautifulSoup
import urllib.parse, re

async def main():
    # Use DuckDuckGo HTML search for site:reddit.com
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://html.duckduckgo.com/',
    }
    query = "site:reddit.com python programming"
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}', headers=headers) as r:
            print("Status:", r.status)
            html = await r.text()
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            for row in soup.select('.links_main'):
                a = row.select_one('.result__url, .result__snippet, a.result__snippet')
                title_el = row.select_one('a.result__title')
                snippet_el = row.select_one('.result__snippet')
                if title_el:
                    href = title_el.get('href', '')
                    # Decode DuckDuckGo redirect if any
                    if 'uddg=' in href:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = qs.get('uddg', [href])[0]
                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append({
                        'title': title,
                        'url': href,
                        'snippet': snippet
                    })
            print(f"Reddit via DDG found {len(results)} results:")
            for idx, res in enumerate(results[:5]):
                print(f"Result {idx}: title={res['title']}, url={res['url']}, snippet={res['snippet'][:100]}")

asyncio.run(main())
