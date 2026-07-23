import numpy as np
import hashlib
from typing import List

try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False

class FastEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        if HAS_FASTEMBED:
            try:
                self.model = TextEmbedding(model_name=model_name)
            except Exception:
                self.model = None
        else:
            self.model = None

    def _fallback_embed_text(self, text: str, dim: int = 384) -> np.ndarray:
        """Deterministic hashing embedding fallback when FastEmbed model is unavailable."""
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec
        for word in words:
            h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
            idx = h % dim
            val = (h % 100) / 100.0
            vec[idx] += val
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed(self, texts: List[str]) -> np.ndarray:
        if self.model is not None and HAS_FASTEMBED:
            try:
                embedded_generators = self.model.embed(texts)
                return np.vstack([np.array(e) for e in embedded_generators])
            except Exception:
                pass
        
        # Fallback embedding
        vectors = [self._fallback_embed_text(t) for t in texts]
        return np.vstack(vectors)
