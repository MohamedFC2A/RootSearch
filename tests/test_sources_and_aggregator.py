import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
import respx
from httpx import Response, RequestError

from core.sources.searxng import SearXNGClient, SearXNGResult
from core.sources.ddg import DuckDuckGoClient
from core.sources.academic import HeterogeneousDataExtractor
from core.sources.structured import StructuredDataExtractor
from core.aggregator import SourceTrustEvaluator, ResultAggregator
from schemas.models import SearchResult

# =====================================================================
# 1. SearXNG API Resilience (30+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 301, 400, 403, 404, 429, 500, 502, 503])
async def test_searxng_http_status_codes(status_code):
    client = SearXNGClient(instance_urls=["https://searx.be"], timeout=1.0)
    with respx.mock() as respx_mock:
        if status_code == 200:
            respx_mock.get("https://searx.be/search").mock(
                return_value=Response(200, json={"results": [{"title": "T", "url": "https://a.com", "content": "C"}]})
            )
        else:
            respx_mock.get("https://searx.be/search").mock(
                return_value=Response(status_code, text="Error")
            )
        
        results = await client.search("test query")
        assert isinstance(results, list)
        if status_code == 200:
            assert len(results) == 1
            assert results[0].title == "T"
            assert results[0].url == "https://a.com"
            assert results[0].content == "C"
            assert results[0].engine == "searxng"
        else:
            assert len(results) == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("instance_index", [0, 1, 2])
async def test_searxng_instance_fallbacks(instance_index):
    instances = ["https://searx1.com", "https://searx2.com", "https://searx3.com"]
    client = SearXNGClient(instance_urls=instances, timeout=1.0)
    
    with respx.mock() as respx_mock:
        for idx in range(instance_index):
            respx_mock.get(f"{instances[idx]}/search").mock(return_value=Response(500, text="Internal Error"))
        
        respx_mock.get(f"{instances[instance_index]}/search").mock(
            return_value=Response(200, json={"results": [{"title": f"Success from {instance_index}", "url": "https://ok.org", "content": "Ok"}]})
        )
        
        results = await client.search("fallback query")
        assert len(results) == 1
        assert results[0].title == f"Success from {instance_index}"

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    "invalid json string {{{",
    "",
    "12345",
    "[]",
    '{"results": "not a list"}',
    '{"results": [{"missing_url": "yes"}]}',
    '{"results": null}'
])
async def test_searxng_malformed_responses(payload):
    client = SearXNGClient(instance_urls=["https://searx.be"], timeout=1.0)
    with respx.mock() as respx_mock:
        respx_mock.get("https://searx.be/search").mock(
            return_value=Response(200, text=payload)
        )
        results = await client.search("malformed test")
        assert isinstance(results, list)

@pytest.mark.parametrize("score_val,pub_date,cat", [
    (1.0, "2024-01-01", "general"),
    (0.5, None, None),
    (2.5, "2023-12-31", "science"),
    (0.0, "invalid date", "news"),
    (-1.0, None, "tech")
])
def test_searxng_result_model_validation(score_val, pub_date, cat):
    item = SearXNGResult(
        title="Test Model",
        url="https://model.org",
        content="Test content model validation",
        score=score_val,
        published_date=pub_date,
        category=cat
    )
    assert item.title == "Test Model"
    assert item.url == "https://model.org"
    assert item.score == score_val
    assert item.published_date == pub_date
    assert item.category == cat

# =====================================================================
# 2. DuckDuckGo Engine Fallback (25+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("max_retries", [1, 2, 3])
async def test_ddg_max_retries_and_executors(max_retries):
    client = DuckDuckGoClient(max_retries=max_retries)
    with patch.object(client, '_sync_search', side_effect=Exception("DDG network error")):
        results = await client.search("python query")
        assert results == []

@pytest.mark.asyncio
@pytest.mark.parametrize("return_data", [
    [],
    [{"title": "DDG 1", "href": "https://ddg1.com", "body": "Body 1"}],
    [{"title": "DDG 1", "href": "https://ddg1.com", "body": "Body 1"}, {"title": "DDG 2", "href": "https://ddg2.com", "body": "Body 2"}],
    [{"title": "", "href": "", "body": ""}],
    [{"unexpected_key": "value"}]
])
async def test_ddg_sync_search_parser(return_data):
    client = DuckDuckGoClient(max_retries=1)
    with patch.object(client, '_sync_search', return_value=[
        {"title": r.get("title", ""), "url": r.get("href", ""), "content": r.get("body", ""), "engine": "duckduckgo"} for r in return_data if isinstance(r, dict)
    ]):
        results = await client.search("parser test")
        assert isinstance(results, list)
        assert len(results) == len(return_data)

@pytest.mark.parametrize("exception_type", [
    ImportError("duckduckgo_search missing"),
    ValueError("Invalid parameters"),
    RuntimeError("Internal DDG limit reached"),
    AttributeError("None type object has no attribute text")
])
def test_ddg_sync_search_exceptions(exception_type):
    client = DuckDuckGoClient()
    with patch("duckduckgo_search.DDGS", side_effect=exception_type):
        res = client._sync_search("exception test", max_results=5)
        assert res == []

# =====================================================================
# 3. Heterogeneous ArXiv & Structured Extractor (25+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("xml_content,expected_count", [
    ("""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>Paper 1 $\\alpha$</title><summary>Summary 1</summary><id>id1</id></entry>
        </feed>""", 1),
    ("""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>Paper Without Summary</title><id>id2</id></entry>
        </feed>""", 1),
    ("""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>""", 0),
    ("<invalid_xml_root>Malformed XML</invalid_xml_root>", 0),
    ("", 0)
])
async def test_arxiv_xml_parsing_variants(xml_content, expected_count):
    with respx.mock() as respx_mock:
        respx_mock.get().mock(return_value=Response(200, text=xml_content))
        papers = await HeterogeneousDataExtractor.fetch_arxiv_papers("quantum")
        assert len(papers) == expected_count
        if expected_count > 0 and "Paper 1" in xml_content:
            assert "Paper 1" in papers[0]["title"]
            assert papers[0]["engine"] == "arxiv"
            assert papers[0]["is_pdf"] is True

@pytest.mark.parametrize("json_script,expected_len", [
    ('<script type="application/ld+json">{"@type": "NewsArticle", "name": "News"}</script>', 1),
    ('<script type="application/ld+json">[{"@type": "Item1"}, {"@type": "Item2"}]</script>', 2),
    ('<script type="application/ld+json">Malformed JSON {{{</script>', 0),
    ('<script type="text/javascript">var a = 1;</script>', 0),
    ('', 0)
])
def test_structured_data_json_ld_extractor(json_script, expected_len):
    html = f"<html><head>{json_script}</head><body></body></html>"
    items = StructuredDataExtractor.extract_json_ld(html)
    assert len(items) == expected_len

@pytest.mark.parametrize("meta_tags,expected_keys", [
    ('<meta property="og:title" content="My Title" /><meta property="og:image" content="img.jpg" />', ["title", "image"]),
    ('<meta name="og:description" content="Desc" />', ["description"]),
    ('<meta name="author" content="John" />', []),
    ('', [])
])
def test_structured_data_open_graph_extractor(meta_tags, expected_keys):
    html = f"<html><head>{meta_tags}</head></html>"
    og_data = StructuredDataExtractor.extract_open_graph(html)
    assert isinstance(og_data, dict)
    for key in expected_keys:
        assert key in og_data

# =====================================================================
# 4. Domain Trust & Authority Scoring (40+ Assertions)
# =====================================================================

TEST_URL_PATTERNS = [
    # High Authority TLDs & Domains (Expected >= 0.7)
    ("https://harvard.edu/research", 0.7, 1.0),
    ("https://cdc.gov/health", 0.7, 1.0),
    ("https://cambridge.ac.uk/paper", 0.7, 1.0),
    ("https://en.wikipedia.org/wiki/Main_Page", 0.7, 1.0),
    ("https://github.com/torvalds/linux", 0.7, 1.0),
    ("https://arxiv.org/abs/2101.00001", 0.7, 1.0),
    ("https://nature.com/articles/s12345", 0.7, 1.0),
    ("https://reuters.com/world", 0.7, 1.0),
    ("https://bbc.com/news", 0.7, 1.0),
    ("https://nih.gov/pubmed", 0.7, 1.0),
    ("https://stackoverflow.com/questions", 0.7, 1.0),
    # Neutral & Standard Web Resources (0.3 <= score <= 0.7)
    ("https://example.com/blog/article", 0.3, 0.7),
    ("https://medium.com/p/12345", 0.3, 0.7),
    ("https://techblog.io/post", 0.3, 0.7),
    ("https://news.net/daily", 0.3, 0.7),
    ("https://ai-research.ai/paper", 0.3, 0.7),
    # Blacklisted & Spam Sites (Expected == 0.0)
    ("https://content-farm.xyz/spam-article", 0.0, 0.0),
    ("https://seo-spam-hub.com/buy-links", 0.0, 0.0),
    ("https://casino-online.example/slots", 0.0, 0.0),
    ("http://sub.content-farm.xyz/page", 0.0, 0.0),
    # Multi-subdomain penalty sites
    ("http://a.b.c.d.e.spammy-site.com/article", 0.0, 0.5),
    ("http://192.168.1.1/index.html", 0.0, 0.6),
    # Additional TLD / domain variants
    ("https://who.int/disease", 0.3, 0.8),
    ("https://un.org/charter", 0.5, 1.0),
    ("https://nasa.gov/mars", 0.7, 1.0),
    ("https://whitehouse.gov/news", 0.7, 1.0),
    ("https://oxford.ac.uk/courses", 0.7, 1.0),
    ("https://sciencedirect.com/article", 0.7, 1.0),
    ("https://nytimes.com/tech", 0.3, 0.8),
    ("https://wsj.com/markets", 0.3, 0.8),
    ("https://economist.com/finance", 0.3, 0.8),
    ("https://bloomberg.com/news", 0.3, 0.8),
    ("https://forbes.com/sites", 0.3, 0.8),
    ("https://wired.com/story", 0.3, 0.8),
    ("https://arstechnica.com/gadgets", 0.3, 0.8),
    ("https://python.org/doc", 0.5, 1.0),
    ("https://rust-lang.org/learn", 0.5, 1.0),
    ("https://w3.org/TR/html5", 0.5, 1.0),
    ("https://gnu.org/licenses", 0.5, 1.0),
    ("https://fsf.org/about", 0.5, 1.0)
]

@pytest.mark.parametrize("url,min_expected,max_expected", TEST_URL_PATTERNS)
def test_authority_scoring_url_patterns(url, min_expected, max_expected):
    evaluator = SourceTrustEvaluator()
    score = evaluator.calculate_authority_score(url)
    assert isinstance(score, float)
    assert min_expected <= score <= max_expected, f"URL {url} score {score} out of range [{min_expected}, {max_expected}]"

def test_source_trust_evaluator_filter_and_rank():
    evaluator = SourceTrustEvaluator()
    raw_results = [
        {"url": "https://content-farm.xyz/spam", "title": "Spam"},
        {"url": "https://harvard.edu/paper", "title": "Edu"},
        {"url": "https://example.com/page", "title": "Example"},
        {"url": "https://harvard.edu/paper", "title": "Duplicate Edu"}
    ]
    ranked = evaluator.filter_and_rank(raw_results, threshold=0.3)
    assert len(ranked) == 2
    assert ranked[0]["url"] == "https://harvard.edu/paper"
    assert ranked[0]["authority_score"] > ranked[1]["authority_score"]
    assert "https://content-farm.xyz/spam" not in [r["url"] for r in ranked]
