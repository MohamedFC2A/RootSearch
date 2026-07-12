"""
RootSearch - Web Interface (FastAPI)
الواجهة الإلكترونية — مع Live Search Tree SSE pipeline (5 stages)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import config
from main import FuckenSearch

app = FastAPI(
    title="RootSearch",
    description="Deep Search Engine — البحث في أعماق الإنترنت",
    version="3.0.0",
)

templates_path = os.path.join(os.path.dirname(__file__), "templates")
static_path = os.path.join(os.path.dirname(__file__), "static")

templates = Jinja2Templates(directory=templates_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# ─────────────────────────────────────────────
#  LRU CACHE
# ─────────────────────────────────────────────

search_cache: Dict[str, dict] = {}
_CACHE_SIZE = 50


def _cache_put(key: str, value: dict) -> None:
    if len(search_cache) >= _CACHE_SIZE:
        oldest = next(iter(search_cache))
        del search_cache[oldest]
    search_cache[key] = value


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
    deep: bool = Query(True),
    page: int = Query(1, ge=1),
    nocache: bool = Query(False),
):
    q = q.strip()
    if not q:
        return JSONResponse({"error": "يرجى إدخال استعلام البحث", "status": "error"}, status_code=400)

    cache_key = f"{q.lower()}:{deep}:{page}"
    if not nocache and cache_key in search_cache:
        return JSONResponse(search_cache[cache_key])

    try:
        engine = FuckenSearch()
        try:
            report = await engine.deep_search(q, deep_analysis=deep)
        finally:
            await engine.close()

        response_data = {
            "status": "success",
            "query": q,
            "deep_search": deep,
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
    deep: bool = Query(True),
    nocache: bool = Query(False),
):
    """
    5-stage Live Search Tree SSE stream:
      [Trigger] → [Source Discovery] → [Extraction] → [Semantic Analysis] → [Verification]
    Each stage emits tree_node / node_status_update / tree_edge events consumed by the frontend.
    """
    q = q.strip()
    cache_key = f"{q.lower()}:{deep}:1"

    # ── Serve from cache immediately ──
    if not nocache and cache_key in search_cache:
        async def _cached():
            yield _tree_node("trigger", "trigger", "success", "Query triggered (cached)", None)
            yield _sse("progress", {"status": "start", "message": "⚡ استرجاع من الذاكرة المؤقتة..."})
            await asyncio.sleep(0.05)
            cached = search_cache[cache_key]["data"]
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
                "label": f'Query: "{q}"',
                "parentId": None,
            }))

            engine = FuckenSearch(on_event=on_event)

            # ── STAGE 1: Source Discovery ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "source_discovery",
                "stage": "source_discovery",
                "status": "pending",
                "label": "Discovering sources...",
                "parentId": "trigger",
            }))

            all_engine_funcs = {
                "google":     engine.search_engine.search_google,
                "bing":       engine.search_engine.search_bing,
                "duckduckgo": engine.search_engine.search_duckduckgo,
                "wikipedia":  engine.search_engine.search_wikipedia,
                "brave":      engine.search_engine.search_brave,
                "searx":      engine.search_engine.search_searx,
            }
            active_engines = set(config.search_engines) | {"duckduckgo", "wikipedia"}
            engine_funcs = {k: v for k, v in all_engine_funcs.items() if k in active_engines}

            async def run_engine(name: str, func):
                event_queue.put_nowait(("tree_node", {
                    "nodeId": f"engine_{name}",
                    "stage": "source_discovery",
                    "status": "fetching",
                    "label": f"Querying {name.capitalize()}...",
                    "parentId": "source_discovery",
                }))
                try:
                    res = await asyncio.wait_for(func(q), timeout=15.0)
                    res = res or []
                    event_queue.put_nowait(("node_status_update", {
                        "nodeId": f"engine_{name}",
                        "status": "success" if res else "failed",
                        "label": (f"{name.capitalize()}: {len(res)} results"
                                  if res else f"{name.capitalize()}: no results"),
                        "metadata": {"count": len(res)},
                    }))
                    return name, res
                except asyncio.TimeoutError:
                    event_queue.put_nowait(("node_status_update", {
                        "nodeId": f"engine_{name}", "status": "failed",
                        "label": f"{name.capitalize()}: timed out",
                    }))
                    return name, []
                except Exception as exc:
                    event_queue.put_nowait(("node_status_update", {
                        "nodeId": f"engine_{name}", "status": "failed",
                        "label": f"{name.capitalize()}: {type(exc).__name__}",
                    }))
                    return name, []

            search_tasks = [asyncio.create_task(run_engine(n, f)) for n, f in engine_funcs.items()]

            all_results = []
            sources_counts: Dict[str, int] = {}

            for coro in asyncio.as_completed(search_tasks):
                name, res = await coro
                all_results.extend(res)
                sources_counts[name] = len(res)

            # GraphCrawler scoring
            from core.search_engine import GraphCrawler
            crawler = GraphCrawler(query=q, max_nodes=120, on_event=on_event)
            prioritised = crawler.prioritise(all_results)
            all_results = engine.search_engine.deduplicate_and_sort(prioritised)
            total = len(all_results)

            event_queue.put_nowait(("node_status_update", {
                "nodeId": "source_discovery",
                "status": "success" if total else "failed",
                "label": f"Discovered {total} unique sources from {len(sources_counts)} engines",
                "metadata": {"total": total, "sources": sources_counts},
            }))
            event_queue.put_nowait(("progress", {
                "status": "search_done",
                "count": total,
                "sources": sources_counts,
                "message": f"🔍 {total} نتيجة فريدة",
            }))

            if not all_results:
                event_queue.put_nowait(("progress", {"status": "empty", "message": "⚠️ لم تُعثر على نتائج."}))
                return

            # ── STAGE 2: Extraction ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "extraction",
                "stage": "extraction",
                "status": "pending",
                "label": "Extracting page content...",
                "parentId": "source_discovery",
            }))

            enriched = []
            if deep:
                to_scrape = sorted(all_results, key=lambda r: r.relevance_score, reverse=True)[:15]
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction",
                    "status": "fetching",
                    "label": f"Scraping {len(to_scrape)} pages...",
                    "metadata": {"total": len(to_scrape)},
                }))

                async def scrape_one(res):
                    from urllib.parse import urlparse as _up
                    domain = _up(res.url).netloc or res.url
                    nid = f"scrape_{domain}"
                    event_queue.put_nowait(("tree_node", {
                        "nodeId": nid,
                        "stage": "extraction",
                        "status": "pending",
                        "label": domain,
                        "parentId": "extraction",
                    }))
                    try:
                        scraped = await asyncio.wait_for(
                            engine.scraper.scrape_url(res.url, fallback_snippet=res.snippet),
                            timeout=12.0
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
                                "label": f"Extracted {scraped.get('word_count', 0):,} words",
                                "metadata": res.metadata,
                            }))
                        else:
                            event_queue.put_nowait(("node_status_update", {
                                "nodeId": nid,
                                "status": "failed",
                                "label": f"Extraction failed — {domain}",
                                "metadata": {"can_retry": True},
                            }))
                    except Exception:
                        event_queue.put_nowait(("node_status_update", {
                            "nodeId": nid, "status": "failed",
                            "label": f"Timeout — {domain}",
                            "metadata": {"can_retry": True},
                        }))
                    return res

                scrape_tasks = [asyncio.create_task(scrape_one(r)) for r in to_scrape]
                for coro in asyncio.as_completed(scrape_tasks):
                    enriched.append(await coro)

                scraped_ok = sum(1 for r in enriched if r.metadata.get("scraped"))
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction",
                    "status": "success" if scraped_ok else "failed",
                    "label": f"Extracted {scraped_ok}/{len(to_scrape)} pages",
                    "metadata": {"ok": scraped_ok, "total": len(to_scrape)},
                }))
            else:
                enriched = all_results
                event_queue.put_nowait(("node_status_update", {
                    "nodeId": "extraction", "status": "success",
                    "label": "Snippet-only mode (deep=false)",
                }))

            # ── STAGE 3: Semantic Analysis ──
            event_queue.put_nowait(("tree_node", {
                "nodeId": "semantic_analysis",
                "stage": "semantic_analysis",
                "status": "pending",
                "label": "Running semantic analysis...",
                "parentId": "extraction",
            }))
            event_queue.put_nowait(("progress", {"status": "analyzing", "message": "🧠 تحليل النصوص..."}))

            final_report = await engine.aggregator.aggregate(enriched, q)
            await engine.close()
            engine = None

            event_queue.put_nowait(("node_status_update", {
                "nodeId": "semantic_analysis",
                "status": "success",
                "label": f"BM25 ranked {final_report.get('total_results', 0)} results",
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
                "label": "Verifying & building report...",
                "parentId": "semantic_analysis",
            }))

            response_data = {
                "status": "success",
                "query": q,
                "deep_search": deep,
                "timestamp": datetime.now().isoformat(),
                "data": final_report,
                "pagination": {"page": 1, "total": final_report.get("total_results", 0), "per_page": 20},
            }
            _cache_put(cache_key, response_data)

            event_queue.put_nowait(("node_status_update", {
                "nodeId": "verification",
                "status": "success",
                "label": "Report ready ✓",
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
        for ck, val in search_cache.items():
            if ck.startswith(q.lower()):
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
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/search")
async def search_page():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


def start():
    print(f"""
{'─' * 50}
  RootSearch v3.0 — Live Search Tree Edition
  Server: http://{config.host}:{config.port}
  Local:  http://localhost:{config.port}
{'─' * 50}
    """)
    uvicorn.run("web.app:app", host=config.host, port=config.port,
                reload=config.debug, log_level="info")


if __name__ == "__main__":
    start()
