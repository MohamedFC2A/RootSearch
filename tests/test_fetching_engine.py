import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import respx
from httpx import Response

from core.fetching.HTTP_client import TLSImpersonateClient
from core.fetching.browser_client import HeadlessBrowserEngine
from core.fetching.parser import ContentCleaner
from core.fetching.engine import ResilientFetchEngine

# =====================================================================
# 1. TLS Client & Impersonation (25+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 301, 400, 403, 404, 500, 502, 503])
async def test_tls_impersonate_status_codes(status_code):
    client = TLSImpersonateClient(timeout=1)
    url = "https://example.com/test"
    with respx.mock() as respx_mock:
        if status_code == 200:
            respx_mock.get(url).mock(return_value=Response(200, text="<html><body>Valid HTML Content</body></html>"))
        else:
            respx_mock.get(url).mock(return_value=Response(status_code, text="Error Response"))
        
        # Force fallback to httpx path if curl_cffi is missing/mocked
        with patch.dict("sys.modules", {"curl_cffi.requests": None}):
            res = await client.fetch_html(url)
            if status_code == 200:
                assert res is not None
                assert "Valid HTML Content" in res
            else:
                assert res is None

@pytest.mark.asyncio
@pytest.mark.parametrize("proxy_url", [
    "http://proxy.example.com:8080",
    "https://user:pass@proxy.io:9000",
    None
])
async def test_tls_impersonate_proxy_configurations(proxy_url):
    client = TLSImpersonateClient(timeout=1)
    url = "https://example.org/proxy_test"
    with respx.mock() as respx_mock:
        respx_mock.get(url).mock(return_value=Response(200, text="Proxy OK Content"))
        with patch.dict("sys.modules", {"curl_cffi.requests": None}):
            res = await client.fetch_html(url, proxy=proxy_url)
            assert res == "Proxy OK Content"

@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_url", [
    "not_a_valid_url",
    "http://",
    "ftp://unsupported.schema",
    "https://non-existent-domain-123456789.xyz/test"
])
async def test_tls_impersonate_invalid_urls(invalid_url):
    client = TLSImpersonateClient(timeout=1)
    with patch.dict("sys.modules", {"curl_cffi.requests": None}):
        res = await client.fetch_html(invalid_url)
        assert res is None

# =====================================================================
# 2. Trafilatura & DOM Cleaning (30+ Assertions)
# =====================================================================

HTML_EDGE_CASES = [
    ("<html><body><h1>Header</h1><p>" + ("Main content paragraph text. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><svg><path d='M0 0'/></svg><p>" + ("Clean text content string. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><iframe></iframe><div>" + ("Iframe wrapper text content block. " * 15) + "</div></body></html>", "trafilatura"),
    ("<html><body><div><p>" + ("Unclosed paragraph text block. " * 15) + "</body></html>", "trafilatura"),
    ("<html><body><script>var bad=1;</script><style>.css{color:red}</style><p>" + ("Strip scripts and styles text. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><nav>Nav Bar</nav><footer>Footer</footer><p>" + ("Body content outside nav footer. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body>" + "\n".join([f"<p>Short line {i} text block content item.</p>" for i in range(10)]) + "</body></html>", "bs4_fallback"),
    ("<html><body><p>Too short</p></body></html>", None),
    ("", None),
    (None, None),
    ("<html><body><!-- Comment --><p>" + ("Comment strip text content item. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><head><title>Title</title></head><body><div>" + ("Nested divs text content item. " * 15) + "</div></body></html>", "trafilatura"),
    ("<html><body><aside>Sidebar</aside><section><p>" + ("Section content text item. " * 15) + "</p></section></body></html>", "trafilatura"),
    ("<html><body><form><input type='text'/></form><p>" + ("Form stripped text content item. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><noscript>JS Required</noscript><p>" + ("Noscript stripped text content item. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><p>\u200b" + ("Zero width space string text item. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><p>&lt;div&gt;" + ("Escaped entities string text item. " * 15) + "&lt;/div&gt;</p></body></html>", "trafilatura"),
    ("<html><body><article><p>" + ("Article semantic tag content text. " * 15) + "</p></article></body></html>", "trafilatura"),
    ("<html><body><main><p>" + ("Main semantic tag content text. " * 15) + "</p></main></body></html>", "trafilatura"),
    ("<html><body><div><span>" + ("Span nested string content text item. " * 15) + "</span></div></body></html>", "trafilatura"),
    ("<html><body><ul>" + "".join([f"<li>List item text block {i} content.</li>" for i in range(10)]) + "</ul></body></html>", "trafilatura"),
    ("<html><body><table>" + "".join([f"<tr><td>Table data row {i} text content.</td></tr>" for i in range(5)]) + "</table></body></html>", "trafilatura"),
    ("<html><body><blockquote><p>" + ("Blockquote text content item. " * 15) + "</p></blockquote></body></html>", "trafilatura"),
    ("<html><body><pre><code>" + ("Code block formatted text item. " * 15) + "</code></pre></body></html>", "trafilatura"),
    ("<html><body><h1>H1</h1><h2>H2</h2><h3>H3</h3><p>" + ("Multiple headers text item. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><p>Line 1 text</p><p>Line 2 text</p><p>" + ("Line 3 long text item. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><div><p>" + ("Deeply nested p tag text item. " * 15) + "</p></div></body></html>", "trafilatura"),
    ("<html><body><span>" + ("Plain span element text item. " * 15) + "</span></body></html>", "trafilatura"),
    ("<html><body><p>Special chars: &amp; &quot; &apos; " + ("Text item content. " * 15) + "</p></body></html>", "trafilatura"),
    ("<html><body><div>" + ("Final fixture string content item. " * 15) + "</div></body></html>", "trafilatura")
]

@pytest.mark.parametrize("html_fixture,expected_cleaner", HTML_EDGE_CASES)
def test_content_cleaner_edge_cases(html_fixture, expected_cleaner):
    res = ContentCleaner.extract_clean_text(html_fixture, "https://example.com")
    if expected_cleaner is None:
        assert res is None
    else:
        assert res is not None
        assert "text" in res
        assert "cleaner" in res
        assert len(res["text"]) > 0

# =====================================================================
# 3. Headless Browser Fallback Trigger (20+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("html_len", [0, 50, 200, 499, 500, 1000])
async def test_headless_browser_trigger_conditions(html_len):
    engine = ResilientFetchEngine()
    short_html = "x" * html_len
    
    mock_tls = AsyncMock(return_value=short_html if html_len > 0 else None)
    mock_browser = AsyncMock(return_value="<html><body>Playwright Dynamic HTML Content</body></html>")
    
    with patch.object(engine.tls_client, "fetch_html", mock_tls), \
         patch.object(engine.browser_client, "fetch_dynamic_html", mock_browser):
        
        res = await engine.fetch_single({"url": "https://trigger.test", "content": "Fallback"})
        if html_len < 500:
            # Should have invoked browser client fallback
            mock_browser.assert_called_once()
        else:
            mock_browser.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize("playwright_exception", [
    ImportError("Playwright not installed"),
    TimeoutError("Page load timed out"),
    RuntimeError("Browser crashed"),
    Exception("Unknown browser error")
])
async def test_headless_browser_client_exceptions(playwright_exception):
    browser_engine = HeadlessBrowserEngine()
    with patch("playwright.async_api.async_playwright", side_effect=playwright_exception):
        res = await browser_engine.fetch_dynamic_html("https://example.org")
        assert res is None

# =====================================================================
# 4. Concurrency & Circuit Breaker (25+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size,concurrency", [
    (1, 1),
    (5, 2),
    (10, 5),
    (20, 8),
    (30, 10)
])
async def test_resilient_fetch_engine_concurrency_batches(batch_size, concurrency):
    engine = ResilientFetchEngine(max_concurrency=concurrency, timeout=2.0)
    items = [{"url": f"https://example.org/item_{i}", "content": f"Content {i}"} for i in range(batch_size)]
    
    async def mock_fetch(url):
        await asyncio.sleep(0.01)
        return "<html><body><h1>" + f"Title for {url}" + "</h1><p>" + ("Full text body content string. " * 15) + "</p></body></html>"

    with patch.object(engine.tls_client, "fetch_html", side_effect=mock_fetch):
        results = await engine.fetch_all(items)
        assert len(results) == batch_size
        for idx, res in enumerate(results):
            assert "full_content" in res
            assert "fetch_successful" in res
            assert res["fetch_successful"] is True

@pytest.mark.asyncio
async def test_resilient_fetch_engine_partial_failures():
    engine = ResilientFetchEngine(max_concurrency=4, timeout=1.0)
    items = [
        {"url": "https://ok1.com", "content": "C1"},
        {"url": "https://fail.com", "content": "C2"},
        {"url": "", "content": "C3"},
        {"url": "https://ok2.com", "content": "C4"}
    ]

    async def mock_tls(url):
        if "fail" in url:
            raise asyncio.TimeoutError("Timeout")
        return "<html><body><h1>Success Title Page</h1><p>" + ("Success page text item content for fetch engine partial failure assertion testing. " * 10) + "</p></body></html>"

    with patch.object(engine.tls_client, "fetch_html", side_effect=mock_tls), \
         patch.object(engine.browser_client, "fetch_dynamic_html", return_value=None):
        results = await engine.fetch_all(items)
        assert len(results) == 4
        assert results[0]["fetch_successful"] is True
        assert results[1]["fetch_successful"] is False
        assert results[2]["fetch_successful"] is False
        assert results[3]["fetch_successful"] is True
