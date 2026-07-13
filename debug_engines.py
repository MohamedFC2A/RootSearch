"""Debug test - check WHY each engine fails"""
import asyncio, sys, aiohttp, json, urllib.parse
sys.path.insert(0, '.')

async def test_raw():
    timeout = aiohttp.ClientTimeout(total=12)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    async with aiohttp.ClientSession(timeout=timeout) as session:

        # Test Reddit
        print("=== REDDIT ===")
        try:
            url = 'https://www.reddit.com/search.json'
            params = {'q': 'python programming', 'sort': 'relevance', 'limit': '5'}
            async with session.get(url, headers={**headers, 'Accept': 'application/json'}, params=params) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    data = await r.json(content_type=None)
                    items = data.get('data', {}).get('children', [])
                    print(f"Items: {len(items)}")
                    if items: print(f"First: {items[0]['data'].get('title','')}")
                else:
                    text = await r.text()
                    print(f"Response: {text[:300]}")
        except Exception as e:
            print(f"ERROR: {e}")
        
        # Test Wikidata
        print("\n=== WIKIDATA ===")
        try:
            url = 'https://www.wikidata.org/w/api.php'
            params = {'action': 'wbsearchentities', 'search': 'python language', 'language': 'en', 'limit': '5', 'format': 'json'}
            async with session.get(url, headers={**headers, 'Accept': 'application/json'}, params=params) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    data = await r.json(content_type=None)
                    items = data.get('search', [])
                    print(f"Items: {len(items)}")
                    if items: print(f"First: {items[0].get('label','')}")
                else:
                    text = await r.text()
                    print(f"Response: {text[:200]}")
        except Exception as e:
            print(f"ERROR: {e}")

        # Test Semantic Scholar
        print("\n=== SEMANTIC SCHOLAR ===")
        try:
            url = 'https://api.semanticscholar.org/graph/v1/paper/search'
            params = {'query': 'deep learning', 'limit': '3', 'fields': 'title,abstract,url'}
            async with session.get(url, headers={'User-Agent': 'research/1.0', 'Accept': 'application/json'}, params=params) as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    data = await r.json(content_type=None)
                    items = data.get('data', [])
                    print(f"Items: {len(items)}")
                    if items: print(f"First: {items[0].get('title','')}")
                else:
                    text = await r.text()
                    print(f"Response: {text[:300]}")
        except Exception as e:
            print(f"ERROR: {e}")

        # Test Jina
        print("\n=== JINA ===")
        try:
            url = 'https://s.jina.ai/python+tutorial'
            async with session.get(url, headers={'Accept': 'application/json', 'X-Return-Format': 'json', 'Authorization': 'Bearer '}) as r:
                print(f"Status: {r.status}")
                text = await r.text()
                print(f"Response preview: {text[:200]}")
        except Exception as e:
            print(f"ERROR: {e}")

        # Test Bing - debug HTML
        print("\n=== BING DEBUG ===")
        try:
            url = 'https://www.bing.com/search'
            params = {'q': 'python', 'count': '5'}
            async with session.get(url, headers=headers, params=params) as r:
                print(f"Status: {r.status}")
                html = await r.text()
                print(f"HTML length: {len(html)}")
                # Find result elements
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                results = soup.select('#b_results > li.b_algo')
                print(f"b_algo results: {len(results)}")
                # Try other selectors
                results2 = soup.select('.b_algo')
                print(f".b_algo results: {len(results2)}")
                if html:
                    # Show what's actually in results area
                    rb = soup.find(id='b_results')
                    if rb:
                        children = list(rb.children)
                        print(f"b_results children: {len(children)}")
                        for c in children[:3]:
                            if hasattr(c, 'get'):
                                print(f"  class: {c.get('class', [])}")
        except Exception as e:
            print(f"ERROR: {e}")

        # Test Ecosia - debug HTML 
        print("\n=== ECOSIA DEBUG ===")
        try:
            url = 'https://www.ecosia.org/search'
            params = {'q': 'python'}
            async with session.get(url, headers=headers, params=params) as r:
                print(f"Status: {r.status}")
                html = await r.text()
                print(f"HTML length: {len(html)}")
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                # Check what's actually there
                title = soup.find('title')
                print(f"Page title: {title.text if title else 'N/A'}")
                # Check for JS-rendered content indicator
                if 'noscript' in html.lower() or 'javascript' in html[:500].lower():
                    print("  -> Page requires JavaScript!")
                # Check for common result selectors
                for sel in ['article', '.result', '[class*="result"]', '[class*="mainline"]', 'main']:
                    items = soup.select(sel)
                    if items:
                        print(f"  Selector '{sel}': {len(items)} items")
                        break
        except Exception as e:
            print(f"ERROR: {e}")
        
        # Test Startpage debug
        print("\n=== STARTPAGE DEBUG ===")
        try:
            url = 'https://www.startpage.com/search'
            params = {'q': 'python', 'language': 'en', 'cat': 'web'}
            async with session.get(url, headers=headers, params=params) as r:
                print(f"Status: {r.status}")
                html = await r.text()
                print(f"HTML length: {len(html)}")
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.find('title')
                print(f"Page title: {title.text if title else 'N/A'}")
                for sel in ['.w-gl__result', '.result', 'article', '[class*="result"]']:
                    items = soup.select(sel)
                    if items:
                        print(f"  Selector '{sel}': {len(items)} items")
                        # Show first item classes/structure
                        first = items[0]
                        print(f"  First item tag: {first.name}, class: {first.get('class')}")
                        break

        except Exception as e:
            print(f"ERROR: {e}")

asyncio.run(test_raw())
