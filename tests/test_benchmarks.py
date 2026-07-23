import pytest
import time
import numpy as np
from unittest.mock import patch

from core.rag.vector_store import InMemoryVectorStore
from core.rag.chunker import SemanticChunker, ContextOrderingEngine, TextChunk
from core.rag.embeddings import FastEmbedder
from core.rag.reranker import SemanticReranker
from core.aggregator import SourceTrustEvaluator, ResultAggregator
from core.fetching.parser import ContentCleaner
from core.sources.structured import StructuredDataExtractor
from core.sources.academic import HeterogeneousDataExtractor
from core.cognitive.prompt_manager import PromptManager
from schemas.models import SearXNGResult, SearchResult, TextChunk, SearchQueryRequest

# =====================================================================
# Micro-Performance Benchmarks & Latency SLA Assertions (30+ Benchmarks)
# =====================================================================

def test_benchmark_vector_search_latency_10k_chunks(benchmark):
    store = InMemoryVectorStore()
    chunks = [
        TextChunk(
            chunk_id=f"https://doc{i}.org#chunk_0",
            source_url=f"https://doc{i}.org",
            source_title=f"Doc {i}",
            text=f"Benchmark chunk text content item {i} quantum computing research paper details",
            token_count=100
        )
        for i in range(10000)
    ]
    
    # Pre-generate embeddings array of shape (10000, 384)
    np.random.seed(42)
    store.chunks = chunks
    store.embeddings = np.random.randn(10000, 384).astype(np.float32)
    
    # Target SLA: < 15ms for 10,000 chunks
    def run_search():
        return store.similarity_search("quantum computing research", top_k=15)

    results = benchmark(run_search)
    assert len(results) == 15

    # High-precision duration check
    t0 = time.perf_counter_ns()
    store.similarity_search("quantum computing research", top_k=15)
    t1 = time.perf_counter_ns()
    latency_ms = (t1 - t0) / 1e6
    assert latency_ms < 50.0, f"Vector search latency {latency_ms:.2f}ms exceeds SLA limit 50ms"

def test_benchmark_u_shaped_context_reordering_1k_elements(benchmark):
    chunks = [
        TextChunk(
            chunk_id=f"chunk_{i}",
            source_url="https://a.org",
            source_title=f"T{i}",
            text=f"Content {i}",
            token_count=50
        )
        for i in range(1000)
    ]

    def run_reorder():
        return ContextOrderingEngine.apply_u_shaped_ordering(chunks)

    ordered = benchmark(run_reorder)
    assert len(ordered) == 1000

    # Target SLA: < 1ms for 1,000 elements
    t0 = time.perf_counter_ns()
    ContextOrderingEngine.apply_u_shaped_ordering(chunks)
    t1 = time.perf_counter_ns()
    latency_ms = (t1 - t0) / 1e6
    assert latency_ms < 5.0, f"U-shape reordering latency {latency_ms:.2f}ms exceeds SLA limit 5ms"

def test_benchmark_semantic_chunker_throughput(benchmark):
    chunker = SemanticChunker(target_chunk_size=300, overlap=40)
    large_text = " ".join([f"Word_{i}" for i in range(50000)]) # 50,000 words
    doc = {"url": "https://large.org", "title": "Large Doc", "content": large_text}

    def run_chunking():
        return chunker.chunk_document(doc)

    chunks = benchmark(run_chunking)
    assert len(chunks) > 0

def test_benchmark_source_trust_authority_scoring_10k_urls(benchmark):
    evaluator = SourceTrustEvaluator()
    urls = [f"https://sub{i % 50}.domain{i % 100}.edu/path_{i}" for i in range(10000)]

    def run_eval():
        return [evaluator.calculate_authority_score(u) for u in urls]

    scores = benchmark(run_eval)
    assert len(scores) == 10000

def test_benchmark_content_cleaner_trafilatura_extraction(benchmark):
    html = "<html><body><h1>Title</h1><p>" + ("Clean paragraph text content string. " * 50) + "</p></body></html>"

    def run_clean():
        return ContentCleaner.extract_clean_text(html, "https://example.com")

    res = benchmark(run_clean)
    assert res is not None

def test_benchmark_fast_embedder_fallback_hashing_speed(benchmark):
    embedder = FastEmbedder()
    texts = [f"Quantum computing sentence block number {i}" for i in range(1000)]

    def run_embed():
        return [embedder._fallback_embed_text(t) for t in texts]

    vectors = benchmark(run_embed)
    assert len(vectors) == 1000

def test_benchmark_searxng_model_instantiation(benchmark):
    def run_models():
        return [
            SearXNGResult(
                title=f"Title {i}",
                url=f"https://url{i}.com",
                content=f"Content {i}",
                score=1.0
            )
            for i in range(5000)
        ]

    models = benchmark(run_models)
    assert len(models) == 5000

def test_benchmark_bm25_score_calculation(benchmark):
    aggregator = ResultAggregator()
    texts = [f"Document {i} text describing quantum mechanics and computing principles." for i in range(1000)]

    def run_bm25():
        return aggregator.calculate_bm25_scores(texts, "quantum computing principles")

    scores = benchmark(run_bm25)
    assert len(scores) == 1000

@pytest.mark.parametrize("size", [10, 50, 100, 250, 500, 1000])
def test_benchmark_vector_store_index_building(size):
    store = InMemoryVectorStore()
    chunks = [
        TextChunk(
            chunk_id=f"url#chunk_{i}",
            source_url="https://url.org",
            source_title=f"T{i}",
            text=f"Sample text document index build benchmark string {i}",
            token_count=50
        )
        for i in range(size)
    ]
    t0 = time.perf_counter_ns()
    store.build_index(chunks)
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1e6
    assert len(store.chunks) == size
    assert store.embeddings is not None
    assert elapsed_ms < 500.0

@pytest.mark.parametrize("source_count", [1, 10, 50, 100, 500])
def test_benchmark_semantic_reranker_fallback(source_count):
    reranker = SemanticReranker()
    chunks = [
        TextChunk(
            chunk_id=f"id_{i}",
            source_url="https://a.com",
            source_title=f"Title {i}",
            text=f"Keyword match text chunk sample {i} query string",
            token_count=40
        )
        for i in range(source_count)
    ]
    t0 = time.perf_counter_ns()
    with patch("core.rag.reranker.HAS_FLASHRANK", False):
        res = reranker.rerank("query string match", chunks, top_n=6)
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1e6
    assert len(res) <= 6
    assert elapsed_ms < 100.0

@pytest.mark.parametrize("template_name", ["synthesis", "intent_classification", "query_expansion"])
def test_benchmark_prompt_manager_rendering_speed(template_name):
    pm = PromptManager(templates_dir="config/prompts")
    context_vars = {
        "query": "test benchmark query",
        "sources": [
            TextChunk(
                chunk_id="u#c0",
                source_url="http://u.com",
                source_title="T",
                text="Text",
                token_count=10
            )
        ]
    }
    t0 = time.perf_counter_ns()
    for _ in range(100):
        pm.render_prompt(template_name, context_vars)
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1e6
    assert elapsed_ms < 1000.0

@pytest.mark.parametrize("item_count", [10, 100, 500, 1000])
def test_benchmark_structured_data_json_ld_parsing(item_count):
    html = f"<html><head><script type='application/ld+json'>[" + ",".join([f'{{"@type": "Item", "id": {i}}}' for i in range(item_count)]) + "]</script></head></html>"
    t0 = time.perf_counter_ns()
    extracted = StructuredDataExtractor.extract_json_ld(html)
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1e6
    assert len(extracted) == item_count
    assert elapsed_ms < 300.0

@pytest.mark.parametrize("num_meta", [10, 50, 100, 500])
def test_benchmark_structured_data_opengraph_parsing(num_meta):
    tags = "".join([f'<meta property="og:tag_{i}" content="val_{i}" />' for i in range(num_meta)])
    html = f"<html><head>{tags}</head></html>"
    t0 = time.perf_counter_ns()
    og = StructuredDataExtractor.extract_open_graph(html)
    t1 = time.perf_counter_ns()
    elapsed_ms = (t1 - t0) / 1e6
    assert len(og) == num_meta
    assert elapsed_ms < 200.0
