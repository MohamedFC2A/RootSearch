"""
RootSearch - Web Interface (FastAPI)
الواجهة الإلكترونية — مع Live Search Tree SSE pipeline (5 stages)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import threading
import traceback
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import config
from main import FuckenSearch
from core.search_engine import engine_display_name

app = FastAPI(
    title="RootSearch",
    description="Deep Search Engine — البحث في أعماق الإنترنت",
    version="3.0.0",
)

# ───────────────────────────────────────────
#  CORS — يسمح للواجهة المستضافة على Vercel بمخاطبة
#  هذا الباك-اند المحلي عبر النفق (Tunnel).
#  افتراضيًا "*" (أي أصل)؛ يمكن تقييدها عبر متغير البيئة
#  ALLOWED_ORIGINS="https://your-app.vercel.app"
# ───────────────────────────────────────────
_origins_env = os.getenv("ALLOWED_ORIGINS", "*").strip()
_allow_origins = ["*"] if _origins_env == "*" else [
    o.strip() for o in _origins_env.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates_path = os.path.join(os.path.dirname(__file__), "templates")
static_path = os.path.join(os.path.dirname(__file__), "static")

templates = Jinja2Templates(directory=templates_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# ─────────────────────────────────
#  SHARED ENGINE POOL (non-streaming endpoint)
# ─────────────────────────────────
# The non-streaming /api/search used to build AND tear down a full FuckenSearch
# (aiohttp session + connector) on every request — no connection reuse and heavy
# per-request TLS setup. We keep one lazily-created shared instance instead.
# The streaming endpoint deliberately keeps its own per-request engine because it
# needs an isolated on_event callback per SSE connection.
_shared_engine: Optional[FuckenSearch] = None
_engine_lock = asyncio.Lock()


async def get_shared_engine() -> FuckenSearch:
    """Lazily create and return the process-wide non-streaming engine (thread/task-safe)."""
    global _shared_engine
    if _shared_engine is None:
        async with _engine_lock:
            if _shared_engine is None:
                _shared_engine = FuckenSearch()
    return _shared_engine


@app.on_event("shutdown")
async def _shutdown_shared_engine() -> None:
    global _shared_engine
    if _shared_engine is not None:
        try:
            await _shared_engine.close()
        except Exception:
            pass
        finally:
            _shared_engine = None
    
    # Close AIAnalyzer global session
    try:
        from core.analyzer import close_global_session
        await close_global_session()
    except Exception:
        pass

# ─────────────────────────────────────────────
#  LRU CACHE
# ─────────────────────────────────────────────

search_cache: "OrderedDict[str, tuple]" = OrderedDict()  # key -> (value, expires_at)
_CACHE_SIZE = 128
_CACHE_TTL = 1800.0  # 30 minutes
_cache_lock = threading.Lock()


def _cache_get(key: str) -> Optional[dict]:
    """Return a live cache entry (moving it to MRU) or None if missing/expired."""
    now = time.monotonic()
    with _cache_lock:
        entry = search_cache.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < now:
            search_cache.pop(key, None)
            return None
        search_cache.move_to_end(key)  # mark most-recently-used
        return value


def _cache_put(key: str, value: dict) -> None:
    """Insert/refresh an entry, evicting the least-recently-used when full."""
    now = time.monotonic()
    with _cache_lock:
        if key in search_cache:
            search_cache.move_to_end(key)
        search_cache[key] = (value, now + _CACHE_TTL)
        while len(search_cache) > _CACHE_SIZE:
            search_cache.popitem(last=False)  # evict LRU


def format_scary_count_ar(n: int) -> str:
    if n is None or n < 0:
        return "0"
    return f"{n:,}"


# ─────────────────────────────────────────────
#  SSE HELPER
# ─────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Format an SSE message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _tree_node(
    node_id: str,
    stage: str,
    status: str,
    label: str,
    parent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Emit a tree_node SSE event (creates a new node in the Live Tree)."""
    payload: Dict[str, Any] = {
        "nodeId": node_id,
        "stage": stage,
        "status": status,
        "label": label,
    }
    if parent_id:
        payload["parentId"] = parent_id
    if metadata:
        payload["metadata"] = metadata
    return _sse("tree_node", payload)


def _node_update(
    node_id: str,
    status: str,
    label: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Emit a node_status_update SSE event (updates existing node state)."""
    payload: Dict[str, Any] = {
        "nodeId": node_id,
        "status": status,
        "label": label,
    }
    if metadata:
        payload["metadata"] = metadata
    return _sse("node_status_update", payload)


def _tree_edge(parent_id: str, child_id: str) -> str:
    """Emit a tree_edge SSE event (connects two nodes)."""
    return _sse("tree_edge", {"parentId": parent_id, "childId": child_id})


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"request": request, "title": "RootSearch"}
    )


@app.head("/")
async def home_head():
    return HTMLResponse(content="", status_code=200)


@app.get("/api/search")
async def api_search(
    q: str = Query(..., min_length=1, max_length=500),
    model: str = Query("fathom_s1"),
    page: int = Query(1, ge=1),
    nocache: bool = Query(False),
    k_trusted: bool = Query(False),
):
    q = q.strip()
    if not q:
        return JSONResponse({"error": "يرجى إدخال استعلام البحث", "status": "error"}, status_code=400)

    cache_key = f"{q.lower()}:{model}:{page}:{k_trusted}"
    if not nocache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return JSONResponse(cached)

    try:
        # Reuse the pooled engine (connection reuse; no per-request session teardown).
        engine = await get_shared_engine()
        report = await engine.deep_search(q, model=model, deep_analysis=True, k_trusted=k_trusted)

        response_data = {
            "status": "success",
            "query": q,
            "model": model,
            "k_trusted": k_trusted,
            "timestamp": datetime.now().isoformat(),
            "data": report,
            "pagination": {"page": page, "total": report.get("total_results", 0), "per_page": 20},
        }
        _cache_put(cache_key, response_data)
        return JSONResponse(response_data)

    except Exception:
        print(f"[API ERROR] {traceback.format_exc()}")
        return JSONResponse({"error": "حدث خطأ غير متوقع.", "status": "error", "query": q}, status_code=500)


@app.get("/api/search/stream")
async def api_search_stream(
    q: str = Query(..., min_length=1, max_length=500),
    model: str = Query("fathom_s1"),
    nocache: bool = Query(False),
    k_trusted: bool = Query(False),
):
    """
    5-stage Live Search Tree SSE stream:
      [Trigger] → [Source Discovery] → [Extraction] → [Semantic Analysis] → [Verification]
    Each stage emits tree_node / node_status_update / tree_edge events consumed by the frontend.
    """
    q = q.strip()
    cache_key = f"{q.lower()}:{model}:1:{k_trusted}"

    # ── Serve from cache immediately ──
    _cached_entry = None if nocache else _cache_get(cache_key)
    if _cached_entry is not None:
        async def _cached():
            yield _tree_node("trigger", "trigger", "success", "تم بدء الاستعلام (مسترجع من الذاكرة)", None)
            yield _sse("progress", {"status": "start", "message": "استرجاع من الذاكرة المؤقتة..."})
            await asyncio.sleep(0.05)
            cached = _cached_entry["data"]
            yield _sse("complete", cached)
        return StreamingResponse(
            _cached(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    # ── Event queue: backend → SSE generator ──
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=512)

    def on_event(event_type: str, payload: Dict[str, Any]) -> None:
        """Callback fired by SearchEngine & DeepScraper to push live events."""
        try:
            event_queue.put_nowait((event_type, payload))
        except asyncio.QueueFull:
            pass  # non-blocking; drop if queue full

    async def pipeline():
        """Run the full 5-stage search pipeline, feeding events into the queue."""
        engine: Optional[FuckenSearch] = None
        search_tasks: list = []
        scrape_tasks: list = []

        try:
            # ── STAGE 0: Trigger ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "trigger",
                "stage": "trigger",
                "status": "success",
                "label": f'الاستعلام: "{q}"',
                "parentId": None,
            }))

            engine = FuckenSearch(on_event=on_event)

            # ── STAGE 1: Source Discovery ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "source_discovery",
                "stage": "source_discovery",
                "status": "pending",
                "label": "جاري اكتشاف المصادر والمحركات...",
                "parentId": "trigger",
            }))

            from core.analyzer import AIAnalyzer
            analyzer = AIAnalyzer()
            
            # Perform query expansion (branching) with a strict 4-second timeout to prevent blocking
            subqueries = [q]  # Always include the original query
            try:
                expanded = await asyncio.wait_for(
                    analyzer.expand_query(q, model=model),
                    timeout=4.0
                )
                if expanded:
                    subqueries.extend(expanded)
            except asyncio.TimeoutError:
                print("[Query Expansion Timeout] AI query expansion took too long, proceeding with original query immediately.")
            except Exception as e:
                print(f"[Query Expansion Error] {e}")

            # سجل كامل لدوال المحركات (نفس أسماء search_all) لتوحيد
            # اختيار المصادر مع المسار غير المتدفق ومنع تلوث النتائج.
            se = engine.search_engine
            # Engine map + intent-based selection reuse the single source of truth on
            # the SearchEngine (engine_methods/select_engines), so this streaming
            # pipeline can never drift from search_all's engine list.
            all_engine_funcs = se.engine_methods()
            engine_funcs = se.select_engines(q)

            # محركات مختصرة للاستعلامات الفرعية (أفضل 3) للحد من التشعّب التوافقي.
            _primary_order = ["startpage", "duckduckgo", "wikipedia", "bing", "brave", "searx"]
            primary_engine_funcs = {
                name: engine_funcs[name]
                for name in _primary_order if name in engine_funcs
            }
            if not primary_engine_funcs:
                primary_engine_funcs = dict(list(engine_funcs.items())[:3])
            else:
                primary_engine_funcs = dict(list(primary_engine_funcs.items())[:3])

            timeout_val = 45.0 if model == "fathom_max" else 20.0

            # Emit the subquery nodes
            for idx, sq in enumerate(subqueries):
                sq_id = f"subquery_{idx}"
                event_queue.put_nowait(("tree_node", {
                    "nodeId": sq_id,
                    "stage": "source_discovery",
                    "status": "success",
                    "label": f'الاستعلام الرئيسي' if idx == 0 else f'تفريعة: "{sq}"',
                    "parentId": "trigger",
                    "metadata": {"query": sq}
                }))

            async def run_engine(sub_idx: int, sub_text: str, name: str, func):
                sq_id = f"subquery_{sub_idx}"
                engine_node_id = f"engine_{sub_idx}_{name}"
                disp = engine_display_name(name)

                event_queue.put_nowait(("tree_node", {
                    "nodeId": engine_node_id,
                    "stage": "source_discovery",
                    "status": "fetching",
                    "label": f"جاري استعلام {disp}...",
                    "parentId": sq_id,
                }))
                try:
                    res = await asyncio.wait_for(func(sub_text), timeout=timeout_val)
                    res = res or []
                    for r in res:
                        if not r.metadata:
                            r.metadata = {}
                        r.metadata["discovery_node"] = engine_node_id
                        r.metadata["subquery_idx"] = sub_idx
                        r.metadata["subquery"] = sub_text

                    event_queue.put_nowait(("node_status_update", {
                        "nodeId": engine_node_id,
                        "status": "success" if res else "failed",
                        "label": (f"{disp}: {len(res)} نتائج"
                                  if res else f"{disp}: لا توجد نتائج"),
                        "metadata": {"count": len(res)},
                    }))
                    return name, res
                except asyncio.TimeoutError:
                    event_queue.put_nowait(("node_status_update", {
                        "nodeId": engine_node_id, "status": "failed",
                        "label": f"{disp}: انتهت المهلة",
                    }))
                    return name, []
                except Exception as exc:
                    event_queue.put_nowait(("node_status_update", {
                        "nodeId": engine_node_id, "status": "failed",
                        "label": f"{disp}: خطأ {type(exc).__name__}",
                    }))
                    return name, []

            search_tasks = []
            for sub_idx, sub_text in enumerate(subqueries):
                # الاستعلام الأصلي (0) يستخدم كامل محركات النية؛
                # الاستعلامات الفرعية تستخدم أفضل 3 محركات فقط (ضبط التشعّب).
                active_funcs = engine_funcs if sub_idx == 0 else primary_engine_funcs
                for name, func in active_funcs.items():
                    task = asyncio.create_task(run_engine(sub_idx, sub_text, name, func))
                    search_tasks.append(task)

            all_results = []
            sources_counts: Dict[str, int] = {}

            for coro in asyncio.as_completed(search_tasks):
                name, res = await coro
                if k_trusted:
                    from core.k_trusted import is_domain_authorized
                    res = [r for r in res if is_domain_authorized(r.url, q)]
                all_results.extend(res)
                sources_counts[name] = sources_counts.get(name, 0) + len(res)

            # GraphCrawler scoring
            from core.search_engine import GraphCrawler
            crawler_nodes = 1000 if k_trusted else (800 if model == "fathom_max" else 300)
            crawler = GraphCrawler(query=q, max_nodes=crawler_nodes, on_event=on_event)
            prioritised = crawler.prioritise(all_results)
            if k_trusted:
                from core.k_trusted import is_domain_authorized
                prioritised = [r for r in prioritised if is_domain_authorized(r.url, q)]
            all_results = engine.search_engine.deduplicate_and_sort(prioritised)
            total = len(all_results)

            event_queue.put_nowait(("node_status_update", {
                "nodeId": "source_discovery",
                "status": "success" if total else "failed",
                "label": f"تم اكتشاف {total} مصدر فريد عبر {len(subqueries)} تفريعات استعلام",
                "metadata": {"total": total, "sources": sources_counts},
            }))
            event_queue.put_nowait(("progress", {
                "status": "search_done",
                "count": total,
                "sources": sources_counts,
                "message": f"تم العثور على {format_scary_count_ar(total)} مصدر من {len(subqueries)} تفريعات",
            }))

            if not all_results:
                event_queue.put_nowait(("progress", {"status": "empty", "message": "لم يتم العثور على نتائج."}))
                empty_report = {
                    "query": q,
                    "results": [],
                    "total_results": 0,
                    "categories": {},
                    "analysis": {
                        "summary": "لم يتم العثور على أي نتائج بحث لهذا الاستعلام.",
                        "keywords": [],
                    },
                }
                event_queue.put_nowait(("complete", empty_report))
                return

            # ── STAGE 2: Extraction ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "extraction",
                "stage": "extraction",
                "status": "pending",
                "label": "جاري استخراج محتوى الصفحات...",
                "parentId": "source_discovery",
            }))

            enriched = []
            if model == "fathom_max":
                # Fathom Max (Abyss Engine): Deep recursive crawling with live link tracing
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction",
                    "status": "fetching",
                    "label": "محرك الأعماق (Abyss Engine): تشغيل زحف متكرر متعدد الطبقات...",
                    "metadata": {"model": "fathom_max"}
                }))

                max_nodes = 250 if k_trusted else config.fathom_max_nodes
                enriched = await engine.scraper.scrape_recursive(
                    seeds=all_results,
                    query=q,
                    max_nodes=max_nodes,
                    max_depth=config.fathom_max_depth,
                    concurrency=config.fathom_max_concurrency,
                    aggregator=engine.aggregator,
                    k_trusted=k_trusted
                )
                
                scraped_ok = sum(1 for r in enriched if r.metadata.get("scraped"))
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction",
                    "status": "success" if scraped_ok else "failed",
                    "label": f"نجح الزحف المتكرر في استخراج {scraped_ok} صفحة بنجاح",
                    "metadata": {"ok": scraped_ok, "total": len(enriched)}
                }))
            else:
                # Fathom S1 (Lightning Engine): Highly concurrent shallow crawling
                s1_max = 50 if k_trusted else config.fathom_s1_max_sources
                to_scrape = sorted(all_results, key=lambda r: r.relevance_score, reverse=True)[:s1_max]
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction",
                    "status": "fetching",
                    "label": f"محرك البرق (Lightning Engine): استخراج {len(to_scrape)} صفحة بالتوازي...",
                    "metadata": {"model": "fathom_s1"}
                }))

                async def scrape_one(res):
                    from urllib.parse import urlparse as _up
                    domain = _up(res.url).netloc or res.url
                    nid = engine.scraper._get_node_id(res.url)
                    parent_id = res.metadata.get("discovery_node", "extraction") if res.metadata else "extraction"
                    event_queue.put_nowait(("tree_node", {
                        "nodeId": nid,
                        "stage": "extraction",
                        "status": "pending",
                        "label": domain,
                        "parentId": parent_id,
                    }))
                    try:
                        scraped = await asyncio.wait_for(
                            engine.scraper.scrape_url(res.url, fallback_snippet=res.snippet),
                            timeout=6.0
                        )
                        if scraped and scraped.get("content"):
                            res.content = scraped["content"]
                            res.metadata.update({
                                "scraped": True,
                                "word_count": scraped.get("word_count", 0),
                                "extraction_method": scraped.get("extraction_method", "trafilatura"),
                                "resolved_ip": scraped.get("resolved_ip", ""),
                                "cb_state": scraped.get("cb_state", "closed"),
                            })
                            event_queue.put_nowait(("node_status_update", {
                                "nodeId": nid,
                                "status": "success",
                                "label": f"تم استخراج {scraped.get('word_count', 0):,} كلمة",
                                "metadata": res.metadata,
                            }))
                        else:
                            event_queue.put_nowait(("node_status_update", {
                                "nodeId": nid,
                                "status": "failed",
                                "label": f"فشل استخراج المحتوى — {domain}",
                            }))
                    except Exception:
                        event_queue.put_nowait(("node_status_update", {
                            "nodeId": nid, "status": "failed",
                            "label": f"انتهت المهلة — {domain}",
                        }))
                    return res

                scrape_tasks = [asyncio.create_task(scrape_one(r)) for r in to_scrape]
                for coro in asyncio.as_completed(scrape_tasks):
                    res = await coro
                    enriched.append(res)
                    # State Hydration for S1
                    try:
                        scraped_so_far = [r for r in enriched if r.metadata.get("scraped")]
                        if scraped_so_far:
                            report = await engine.aggregator.aggregate(scraped_so_far, q, final_analysis=False, k_trusted=k_trusted)
                            event_queue.put_nowait(("partial_results", report))
                    except Exception as ae:
                        print(f"[Hydration S1 Error] {ae}")

                scraped_ok = sum(1 for r in enriched if r.metadata.get("scraped"))
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction",
                    "status": "success" if scraped_ok else "failed",
                    "label": f"تم استخراج {scraped_ok}/{len(to_scrape)} صفحة",
                    "metadata": {"ok": scraped_ok, "total": len(to_scrape)},
                }))

            # ── STAGE 3: Semantic Analysis ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "semantic_analysis",
                "stage": "semantic_analysis",
                "status": "pending",
                "label": "جاري تشغيل التحليل الدلالي والتصنيف...",
                "parentId": "extraction",
            }))
            event_queue.put_nowait(("progress", {"status": "analyzing", "message": "تحليل النصوص دلالياً..."}))

            # Final Aggregation with complete AI Summary report
            final_report = await engine.aggregator.aggregate(enriched, q, final_analysis=True, model=model, k_trusted=k_trusted)
            await engine.close()
            engine = None

            event_queue.put_nowait(("node_status_update", {
                "nodeId": "semantic_analysis",
                "status": "success",
                "label": f"تم ترتيب {final_report.get('total_results', 0)} نتيجة بواسطة BM25",
                "metadata": {
                    "total": final_report.get("total_results", 0),
                    "categories": list((final_report.get("categories") or {}).keys()),
                },
            }))

            # ── STAGE 4: Verification ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "verification",
                "stage": "verification",
                "status": "pending",
                "label": "جاري التحقق وصياغة التقرير...",
                "parentId": "semantic_analysis",
            }))

            response_data = {
                "status": "success",
                "query": q,
                "deep_search": model == "fathom_max",
                "timestamp": datetime.now().isoformat(),
                "data": final_report,
                "pagination": {"page": 1, "total": final_report.get("total_results", 0), "per_page": 20},
            }
            _cache_put(cache_key, response_data)

            event_queue.put_nowait(("node_status_update", {
                "nodeId": "verification",
                "status": "success",
                "label": "التقرير جاهز",
            }))

            # ── DONE ──
            event_queue.put_nowait(("complete", final_report))

        except Exception:
            print(f"[STREAM ERROR] {traceback.format_exc()}")
            event_queue.put_nowait(("error", {"message": "حدث خطأ غير متوقع."}))
        finally:
            for t in search_tasks:
                if not t.done():
                    t.cancel()
            for t in scrape_tasks:
                if not t.done():
                    t.cancel()
            if engine:
                try:
                    await engine.close()
                except Exception:
                    pass
            # Signal done
            event_queue.put_nowait(("__done__", {}))

    async def event_generator():
        pipeline_task = asyncio.create_task(pipeline())
        try:
            while True:
                try:
                    event_type, payload = await asyncio.wait_for(
                        event_queue.get(), timeout=60.0
                    )
                except asyncio.TimeoutError:
                    yield _sse("progress", {"status": "heartbeat", "message": "..."})
                    continue

                if event_type == "__done__":
                    break

                yield _sse(event_type, payload)
        finally:
            if not pipeline_task.done():
                pipeline_task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )


@app.get("/api/keyword/explain")
async def api_explain_keyword(
    q: str = Query(...),
    kw: str = Query(...),
):
    q, kw = q.strip(), kw.strip()
    if not q or not kw:
        return JSONResponse({"error": "معاملات ناقصة", "status": "error"}, status_code=400)
    try:
        from core.analyzer import AIAnalyzer
        analyzer = AIAnalyzer()
        results_list = []
        for ck in list(search_cache.keys()):
            if ck.startswith(q.lower()):
                val = _cache_get(ck)
                if val:
                    results_list = val.get("data", {}).get("results", [])
                break
        explanation = await analyzer.explain_keyword(q, kw, results_list)
        return JSONResponse({"status": "success", "query": q, "keyword": kw, "explanation": explanation})
    except Exception:
        print(f"[EXPLAIN ERROR] {traceback.format_exc()}")
        return JSONResponse({"error": "فشل تفسير الكلمة", "status": "error"}, status_code=500)


@app.get("/api/status")
async def api_status():
    return JSONResponse({
        "status": "running",
        "version": "3.0.0",
        "name": "RootSearch",
        "engines": config.search_engines,
        "deep_analysis": config.use_ai_analysis,
        "fathom_s1_max_sources": config.fathom_s1_max_sources,
        "fathom_max_nodes": config.fathom_max_nodes,
        "fathom_max_concurrency": config.fathom_max_concurrency,
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/search")
async def search_page():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


def start():
    print(f"""
{'─' * 50}
  RootSearch Demo 1 T — Live Search Tree Edition
  Server: http://{config.host}:{config.port}
  Local:  http://localhost:{config.port}
{'─' * 50}
    """)
    uvicorn.run("web.app:app", host=config.host, port=config.port,
                reload=config.debug, log_level="info")


if __name__ == "__main__":
    start()
