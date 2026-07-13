import asyncio, sys, aiohttp, re
from bs4 import BeautifulSoup

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    async with aiohttp.ClientSession() as session:
        # Startpage
        async with session.get('https://www.startpage.com/search?q=python&language=en&cat=web', headers=headers) as r:
            html = await r.text()
            soup = BeautifulSoup(html, 'html.parser')
            print("=== STARTPAGE FIRST RESULT ===")
            results = soup.select('.result')
            if results:
                res = results[0]
                print("HTML:")
                print(res.prettify()[:2500])
                # Test finding selectors
                title_el = res.select_one("h2, h3, .title, a")
                link_els = res.select("a")
                print("Title element:", title_el)
                print("All links in result:")
                for l in link_els:
                    print(f"  Href: {l.get('href')}, text: {l.get_text(strip=True)}, class: {l.get('class')}")
            else:
                print("No startpage results found")
                
        # Bing HTML dump analysis
        async with session.get('https://www.bing.com/search?q=python&setlang=en', headers=headers) as r:
            html = await r.text()
            print("=== BING ANALYSIS ===")
            # Look for typical class names in Bing
            # Find class/id names
            classes = set(re.findall(r'class="([^"]+)"', html))
            ids = set(re.findall(r'id="([^"]+)"', html))
            print("Some IDs in Bing HTML:", list(ids)[:30])
            print("Some Classes in Bing HTML:", list(classes)[:30])
            # Let's search for some text like "python.org" or search results links in the html
            # Find all hrefs containing python.org
            urls = re.findall(r'href="([^"]+python\.org[^"]*)"', html)
            print("Hrefs to python.org:", urls)
            # Find elements containing these links
            soup = BeautifulSoup(html, 'html.parser')
            for u in urls[:3]:
                # find the element
                el = soup.find(href=u)
                if el:
                    print(f"Found element for {u}: Tag={el.name}, Parent={el.parent.name if el.parent else 'None'}, Parent class={el.parent.get('class') if el.parent else 'None'}")
                    # Show parent chain
                    curr = el
                    chain = []
                    for _ in range(4):
                        if curr.parent:
                            chain.append(f"{curr.parent.name}.{'.'.join(curr.parent.get('class', []))}")
                            curr = curr.parent
                    print("  Parent chain:", " -> ".join(chain))

asyncio.run(main())
