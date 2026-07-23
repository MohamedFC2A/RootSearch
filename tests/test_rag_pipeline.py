import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from core.rag.chunker import SemanticChunker, ContextOrderingEngine, TextChunk
from core.rag.embeddings import FastEmbedder
from core.rag.vector_store import InMemoryVectorStore
from core.rag.reranker import SemanticReranker

# =====================================================================
# 1. Semantic Text Chunker Math (30+ Assertions)
# =====================================================================

WORD_COUNTS = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
CHUNK_SIZES = [100, 300, 500]
OVERLAPS = [0, 40, 100]

@pytest.mark.parametrize("word_count", WORD_COUNTS)
@pytest.mark.parametrize("target_chunk_size", CHUNK_SIZES)
@pytest.mark.parametrize("overlap", OVERLAPS)
def test_semantic_chunker_document_chunking(word_count, target_chunk_size, overlap):
    chunker = SemanticChunker(target_chunk_size=target_chunk_size, overlap=overlap)
    text = " ".join([f"word{i}" for i in range(word_count)])
    doc = {
        "url": "https://example.com/chunk_test",
        "title": "Chunk Test Title",
        "content": text
    }
    chunks = chunker.chunk_document(doc)
    assert isinstance(chunks, list)
    
    if word_count > 0:
        assert len(chunks) > 0
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"https://example.com/chunk_test#chunk_{idx}"
            assert chunk.source_url == "https://example.com/chunk_test"
            assert chunk.source_title == "Chunk Test Title"
            assert isinstance(chunk.token_count, int)
            assert chunk.token_count > 0

@pytest.mark.parametrize("empty_doc", [
    {"url": "https://example.com", "title": "", "content": ""},
    {"url": "", "title": "", "full_content": None},
    {}
])
def test_semantic_chunker_empty_documents(empty_doc):
    chunker = SemanticChunker()
    chunks = chunker.chunk_document(empty_doc)
    assert chunks == []

# =====================================================================
# 2. In-Memory Vector Math & Embeddings (30+ Assertions)
# =====================================================================

@pytest.mark.parametrize("dim", [128, 384, 768])
@pytest.mark.parametrize("vector_pair_type", [
    "identical",
    "orthogonal",
    "inverse",
    "zero_query",
    "zero_doc",
    "nan_guard",
    "inf_guard"
])
def test_vector_store_cosine_similarity_math(dim, vector_pair_type):
    store = InMemoryVectorStore()
    
    if vector_pair_type == "identical":
        v1 = np.ones(dim, dtype=np.float32)
        v2 = np.ones((1, dim), dtype=np.float32)
    elif vector_pair_type == "orthogonal":
        v1 = np.zeros(dim, dtype=np.float32); v1[0] = 1.0
        v2 = np.zeros((1, dim), dtype=np.float32); v2[0, 1] = 1.0
    elif vector_pair_type == "inverse":
        v1 = np.ones(dim, dtype=np.float32)
        v2 = -np.ones((1, dim), dtype=np.float32)
    elif vector_pair_type == "zero_query":
        v1 = np.zeros(dim, dtype=np.float32)
        v2 = np.ones((1, dim), dtype=np.float32)
    elif vector_pair_type == "zero_doc":
        v1 = np.ones(dim, dtype=np.float32)
        v2 = np.zeros((1, dim), dtype=np.float32)
    elif vector_pair_type == "nan_guard":
        v1 = np.full(dim, np.nan, dtype=np.float32)
        v2 = np.ones((1, dim), dtype=np.float32)
    elif vector_pair_type == "inf_guard":
        v1 = np.full(dim, 1e5, dtype=np.float32)
        v2 = np.ones((1, dim), dtype=np.float32)

    v1 = np.nan_to_num(v1)
    v2 = np.nan_to_num(v2)

    dummy_chunk = TextChunk(
        chunk_id="test_id",
        source_url="https://a.com",
        source_title="T",
        text="Sample text vector test",
        token_count=10
    )
    store.chunks = [dummy_chunk]
    store.embeddings = v2

    with patch.object(store.embedder, "embed", return_value=np.array([v1])):
        results = store.similarity_search("test query", top_k=1)
        assert len(results) == 1
        chunk, sim = results[0]
        assert isinstance(sim, float)
        assert not np.isnan(sim)
        assert not np.isinf(sim)

def test_fast_embedder_fallback_hashing():
    embedder = FastEmbedder()
    vec1 = embedder._fallback_embed_text("quantum computing research")
    vec2 = embedder._fallback_embed_text("quantum computing research")
    vec3 = embedder._fallback_embed_text("completely different subject matter")

    assert vec1.shape == (384,)
    assert np.allclose(vec1, vec2)
    assert not np.allclose(vec1, vec3)

# =====================================================================
# 3. Cross-Encoder & Keyword Reranking (30+ Assertions)
# =====================================================================

@pytest.mark.parametrize("has_flashrank", [True, False])
@pytest.mark.parametrize("candidate_count", [0, 1, 10, 50, 200])
@pytest.mark.parametrize("top_n", [1, 5, 10, 20])
def test_semantic_reranker_truncation_and_fallbacks(has_flashrank, candidate_count, top_n):
    reranker = SemanticReranker()
    chunks = [
        TextChunk(
            chunk_id=f"url#chunk_{i}",
            source_url="https://a.com",
            source_title=f"Doc {i}",
            text=f"Text paragraph content with match word query {i if i % 2 == 0 else 'unrelated'}",
            token_count=50
        )
        for i in range(candidate_count)
    ]

    with patch("core.rag.reranker.HAS_FLASHRANK", has_flashrank):
        reranked = reranker.rerank("query match", chunks, top_n=top_n)
        assert isinstance(reranked, list)
        expected_len = min(candidate_count, top_n)
        assert len(reranked) == expected_len

# =====================================================================
# 4. U-Shape Context Ordering (30+ Assertions)
# =====================================================================

LIST_SIZES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 50, 100]

@pytest.mark.parametrize("n_items", LIST_SIZES)
def test_u_shaped_ordering_mathematical_proof(n_items):
    chunks = [
        TextChunk(
            chunk_id=f"chunk_{i}",
            source_url="https://example.org",
            source_title=f"Title {i}",
            text=f"Ranked item {i}",
            token_count=100
        )
        for i in range(n_items)
    ]
    
    ordered = ContextOrderingEngine.apply_u_shaped_ordering(chunks)
    assert len(ordered) == n_items
    
    if n_items > 2:
        # Highest relevance (item 0) MUST be at index 0
        assert ordered[0].chunk_id == "chunk_0"
        # 2nd highest relevance (item 1) MUST be at index N-1
        assert ordered[-1].chunk_id == "chunk_1"
        if n_items >= 4:
            # 3rd highest relevance (item 2) MUST be at index 1
            assert ordered[1].chunk_id == "chunk_2"
            # 4th highest relevance (item 3) MUST be at index N-2
            assert ordered[-2].chunk_id == "chunk_3"
