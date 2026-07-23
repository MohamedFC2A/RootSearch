"""
███████╗██╗░░░██╗░█████╗░██╗░░██╗███████╗███╗░░██╗
██╔════╝██║░░░██║██╔══██╗██║░██╔╝██╔════╝████╗░██║
█████╗░░██║░░░██║██║░░╚═╝█████═╝░█████╗░░██╔██╗██║
██╔══╝░░██║░░░██║██║░░██╗██╔═██╗░██╔══╝░░██║╚████║
██║░░░░░╚██████╔╝╚█████╔╝██║░╚██╗███████╗██║░╚███║
╚═╝░░░░░░╚═════╝░░╚════╝░╚═╝░░╚═╝╚══════╝╚═╝░░╚══╝

███████╗███████╗░█████╗░██████╗░░█████╗░██╗░░██╗
██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║░░██║
█████╗░░█████╗░░██║░░╚═╝██████╔╝██║░░╚═╝███████║
██╔══╝░░██╔══╝░░██║░░██╗██╔══██╗██║░░██╗██╔══██║
██║░░░░░██║░░░░░╚█████╔╝██║░░██║╚█████╔╝██║░░██║
╚═╝░░░░░╚═╝░░░░░░╚════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝

RootSearch - Deep Search Engine & Next-Gen Meta-Search AI Pipeline
"""

import asyncio
import sys
import os
import logging
from typing import Optional, AsyncGenerator, List, Dict, Any

# إضافة المسار الحالي
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from core.search_engine import SearchEngine
from core.scraper import DeepScraper
from core.aggregator import ResultAggregator, SourceTrustEvaluator
from core.sources.searxng import SearXNGClient
from core.sources.ddg import DuckDuckGoClient
from core.sources.academic import HeterogeneousDataExtractor
from core.fetching.engine import ResilientFetchEngine
from core.rag.chunker import SemanticChunker, ContextOrderingEngine
from core.rag.vector_store import InMemoryVectorStore
from core.rag.reranker import SemanticReranker
from core.cognitive.prompt_manager import PromptManager
from core.cognitive.LLM_client import MockLLMClient
from core.cognitive.synthesizer import GroundedAISynthesizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RootSearch.Pipeline")

class RootSearchPipeline:
    """Enterprise Next-Gen Async Streaming Pipeline."""

    def __init__(self):
        self.searxng_client = SearXNGClient(instance_urls=["https://searx.be", "https://searx.space"])
        self.ddg_client = DuckDuckGoClient()
        self.evaluator = SourceTrustEvaluator()
        self.fetch_engine = ResilientFetchEngine(max_concurrency=8, timeout=8.0)
        self.chunker = SemanticChunker(target_chunk_size=300, overlap=40)
        self.vector_store = InMemoryVectorStore()
        self.reranker = SemanticReranker()
        self.prompt_manager = PromptManager()
        self.synthesizer = GroundedAISynthesizer(self.prompt_manager)
        self.llm_client = MockLLMClient()

    async def execute_search_stream(self, query: str) -> AsyncGenerator[str, None]:
        logger.info(f"Initiating pipeline for query: '{query}'")

        # Step 1: Multi-Engine Concurrent Gathering
        searxng_task = asyncio.create_task(self.searxng_client.search(query))
        ddg_task = asyncio.create_task(self.ddg_client.search(query))
        arxiv_task = asyncio.create_task(HeterogeneousDataExtractor.fetch_arxiv_papers(query))

        s_results, d_results, a_results = await asyncio.gather(
            searxng_task, ddg_task, arxiv_task, return_exceptions=True
        )

        raw_results = []
        if isinstance(s_results, list):
            for r in s_results:
                if hasattr(r, "dict"):
                    raw_results.append(r.dict())
                elif hasattr(r, "model_dump"):
                    raw_results.append(r.model_dump())
                elif isinstance(r, dict):
                    raw_results.append(r)
        if isinstance(d_results, list):
            raw_results.extend(d_results)
        if isinstance(a_results, list):
            raw_results.extend(a_results)

        # Step 2: Authority & Domain Quality Filtering
        filtered_sources = self.evaluator.filter_and_rank(raw_results)[:8]

        # Step 3: Resilient Parallel Content Fetching & Boilerplate Removal
        fetched_docs = await self.fetch_engine.fetch_all(filtered_sources)

        # Step 4: Semantic Chunking
        all_chunks = []
        for doc in fetched_docs:
            chunks = self.chunker.chunk_document(doc)
            all_chunks.extend(chunks)

        if not all_chunks:
            yield "No high-quality sources could be fetched to answer your query."
            return

        # Step 5: In-Memory Embedding & Similarity Search
        self.vector_store.build_index(all_chunks)
        top_similar_chunks = [item[0] for item in self.vector_store.similarity_search(query, top_k=12)]

        # Step 6: Cross-Encoder Semantic Reranking
        reranked_chunks = self.reranker.rerank(query, top_similar_chunks, top_n=5)

        # Step 7: U-Shape Context Ordering ("Lost in the Middle" Mitigation)
        final_ordered_chunks = ContextOrderingEngine.apply_u_shaped_ordering(reranked_chunks)

        # Step 8: Decoupled Async Grounded Streaming AI Synthesis
        async for chunk in self.synthesizer.generate_synthesis_stream(
            query, final_ordered_chunks, self.llm_client
        ):
            yield chunk


class RootSearch:
    """المحرك الرئيسي — ينسق جميع المكونات مع دعم on_event للشجرة الحية"""

    def __init__(self, on_event=None):
        self.search_engine = SearchEngine(on_event=on_event)
        self.scraper = DeepScraper(on_event=on_event)
        self.aggregator = ResultAggregator(on_event=on_event)
        self.pipeline = RootSearchPipeline()
    
    async def deep_search(self, query: str, model: str = "fathom_s1", deep_analysis: bool = True, k_trusted: bool = False) -> dict:
        """
        البحث العميق الخارق
        """
        print(f"\n[*] RootSearch: بدء البحث العميق...")
        print(f"[*] الاستعلام: {query}")
        print(f"[*]  النموذج: {model}")
        print(f"[*]  الوضع: {'تحليل عميق' if deep_analysis else 'بحث سريع'}")
        print(f"[*]  التحقق الفائق (K-Trusted): {k_trusted}")
        
        # 1. البحث في جميع محركات البحث
        print(f"\n[*] البحث في {len(config.search_engines)} محركات بحث...")
        results = await self.search_engine.search_all(query, model=model, k_trusted=k_trusted)
        print(f"[*] تم العثور على {len(results)} نتيجة (قبل التصفية)")
        
        if not results:
            return {
                'query': query,
                'results': [],
                'total_results': 0,
                'message': 'لم يتم العثور على نتائج. جرب تغيير صياغة الاستعلام.'
            }
        
        # 1.5 تصفية وفحص المصادر بالذكاء الاصطناعي لتأكيد ارتباطها وجدواها قبل الجلب
        if deep_analysis:
            print(f"[*] تصفية وتقييم مصادر البحث بالذكاء الاصطناعي...")
            max_seeds = 25 if model == "fathom_max" else 15
            results = await self.aggregator.analyzer.filter_sources_ai(query, results, max_seeds=max_seeds)

        # 2. تسليق المحتوى (إذا كان تحليل عميق)
        if deep_analysis:
            print(f"\n[*]  تسليق المواقع واستخراج المحتوى...")
            if model == "fathom_max":
                enriched_results = await self.scraper.scrape_recursive(
                    seeds=results,
                    query=query,
                    max_nodes=config.fathom_max_nodes,
                    max_depth=config.fathom_max_depth,
                    concurrency=config.fathom_max_concurrency,
                    aggregator=self.aggregator,
                    k_trusted=k_trusted
                )
            else:
                enriched_results = await self.scraper.scrape_batch(results, max_pages=config.fathom_s1_max_sources, k_trusted=k_trusted, query=query)
            print(f"[*] تم تسليق {sum(1 for r in enriched_results if r.content)} صفحة بنجاح")
        else:
            enriched_results = results
        
        # 3. تجميع وترتيب وتحليل
        print(f"\n[*] تجميع وتحليل النتائج...")
        final_report = await self.aggregator.aggregate(enriched_results, query, final_analysis=True, model=model, k_trusted=k_trusted)
        
        print(f"\n[*] اكتمل البحث العميق!")
        print(f"[*] إجمالي النتائج: {final_report['total_results']}")
        print(f"[*] التصنيفات: {', '.join(final_report.get('categories', {}).keys())}")
        
        return final_report
    
    async def quick_search(self, query: str) -> dict:
        """بحث سريع بدون تحليل عميق"""
        return await self.deep_search(query, model="fathom_s1", deep_analysis=False)
    
    async def close(self):
        """تنظيف الموارد"""
        await self.search_engine.close()
        await self.scraper.close()


def main():
    """نقطة الدخول الرئيسية - تفوض العمل لـ cli.terminal"""
    from cli.terminal import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
