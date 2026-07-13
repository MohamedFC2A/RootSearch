import asyncio, aiohttp
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://lite.qwant.com/?q=python&t=web', headers=headers) as r:
            html = await r.text()
            soup = BeautifulSoup(html, 'html.parser')
            # List all unique classes on the page
            classes = set()
            for el in soup.find_all(class_=True):
                classes.update(el.get('class'))
            print("Classes:", sorted(list(classes))[:40])
            
            # Print a snippet of a link or structure
            links = soup.find_all('a')
            print("Number of links:", len(links))
            for l in links[10:30]:
                print(f"Link: href={l.get('href')}, text={l.get_text(strip=True)[:50]}")

asyncio.run(main())
