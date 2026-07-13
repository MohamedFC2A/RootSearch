import asyncio, sys
sys.path.insert(0, '.')
from core.search_engine import SearchEngine

async def test():
    engine = SearchEngine()
    try:
        tests = [
            ('Qwant', engine.search_qwant, 'python'),
            ('Mojeek', engine.search_mojeek, 'python programming'),
            ('OpenAlex', engine.search_openalex, 'machine learning'),
            ('Semantic Scholar', engine.search_semantic_scholar, 'deep learning'),
            ('PubMed', engine.search_pubmed, 'diabetes treatment'),
            ('CrossRef', engine.search_crossref, 'neural networks'),
            ('CORE', engine.search_core, 'natural language processing'),
            ('HackerNews', engine.search_hackernews, 'python'),
            ('Reddit', engine.search_reddit, 'python programming'),
            ('Wikidata', engine.search_wikidata, 'python language'),
            ('OpenLibrary', engine.search_openlibrary, 'python programming'),
            ('Internet Archive', engine.search_internet_archive, 'python tutorial'),
            ('Jina', engine.search_jina, 'python tutorial'),
            ('Ecosia', engine.search_ecosia, 'python programming'),
            ('Startpage', engine.search_startpage, 'python programming'),
            ('Bing', engine.search_bing, 'python programming'),
            ('Brave', engine.search_brave, 'python programming'),
        ]
        results_log = []
        for name, fn, query in tests:
            try:
                r = await fn(query, num_results=3)
                status = 'OK' if r else 'FAIL'
                count = len(r)
                first = r[0].title[:60] if r else 'N/A'
                print(f'  [{status}] {name}: {count} results | {first}')
                results_log.append((name, status, count))
            except Exception as e:
                print(f'  [ERR] {name}: {type(e).__name__}: {str(e)[:100]}')
                results_log.append((name, 'ERR', 0))
        
        print('\n--- SUMMARY ---')
        ok = sum(1 for _, s, _ in results_log if s == 'OK')
        fail = sum(1 for _, s, _ in results_log if s != 'OK')
        print(f'Working: {ok}/{len(results_log)}')
        print(f'Failed: {fail}/{len(results_log)}')
        for name, status, count in results_log:
            if status != 'OK':
                print(f'  NEEDS FIX: {name}')
    finally:
        await engine.close()

asyncio.run(test())
