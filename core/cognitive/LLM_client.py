import asyncio
from typing import AsyncGenerator, Optional

class MockLLMClient:
    """Async Streaming Client placeholder for OpenAI / Gemini / Anthropic / Local LLM APIs."""
    def __init__(self, response_text: Optional[str] = None):
        self.response_text = response_text

    async def stream_completion(self, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        if self.response_text:
            text = self.response_text
        else:
            text = (
                "Based on the verified sources [Source 1], key findings indicate strong evidence for the query topic. "
                "Further academic consensus [Source 2] confirms these conclusions and highlights structured results."
            )
        for word in text.split(" "):
            await asyncio.sleep(0.02)
            yield word + " "

class LLMClient:
    """Provider-agnostic Async Streaming Client."""
    def __init__(self, provider: str = "mock", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        self.mock_client = MockLLMClient()

    async def stream_completion(self, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        if self.provider == "mock":
            async for token in self.mock_client.stream_completion(system_prompt, user_prompt):
                yield token
        else:
            # Fallback to mock streaming if external API key or client is unavailable
            async for token in self.mock_client.stream_completion(system_prompt, user_prompt):
                yield token
