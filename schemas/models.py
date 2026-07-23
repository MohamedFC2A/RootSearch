from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Any, Optional

class SearXNGResult(BaseModel):
    title: str
    url: str
    content: str
    engine: str = "searxng"
    score: float = 1.0
    published_date: Optional[str] = None
    category: Optional[str] = None

class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    engine: str = "unknown"
    authority_score: float = 0.5
    full_content: Optional[str] = None
    fetch_successful: bool = False

class TextChunk(BaseModel):
    chunk_id: str
    source_url: str
    source_title: str
    text: str
    token_count: int

class CitationMetadata(BaseModel):
    source_index: int
    title: str
    url: str

class SearchQueryRequest(BaseModel):
    query: str
    categories: List[str] = Field(default_factory=lambda: ["general"])
    max_results: int = 15
