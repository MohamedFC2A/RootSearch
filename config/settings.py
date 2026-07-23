from pydantic import BaseModel, Field
from typing import List, Optional
import os

class SearchEngineSettings(BaseModel):
    searxng_instances: List[str] = Field(
        default=["https://searx.be", "https://searx.space", "https://searx.prvcy.eu"]
    )
    request_timeout: float = 8.0
    max_concurrency: int = 10
    default_max_results: int = 15

class RAGSettings(BaseModel):
    chunk_size: int = 300
    chunk_overlap: int = 40
    top_k_similarity: int = 12
    top_n_rerank: int = 6

class Settings(BaseModel):
    app_name: str = "RootSearch AI Engine"
    debug: bool = False
    engine: SearchEngineSettings = SearchEngineSettings()
    rag: RAGSettings = RAGSettings()
    prompts_dir: str = os.path.join(os.path.dirname(__file__), "prompts")
    domains_trust_path: str = os.path.join(os.path.dirname(__file__), "domains_trust.json")

settings = Settings()
