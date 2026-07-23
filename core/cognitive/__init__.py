from core.cognitive.prompt_manager import PromptManager
from core.cognitive.LLM_client import MockLLMClient, LLMClient
from core.cognitive.synthesizer import GroundedAISynthesizer
from core.cognitive.legacy import (
    DomainCredibilityScorer,
    PhysicalSanityGate,
    DualHeadSemanticGuard,
    AsynchronousMicroJudge,
    CognitiveReasoningPipeline,
    MathematicalConsensusSolver,
    SmartSourceFilter
)

__all__ = [
    "PromptManager",
    "MockLLMClient",
    "LLMClient",
    "GroundedAISynthesizer",
    "DomainCredibilityScorer",
    "PhysicalSanityGate",
    "DualHeadSemanticGuard",
    "AsynchronousMicroJudge",
    "CognitiveReasoningPipeline",
    "MathematicalConsensusSolver",
    "SmartSourceFilter"
]
