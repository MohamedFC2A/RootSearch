import pytest
import asyncio
from typing import Dict, List, Any
import numpy as np

from schemas.models import SearchResult, SearXNGResult, TextChunk, CitationMetadata, SearchQueryRequest
from config.settings import settings

# Shared fixtures for pytest suite

@pytest.fixture
def sample_searxng_json_success() -> Dict[str, Any]:
    return {
        "query": "quantum computing",
        "number_of_results": 2,
        "results": [
            {
                "title": "Quantum Computing Fundamentals",
                "url": "https://example.edu/quantum",
                "content": "Comprehensive guide to quantum bits and entanglement.",
                "engine": "google",
                "score": 2.5,
                "publishedDate": "2024-01-15",
                "category": "science"
            },
            {
                "title": "Introduction to Qubits",
                "url": "https://arxiv.org/abs/2401.00001",
                "content": "Technical paper introducing qubit gates.",
                "engine": "arxiv",
                "score": 1.8,
                "publishedDate": "2024-02-01",
                "category": "academic"
            }
        ]
    }

@pytest.fixture
def sample_searxng_json_empty() -> Dict[str, Any]:
    return {"query": "empty test", "number_of_results": 0, "results": []}

@pytest.fixture
def sample_arxiv_xml_success() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <link href="http://arxiv.org/api/query?search_query=all:quantum" rel="self" type="application/atom+xml"/>
  <title type="html">ArXiv Query: search_query=all:quantum</title>
  <entry>
    <id>http://arxiv.org/abs/2305.12345v1</id>
    <title>Quantum Supremacy in $\mathbb{R}^n$ vector spaces</title>
    <summary>We present a proof of quantum supremacy using $\alpha$ and $\beta$ gates.</summary>
    <link href="http://arxiv.org/abs/2305.12345v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2305.12345v1" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2305.67890v1</id>
    <title>No Summary Paper Title</title>
    <summary></summary>
    <link href="http://arxiv.org/abs/2305.67890v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""

@pytest.fixture
def sample_html_fixtures() -> Dict[str, str]:
    return {
        "clean": "<html><body><h1>Title</h1><p>" + ("This is clean long body text for testing extraction. " * 15) + "</p></body></html>",
        "svg_spam": "<html><body><svg viewBox='0 0 100 100'><path d='M10 10'/></svg><p>" + ("SVG spam container text content test. " * 15) + "</p></body></html>",
        "nested_iframe": "<html><body><iframe><p>Nested frame</p></iframe><div>" + ("Nested iframe container valid text content. " * 15) + "</div></body></html>",
        "unclosed_tags": "<html><body><div><p>Unclosed paragraph text content for HTML parser resilience test. " * 15 + "</body></html>",
        "zero_width": "<html><body><p>\u200B\u200C\u200DZero width characters content test paragraph string. " * 15 + "</p></body></html>",
        "pure_js": "<html><head><script>var x = 100; function test(){ console.log(x); }</script></head><body><script>alert('XSS');</script></body></html>",
        "giant_css": "<html><head><style>body { background: red; color: blue; margin: 0; padding: 0; font-size: 14px; }</style></head><body><p>" + ("CSS test text string content. " * 15) + "</p></body></html>",
        "json_ld": """<html><head>
            <script type="application/ld+json">
            {"@context": "https://schema.org", "@type": "Article", "headline": "Test Article", "author": "John Doe"}
            </script>
            </head><body><p>Article body content text here.</p></body></html>""",
        "opengraph": """<html><head>
            <meta property="og:title" content="OpenGraph Test Title" />
            <meta property="og:description" content="OpenGraph Description test" />
            <meta property="og:image" content="https://example.com/image.png" />
            </head><body><p>OG test page body content.</p></body></html>"""
    }

@pytest.fixture
def sample_documents() -> List[Dict[str, Any]]:
    docs = []
    for i in range(1, 10):
        docs.append({
            "url": f"https://example{i}.org/doc{i}",
            "title": f"Document {i} Title",
            "content": f"Snippet summary for document {i}.",
            "full_content": f"Paragraph 1 for document {i} containing important technical explanations. " * 5 + f"\n\nParagraph 2 detailing algorithms and system metrics for doc {i}. " * 5,
            "fetch_successful": True,
            "authority_score": 0.8
        })
    return docs

@pytest.fixture
def sample_text_chunks() -> List[TextChunk]:
    chunks = []
    for i in range(1, 10):
        chunks.append(TextChunk(
            chunk_id=f"https://example{i}.org/doc{i}#chunk_0",
            source_url=f"https://example{i}.org/doc{i}",
            source_title=f"Document {i} Title",
            text=f"Sample text for chunk {i} with relevance keywords quantum computing research paper details.",
            token_count=150
        ))
    return chunks
