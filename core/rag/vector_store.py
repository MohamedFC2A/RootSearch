import numpy as np
from typing import List, Tuple, Optional
from core.rag.chunker import TextChunk
from core.rag.embeddings import FastEmbedder

class InMemoryVectorStore:
    def __init__(self):
        self.chunks: List[TextChunk] = []
        self.embeddings: Optional[np.ndarray] = None
        self.embedder = FastEmbedder()

    def build_index(self, chunks: List[TextChunk]):
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            return

        texts = [c.text for c in chunks]
        self.embeddings = self.embedder.embed(texts)

    def similarity_search(self, query: str, top_k: int = 15) -> List[Tuple[TextChunk, float]]:
        if not self.chunks or self.embeddings is None:
            return []

        query_embedding = self.embedder.embed([query])[0]

        # Compute cosine similarity
        norm_q = np.linalg.norm(query_embedding)
        norm_e = np.linalg.norm(self.embeddings, axis=1)
        
        # Guard against zero-division
        norm_e[norm_e == 0] = 1e-10
        norm_q = 1e-10 if norm_q == 0 else norm_q

        similarities = np.dot(self.embeddings, query_embedding) / (norm_e * norm_q)
        
        top_k = min(top_k, len(self.chunks))
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [(self.chunks[idx], float(similarities[idx])) for idx in top_indices]
