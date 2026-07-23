from typing import List, Tuple
from core.rag.chunker import TextChunk

try:
    from flashrank import Ranker, RerankRequest
    HAS_FLASHRANK = True
except ImportError:
    HAS_FLASHRANK = False

class SemanticReranker:
    def __init__(self):
        if HAS_FLASHRANK:
            try:
                self.ranker = Ranker(model_name="ms-marco-MiniLM-L-6-v2")
            except Exception:
                self.ranker = None
        else:
            self.ranker = None

    def rerank(self, query: str, candidate_chunks: List[TextChunk], top_n: int = 6) -> List[TextChunk]:
        if not candidate_chunks:
            return []

        if HAS_FLASHRANK and self.ranker is not None:
            try:
                passages = [
                    {"id": c.chunk_id, "text": c.text, "meta": {"chunk": c}}
                    for c in candidate_chunks
                ]
                rerank_request = RerankRequest(query=query, passages=passages)
                results = self.ranker.rerank(rerank_request)
                
                reranked_chunks = [item["meta"]["chunk"] for item in results[:top_n]]
                return reranked_chunks
            except Exception:
                pass

        # Smart Keyword Overlap Fallback Reranking if FlashRank isn't installed/loaded
        query_words = set(query.lower().split())
        
        def _score_chunk(chunk: TextChunk) -> float:
            words = chunk.text.lower().split()
            if not words:
                return 0.0
            matches = sum(1 for w in words if w in query_words)
            return matches / float(len(words))

        sorted_chunks = sorted(candidate_chunks, key=_score_chunk, reverse=True)
        return sorted_chunks[:top_n]
