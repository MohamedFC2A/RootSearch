import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://lite.qwant.com/?q=python&t=web', headers=headers) as r:
            print("Qwant Lite Status:", r.status)
            html = await r.text()
            print("Length:", len(html))
            soup = BeautifulSoup(html, 'html.parser')
            print("Title:", soup.title.text if soup.title else "No Title")
            results = soup.select('.result, li.result, article')
            print("Result elements found:", len(results))
            # Find all divs or elements with a class containing result
            res_any = soup.select('[class*="result"]')
            print("Any elements containing class 'result':", len(res_any))
            # Let's search for link hrefs containing python.org
            import re
            links = re.findall(r'href="([^"]+python\.org[^"]*)"', html)
            print("Hrefs to python.org:", links)
            # Find parent info for these links
            for l in links[:2]:
                el = soup.find(href=l)
                if el:
                    print(f"Link: {l}, Parent: {el.parent.name}, Parent class: {el.parent.get('class')}")
                    # print parent chain
                    curr = el
                    chain = []
                    for _ in range(3):
                        if curr.parent:
                            chain.append(f"{curr.parent.name}.{'.'.join(curr.parent.get('class', []))}")
                            curr = curr.parent
                    print("  Chain:", " -> ".join(chain))

asyncio.run(main())
