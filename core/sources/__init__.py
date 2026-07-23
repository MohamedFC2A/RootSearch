from core.sources.searxng import SearXNGClient, SearXNGResult
from core.sources.ddg import DuckDuckGoClient
from core.sources.academic import HeterogeneousDataExtractor
from core.sources.structured import StructuredDataExtractor

__all__ = [
    "SearXNGClient",
    "SearXNGResult",
    "DuckDuckGoClient",
    "HeterogeneousDataExtractor",
    "StructuredDataExtractor"
]
