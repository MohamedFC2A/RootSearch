import unittest
from core.rag.chunker import SemanticChunker, ContextOrderingEngine, TextChunk
from core.rag.vector_store import InMemoryVectorStore
from core.rag.reranker import SemanticReranker

class TestRAGEngine(unittest.TestCase):
    def setUp(self):
        self.chunker = SemanticChunker(target_chunk_size=100, overlap=20)
        self.vector_store = InMemoryVectorStore()
        self.reranker = SemanticReranker()

    def test_semantic_chunking(self):
        doc = {
            "title": "Quantum Computing Guide",
            "url": "https://example.com/quantum",
            "full_content": (
                "Quantum computing uses qubits to process information in parallel superposition.\n\n"
                "Superconducting circuits and trapped ions are primary physical qubit architectures.\n\n"
                "Quantum error correction guarantees fault-tolerant operation over long durations."
            )
        }
        chunks = self.chunker.chunk_document(doc)
        self.assertGreater(len(chunks), 0)
        self.assertIsInstance(chunks[0], TextChunk)
        self.assertIn("https://example.com/quantum", chunks[0].source_url)

    def test_vector_store_similarity_search(self):
        chunks = [
            TextChunk(chunk_id="1", source_url="u1", source_title="t1", text="Quantum computing and qubits", token_count=5),
            TextChunk(chunk_id="2", source_url="u2", source_title="t2", text="Baking sourdough bread at home", token_count=5)
        ]
        self.vector_store.build_index(chunks)
        results = self.vector_store.similarity_search("quantum qubits", top_k=2)

        self.assertEqual(len(results), 2)
        top_chunk, score = results[0]
        self.assertEqual(top_chunk.chunk_id, "1")

    def test_reranker(self):
        chunks = [
            TextChunk(chunk_id="1", source_url="u1", source_title="t1", text="Quantum algorithms Shor Grover", token_count=5),
            TextChunk(chunk_id="2", source_url="u2", source_title="t2", text="Vegetable soup recipe cooking", token_count=5)
        ]
        reranked = self.reranker.rerank("quantum algorithms", chunks, top_n=1)
        self.assertEqual(len(reranked), 1)
        self.assertEqual(reranked[0].chunk_id, "1")

    def test_u_shape_ordering(self):
        chunks = [
            TextChunk(chunk_id=str(i), source_url=f"u{i}", source_title=f"t{i}", text=f"text {i}", token_count=5)
            for i in range(1, 6)
        ]
        u_ordered = ContextOrderingEngine.apply_u_shaped_ordering(chunks)
        self.assertEqual(len(u_ordered), 5)
        # Verify first element is original 0th (highest score) and last element is original 1st (second highest score)
        self.assertEqual(u_ordered[0].chunk_id, "1")
        self.assertEqual(u_ordered[-1].chunk_id, "2")

if __name__ == "__main__":
    unittest.main()
