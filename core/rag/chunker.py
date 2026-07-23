import re
from typing import List, Dict, Any
from pydantic import BaseModel

class TextChunk(BaseModel):
    chunk_id: str
    source_url: str
    source_title: str
    text: str
    token_count: int

class SemanticChunker:
    def __init__(self, target_chunk_size: int = 300, overlap: int = 50):
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap

    def chunk_document(self, doc: Dict[str, Any]) -> List[TextChunk]:
        text = doc.get("full_content", "") or doc.get("content", "")
        url = doc.get("url", "")
        title = doc.get("title", "")
        
        if not text:
            return []

        # Split text by paragraph break patterns
        paragraphs = re.split(r'\n\s*\n', text)
        chunks: List[TextChunk] = []
        current_chunk = []
        current_tokens = 0
        chunk_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Approximate token count (words * 1.3)
            para_tokens = int(len(para.split()) * 1.3)
            
            if current_tokens + para_tokens > self.target_chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append(TextChunk(
                    chunk_id=f"{url}#chunk_{chunk_idx}",
                    source_url=url,
                    source_title=title,
                    text=chunk_text,
                    token_count=current_tokens
                ))
                chunk_idx += 1
                # Overlap retention
                current_chunk = current_chunk[-1:] if self.overlap > 0 else []
                current_tokens = int(len(" ".join(current_chunk).split()) * 1.3)

            current_chunk.append(para)
            current_tokens += para_tokens

        if current_chunk:
            chunks.append(TextChunk(
                chunk_id=f"{url}#chunk_{chunk_idx}",
                source_url=url,
                source_title=title,
                text=" ".join(current_chunk),
                token_count=current_tokens
            ))

        return chunks

class ContextOrderingEngine:
    @staticmethod
    def apply_u_shaped_ordering(chunks: List[TextChunk]) -> List[TextChunk]:
        """
        Reorders chunks into a U-shaped layout:
        Most relevant chunks are placed at the absolute start and end of the prompt context window,
        placing less relevant chunks in the middle.
        """
        if len(chunks) <= 2:
            return chunks

        u_ordered = [None] * len(chunks)
        left = 0
        right = len(chunks) - 1

        for idx, chunk in enumerate(chunks):
            if idx % 2 == 0:
                u_ordered[left] = chunk
                left += 1
            else:
                u_ordered[right] = chunk
                right -= 1

        return [c for c in u_ordered if c is not None]
