"""
Fucken Search - Web Interface (FastAPI)
الواجهة الإلكترونية الخارقة
"""

import asyncio
import json
import os
import sys
import traceback
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# إضافة المسار الحالي
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import config
from main import FuckenSearch

app = FastAPI(
    title="Fucken Search",
    description="Deep Search Engine - البحث الخارق في أعماق الإنترنت",
    version="2.0.0",
)

# إعداد القوالب والملفات الثابتة
templates_path = os.path.join(os.path.dirname(__file__), "templates")
static_path = os.path.join(os.path.dirname(__file__), "static")

templates = Jinja2Templates(directory=templates_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# تخزين مؤقت للنتائج (LRU بسيط)
search_cache: dict = {}
cache_size = 50


def _cache_put(key: str, value: dict):
    """إضافة إلى الكاش مع إزالة الأقدم عند الامتلاء"""
    if len(search_cache) >= cache_size:
        oldest = next(iter(search_cache))
        del search_cache[oldest]
    search_cache[key] = value


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """الصفحة الرئيسية"""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "title": "Fucken Search"}
    )


@app.get("/api/search")
async def api_search(
    q: str = Query(..., min_length=1, max_length=500, description="استعلام البحث"),
    deep: bool = Query(True, description="تحليل عميق أم بحث سريع"),
    page: int = Query(1, ge=1, description="رقم الصفحة"),
    nocache: bool = Query(False, description="تجاهل الكاش"),
):
    """API البحث"""
    q = q.strip()
    if not q:
        return JSONResponse({"error": "يرجى إدخال استعلام البحث", "status": "error"}, status_code=400)

    # فحص الكاش (إلا إذا طلب المستخدم بحثاً جديداً)
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
            "pagination": {
                "page": page,
                "total": report.get("total_results", 0),
                "per_page": 20,
            }
        }
        _cache_put(cache_key, response_data)
        return JSONResponse(response_data)

    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"[API ERROR] {err_trace}") # Log the error securely
        return JSONResponse({
            "error": "حدث خطأ غير متوقع أثناء البحث.",
            "status": "error",
            "query": q,
        }, status_code=500)


@app.get("/api/search/stream")
async def api_search_stream(
    q: str = Query(..., min_length=1, max_length=500, description="استعلام البحث"),
    deep: bool = Query(True, description="تحليل عميق أم بحث سريع"),
    nocache: bool = Query(False, description="تجاهل الكاش"),
):
    """بث مباشر ديناميكي لعملية البحث - يبث حالة كل محرك فور اكتماله"""
    q = q.strip()
    cache_key = f"{q.lower()}:{deep}:1"

    if not nocache and cache_key in search_cache:
        cached_report = search_cache[cache_key]["data"]
        async def cached_event_generator():
            try:
                yield _sse("progress", {"status": "start", "message": "⚡ استرجاع نتائج البحث الفورية من الذاكرة المؤقتة..."})
                await asyncio.sleep(0.05)
                yield _sse("progress", {
                    "status": "search_done",
                    "message": "🔍 تم استرجاع النتائج المؤرشفة فورياً.",
                    "count": cached_report.get("total_results", 0),
                    "sources": cached_report.get("analysis", {}).get("statistics", {}).get("sources_used", {})
                })
                await asyncio.sleep(0.05)
                yield _sse("complete", cached_report)
            except Exception as exc:
                err = traceback.format_exc()
                print(f"[STREAM CACHE ERROR] {err}")
                yield _sse("error", {"message": "حدث خطأ أثناء استرجاع النتائج المؤقتة."})

        return StreamingResponse(
            cached_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Pragma": "no-cache",
            }
        )

    async def event_generator():
        engine: Optional[FuckenSearch] = None
        search_tasks = []
        scrape_task_objs = []
        try:
            # ـ 1 ـ بدء
            yield _sse("progress", {"status": "start", "message": "⚡ تهيئة محرك البحث الخارق..."})
            await asyncio.sleep(0.1)

            engine = FuckenSearch()

            # ـ 2 ـ الاستعلام المتوازي من كل المحركات مع بث حي
            yield _sse("progress", {"status": "searching", "message": "🌐 جاري الاستعلام المتوازي من جميع المحركات..."})

            # ربط الأسماء بالدوال
            all_engine_funcs = {
                "google":     engine.search_engine.search_google,
                "bing":       engine.search_engine.search_bing,
                "duckduckgo": engine.search_engine.search_duckduckgo,
                "wikipedia":  engine.search_engine.search_wikipedia,
                "brave":      engine.search_engine.search_brave,
                "searx":      engine.search_engine.search_searx,
            }

            # استخدام فقط المحركات المفعلة + دائماً DuckDuckGo و Wikipedia كضمان
            active_engines = set(config.search_engines) | {"duckduckgo", "wikipedia"}
            engine_funcs = {k: v for k, v in all_engine_funcs.items() if k in active_engines}

            async def run_engine(name: str, func):
                try:
                    res = await asyncio.wait_for(func(q), timeout=15.0)
                    return name, res if res else []
                except asyncio.TimeoutError:
                    return name, []
                except Exception as exc:
                    return name, []

            search_tasks = [asyncio.create_task(run_engine(name, func)) for name, func in engine_funcs.items()]

            all_results = []
            sources_counts: dict = {}

            # بث حالة كل محرك فور اكتماله
            for coro in asyncio.as_completed(search_tasks):
                name, res = await coro
                count = len(res) if res else 0
                all_results.extend(res)
                sources_counts[name] = count

                msg = f"✅ {name.capitalize()}: جُلب {count} نتيجة" if count > 0 else f"⚠️ {name.capitalize()}: لا نتائج / محجوب"
                yield _sse("progress", {
                    "status": "engine_done",
                    "engine": name,
                    "count": count,
                    "message": msg,
                })

            # ـ 3 ـ إزالة التكرار وترتيب
            all_results = engine.search_engine.deduplicate_and_sort(all_results)
            total = len(all_results)

            yield _sse("progress", {
                "status": "search_done",
                "message": f"🔍 تم رصد {total} نتيجة فريدة من {len(sources_counts)} محرك",
                "count": total,
                "sources": sources_counts,
            })
            await asyncio.sleep(0.1)

            if not all_results:
                yield _sse("progress", {"status": "empty", "message": "⚠️ لم يتم العثور على نتائج لهذا الاستعلام."})
                return

            # ـ 4 ـ تسليق المواقع (إذا Deep)
            enriched = []
            if deep:
                to_scrape = sorted(all_results, key=lambda r: r.relevance_score, reverse=True)[:15]
                yield _sse("progress", {
                    "status": "scraping_start",
                    "message": f"🕷️ جاري تسليق {len(to_scrape)} موقع...",
                    "total": len(to_scrape),
                })

                async def scrape_one(res):
                    try:
                        scraped = await asyncio.wait_for(engine.scraper.scrape_url(res.url), timeout=12.0)
                        if scraped and scraped.get("content"):
                            res.content = scraped["content"]
                            res.metadata["scraped"] = True
                            res.metadata["word_count"] = scraped.get("word_count", 0)
                            res.metadata["extraction_method"] = scraped.get("extraction_method", "trafilatura")
                            res.metadata["resolved_ip"] = scraped.get("resolved_ip", "")
                    except Exception:
                        pass
                    return res

                scrape_task_objs = [asyncio.create_task(scrape_one(r)) for r in to_scrape]
                scraped_count = 0

                for coro in asyncio.as_completed(scrape_task_objs):
                    res = await coro
                    scraped_count += 1
                    enriched.append(res)
                    ok = res.metadata.get("scraped", False)
                    wc = res.metadata.get("word_count", 0)

                    domain = ""
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(res.url).netloc
                    except Exception:
                        pass

                    yield _sse("progress", {
                        "status": "scraping_progress",
                        "scraped_count": scraped_count,
                        "total": len(to_scrape),
                        "url": res.url,
                        "title": res.title,
                        "source": res.source,
                        "domain": domain,
                        "success": ok,
                        "word_count": wc,
                        "message": f"{'✅' if ok else '❌'} {'تم مسح: ' if ok else 'فشل مسح: '}{res.title[:50]}",
                    })
            else:
                enriched = all_results

            # ـ 5 ـ التجميع والتحليل
            yield _sse("progress", {"status": "analyzing", "message": "🧠 تحليل النصوص وبناء التقرير الشامل..."})

            final_report = await engine.aggregator.aggregate(enriched, q)
            await engine.close()
            engine = None

            # حفظ في الكاش لضمان استرجاعه فورياً عند الريفرش
            response_data = {
                "status": "success",
                "query": q,
                "deep_search": deep,
                "timestamp": datetime.now().isoformat(),
                "data": final_report,
                "pagination": {
                    "page": 1,
                    "total": final_report.get("total_results", 0),
                    "per_page": 20,
                }
            }
            _cache_put(cache_key, response_data)

            # ـ 6 ـ الإرسال النهائي
            yield _sse("complete", final_report)

        except Exception as exc:
            err = traceback.format_exc()
            print(f"[STREAM ERROR] {err}")
            yield _sse("error", {"message": "حدث خطأ غير متوقع أثناء عملية البحث."})
        finally:
            # إلغاء كافة مهام البحث والتسليق الجارية فور انقطاع الاتصال لمنع تداخل العمليات وحجز الموارد
            for t in search_tasks:
                if not t.done():
                    t.cancel()
            for t in scrape_task_objs:
                if not t.done():
                    t.cancel()
            if engine:
                try:
                    await engine.close()
                except Exception:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        }
    )

def _sse(event: str, data: dict) -> str:
    """تنسيق رسالة SSE بشكل صحيح"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/keyword/explain")
async def api_explain_keyword(
    q: str = Query(..., description="موضوع البحث الحالي"),
    kw: str = Query(..., description="الكلمة المفتاحية المراد تفسيرها"),
):
    """API لتفسير الكلمات والشخصيات المجهولة سياقياً"""
    q = q.strip()
    kw = kw.strip()
    if not q or not kw:
        return JSONResponse({"error": "معاملات ناقصة", "status": "error"}, status_code=400)
        
    try:
        from core.analyzer import AIAnalyzer
        analyzer = AIAnalyzer()
        
        # استرجاع النتائج من الكاش لسرعة استخلاص السياق المحلي
        results_list = []
        for cache_key, val in search_cache.items():
            if cache_key.startswith(q.lower()):
                results_list = val.get("data", {}).get("results", [])
                break
                
        explanation = await analyzer.explain_keyword(q, kw, results_list)
        return JSONResponse({
            "status": "success",
            "query": q,
            "keyword": kw,
            "explanation": explanation
        })
    except Exception as e:
        import traceback
        print(f"[EXPLAIN KEYWORD ERROR] {traceback.format_exc()}")
        return JSONResponse({
            "error": "فشل تفسير الكلمة",
            "status": "error"
        }, status_code=500)


@app.get("/api/status")
async def api_status():
    """حالة الخادم"""
    return JSONResponse({
        "status": "running",
        "version": "2.0.0",
        "name": "Fucken Search",
        "engines": config.search_engines,
        "deep_analysis": config.use_ai_analysis,
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/search")
async def search_page():
    """توجيه أي طلب لصفحة البحث إلى الصفحة الرئيسية لتفادي المشاكل"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


def start():
    """تشغيل خادم الويب"""
    print(f"""
{'🔥' * 40}
🔥  FUCKEN SEARCH v2.0 — Web Interface
🔥  الخادم: http://{config.host}:{config.port}
🔥  المحلي: http://localhost:{config.port}
{'🔥' * 40}
    """)

    uvicorn.run(
        "web.app:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info",
    )


if __name__ == "__main__":
    start()
