import pytest
import asyncio
import json
import re
from unittest.mock import patch, MagicMock

from core.cognitive.prompt_manager import PromptManager
from core.cognitive.LLM_client import MockLLMClient, LLMClient
from core.cognitive.synthesizer import GroundedAISynthesizer
from core.rag.chunker import TextChunk

# =====================================================================
# 1. YAML & Jinja2 Template Ingestion (20+ Assertions)
# =====================================================================

@pytest.mark.parametrize("template_name", [
    "synthesis",
    "intent_classification",
    "query_expansion"
])
@pytest.mark.parametrize("query_val", [
    "quantum computing",
    "climate change mitigation",
    "deep learning transformers",
    "<script>alert('xss')</script>",
    "{{ 7 * 7 }}"
])
def test_prompt_manager_template_rendering(template_name, query_val):
    pm = PromptManager(templates_dir="config/prompts")
    context_vars = {
        "query": query_val,
        "sources": [
            TextChunk(
                chunk_id="http://test.org#chunk_0",
                source_url="http://test.org",
                source_title="Test Title",
                text="Sample chunk content text",
                token_count=20
            )
        ]
    }
    rendered = pm.render_prompt(template_name, context_vars)
    assert isinstance(rendered, dict)
    assert "system" in rendered
    assert "user" in rendered
    assert len(rendered["system"]) > 0
    assert len(rendered["user"]) > 0

def test_prompt_manager_missing_template():
    pm = PromptManager(templates_dir="config/prompts")
    with pytest.raises(FileNotFoundError):
        pm.render_prompt("non_existent_template_xyz", {})

# =====================================================================
# 2. Async Streaming Token Generator (30+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("text_payload", [
    "Word1 Word2 Word3 Word4 Word5",
    "SingleWord",
    "Line 1\nLine 2\nLine 3",
    "Special symbols: !@#$%^&*()_+",
    "Unicode Arabic content: البحث العلمي المتقدم"
])
async def test_mock_llm_client_streaming(text_payload):
    client = MockLLMClient(response_text=text_payload)
    tokens = []
    async for token in client.stream_completion("System prompt", "User prompt"):
        tokens.append(token)
    
    reconstructed = "".join(tokens).strip()
    assert reconstructed == text_payload.strip()
    assert len(tokens) == len(text_payload.split(" "))

@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["mock", "openai", "anthropic", "unknown"])
async def test_llm_client_provider_fallbacks(provider):
    client = LLMClient(provider=provider)
    tokens = []
    async for token in client.stream_completion("System", "User"):
        tokens.append(token)
    assert len(tokens) > 0

# =====================================================================
# 3. Citation Metadata Tagging (30+ Assertions)
# =====================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("source_count", [0, 1, 3, 5, 10])
async def test_grounded_ai_synthesizer_stream_metadata(source_count):
    pm = PromptManager(templates_dir="config/prompts")
    synthesizer = GroundedAISynthesizer(pm)
    llm_client = MockLLMClient(response_text="Streamed answer string with [Source 1] citations.")
    
    chunks = [
        TextChunk(
            chunk_id=f"https://source{i}.org#chunk_0",
            source_url=f"https://source{i}.org",
            source_title=f"Title {i}",
            text=f"Content for source {i}",
            token_count=30
        )
        for i in range(1, source_count + 1)
    ]

    stream_output = []
    async for chunk in synthesizer.generate_synthesis_stream("Test Query", chunks, llm_client):
        stream_output.append(chunk)

    full_response = "".join(stream_output)
    
    # Assert metadata header block existence
    assert "[[METADATA_START]]" in full_response
    assert "[[METADATA_END]]" in full_response

    # Parse metadata header JSON
    match = re.search(r'\[\[METADATA_START\]\](.*?)\[\[METADATA_END\]\]', full_response, re.DOTALL)
    assert match is not None
    meta_json = json.loads(match.group(1))
    assert "citations" in meta_json
    citations = meta_json["citations"]
    assert len(citations) == source_count
    
    for idx in range(1, source_count + 1):
        key = f"Source {idx}"
        assert key in citations
        assert citations[key]["url"] == f"https://source{idx}.org"
        assert citations[key]["title"] == f"Title {idx}"
