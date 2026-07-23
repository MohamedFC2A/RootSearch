import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any
from core.rag.chunker import TextChunk
from core.cognitive.prompt_manager import PromptManager

class GroundedAISynthesizer:
    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager

    async def generate_synthesis_stream(
        self,
        query: str,
        ordered_chunks: List[TextChunk],
        llm_client: Any
    ) -> AsyncGenerator[str, None]:
        
        # Render decoupled prompt
        prompts = self.prompt_manager.render_prompt(
            "synthesis",
            {"query": query, "sources": ordered_chunks}
        )

        # Build citation map index metadata
        citation_map = {}
        for idx, chunk in enumerate(ordered_chunks, start=1):
            citation_map[f"Source {idx}"] = {
                "title": chunk.source_title,
                "url": chunk.source_url
            }

        # Yield metadata payload header first as JSON stream marker
        yield f"[[METADATA_START]]{json.dumps({'citations': citation_map})}[[METADATA_END]]\n\n"

        # Stream response tokens from LLM client
        async for token in llm_client.stream_completion(
            system_prompt=prompts["system"],
            user_prompt=prompts["user"]
        ):
            yield token
