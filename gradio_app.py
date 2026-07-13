"""
FuckenSearch — HuggingFace Space Entry Point (Gradio)
واجهة بحث احترافية تعمل على HuggingFace Spaces مجاناً
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Dict, List, Optional

import gradio as gr

# تأكد من أن المسار صحيح عند التشغيل من أي مكان
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.search_engine import SearchEngine, SearchResult
from config import config


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

SOURCE_EMOJIS = {
    "wikipedia": "📖",
    "arxiv": "🔬",
    "pubmed": "🏥",
    "openalex": "🎓",
    "semantic_scholar": "🧠",
    "crossref": "📄",
    "core": "📚",
    "stackexchange": "💡",
    "reddit": "💬",
    "hackernews": "📰",
    "duckduckgo": "🦆",
    "duckduckgo_lite": "🦆",
    "ddg_instant": "🦆",
    "startpage": "🔍",
    "github": "🐙",
    "europepmc": "🏥",
    "base_search": "🔍",
    "core_open": "📚",
    "doaj": "📔",
    "bing": "🅱️",
    "brave": "🦁",
    "mojeek": "🌍",
    "qwant": "🇫🇷",
    "ecosia": "🌳",
    "searx": "⚙️",
    "wikidata": "🗂️",
    "openlibrary": "📕",
    "internet_archive": "🏛️",
    "jina": "⚡",
}


def get_source_emoji(source: str) -> str:
    for key, emoji in SOURCE_EMOJIS.items():
        if source.startswith(key):
            return emoji
    return "🔗"


def results_to_html(results: List[SearchResult], query: str, elapsed: float) -> str:
    """تحويل النتائج إلى HTML جميل"""
    if not results:
        return """
        <div style='text-align:center;padding:60px;color:#888;font-family:sans-serif;'>
            <div style='font-size:48px;margin-bottom:16px;'>🔍</div>
            <div style='font-size:18px;'>لم يتم العثور على نتائج. جرّب كلمات مفتاحية مختلفة.</div>
        </div>
        """

    source_counts: Dict[str, int] = {}
    for r in results:
        src = r.source.split("_")[0]
        source_counts[src] = source_counts.get(src, 0) + 1

    source_badges = " ".join(
        f"<span style='background:#e0f0ff;color:#0066cc;padding:2px 8px;border-radius:12px;"
        f"font-size:11px;margin:2px;display:inline-block;'>"
        f"{get_source_emoji(src)} {src} ({cnt})</span>"
        for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1])
    )

    html = f"""
    <div style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:900px;'>
      <div style='background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                  padding:16px 20px;border-radius:12px;margin-bottom:16px;color:white;'>
        <div style='font-size:14px;opacity:0.9;'>
          ✅ <strong>{len(results)}</strong> نتيجة في <strong>{elapsed:.1f}s</strong>
          من <strong>{len(source_counts)}</strong> مصدر
        </div>
        <div style='margin-top:8px;'>{source_badges}</div>
      </div>
    """

    for i, r in enumerate(results):
        emoji = get_source_emoji(r.source)
        score_pct = int(r.relevance_score * 100)
        score_color = "#22c55e" if score_pct > 80 else "#f59e0b" if score_pct > 60 else "#94a3b8"
        snippet = (r.snippet or "")[:300].replace("<", "&lt;").replace(">", "&gt;")
        title = (r.title or r.url).replace("<", "&lt;").replace(">", "&gt;")
        url_display = r.url[:70] + "…" if len(r.url) > 70 else r.url

        html += f"""
        <div style='background:white;border:1px solid #e2e8f0;border-radius:10px;
                    padding:16px 20px;margin-bottom:10px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.05);
                    transition:box-shadow 0.2s;'>
          <div style='display:flex;align-items:flex-start;gap:12px;'>
            <div style='font-size:22px;line-height:1;'>{emoji}</div>
            <div style='flex:1;min-width:0;'>
              <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                <a href="{r.url}" target="_blank"
                   style='color:#1a56db;text-decoration:none;font-size:15px;
                          font-weight:600;line-height:1.4;display:block;
                          max-width:85%;'>
                  {i+1}. {title}
                </a>
                <span style='background:{score_color};color:white;font-size:10px;
                             padding:2px 6px;border-radius:6px;white-space:nowrap;
                             margin-left:8px;flex-shrink:0;'>
                  {score_pct}%
                </span>
              </div>
              <div style='color:#16a34a;font-size:11px;margin:4px 0;
                          overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>
                {url_display}
              </div>
              {f'<div style="color:#475569;font-size:13px;line-height:1.6;">{snippet}</div>' if snippet else ''}
              <div style='margin-top:6px;'>
                <span style='background:#f1f5f9;color:#64748b;padding:2px 6px;
                             border-radius:4px;font-size:10px;'>
                  {r.source}
                </span>
                {f'<span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:4px;">{r.content_type}</span>' if r.content_type and r.content_type != "web" else ""}
              </div>
            </div>
          </div>
        </div>
        """

    html += "</div>"
    return html


async def _async_search(query: str, engines: List[str]) -> tuple:
    """بحث غير متزامن"""
    engine = SearchEngine()
    try:
        # تطبيق فلتر المحركات المختارة
        config.search_engines = engines
        t0 = time.time()
        results = await engine.search_all(query)
        elapsed = time.time() - t0
        return results, elapsed
    finally:
        await engine.close()


def do_search(query: str, selected_engines: List[str], num_results: int) -> str:
    """دالة البحث الرئيسية"""
    if not query or not query.strip():
        return "<div style='text-align:center;padding:40px;color:#888;'>أدخل استعلام البحث أولاً.</div>"

    if not selected_engines:
        return "<div style='text-align:center;padding:40px;color:#e11d48;'>اختر مصدراً واحداً على الأقل.</div>"

    config.results_per_engine = max(5, min(num_results // max(len(selected_engines), 1), 25))
    config.max_final_results = num_results

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results, elapsed = loop.run_until_complete(_async_search(query.strip(), selected_engines))
        loop.close()
        return results_to_html(results[:num_results], query, elapsed)
    except Exception as e:
        return f"<div style='color:#e11d48;padding:20px;border:1px solid #fca5a5;border-radius:8px;'>❌ خطأ: {str(e)}</div>"


# ─────────────────────────────────────────────
#  GRADIO UI
# ─────────────────────────────────────────────

ALL_ENGINES = [
    ("🦆 DuckDuckGo", "duckduckgo"),
    ("🔍 Startpage (Google)", "startpage"),
    ("🅱️ Bing", "bing"),
    ("🦁 Brave", "brave"),
    ("🌍 Mojeek", "mojeek"),
    ("🇫🇷 Qwant", "qwant"),
    ("🌳 Ecosia", "ecosia"),
    ("⚙️ SearXNG", "searx"),
    ("📖 Wikipedia", "wikipedia"),
    ("🗂️ Wikidata", "wikidata"),
    ("🔬 arXiv", "arxiv"),
    ("🎓 OpenAlex", "openalex"),
    ("🧠 Semantic Scholar", "semantic_scholar"),
    ("🏥 PubMed", "pubmed"),
    ("📄 CrossRef", "crossref"),
    ("📚 CORE", "core"),
    ("💡 Stack Exchange", "stackexchange"),
    ("💬 Reddit", "reddit"),
    ("📰 Hacker News", "hackernews"),
    ("📕 Open Library", "openlibrary"),
    ("🏛️ Internet Archive", "internet_archive"),
    ("⚡ Jina AI", "jina"),
]

DEFAULT_ENGINES = [v for _, v in ALL_ENGINES]
ENGINE_CHOICES = [(label, val) for label, val in ALL_ENGINES]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

body, .gradio-container {
    font-family: 'Inter', sans-serif !important;
    background: #f8fafc !important;
}

.search-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4c1d95 100%);
    padding: 40px 24px;
    border-radius: 16px;
    margin-bottom: 24px;
    text-align: center;
    box-shadow: 0 10px 40px rgba(79,70,229,0.3);
}

.search-header h1 {
    color: white;
    font-size: 36px;
    font-weight: 700;
    margin: 0 0 8px;
    letter-spacing: -0.5px;
}

.search-header p {
    color: rgba(255,255,255,0.8);
    font-size: 14px;
    margin: 0;
}

.search-btn {
    background: linear-gradient(135deg, #7c3aed, #6d28d9) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 16px !important;
    height: 50px !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 12px rgba(124,58,237,0.4) !important;
}

.search-btn:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(124,58,237,0.5) !important;
}

#search-input textarea {
    border-radius: 10px !important;
    font-size: 16px !important;
    border: 2px solid #e2e8f0 !important;
    padding: 12px 16px !important;
    transition: border-color 0.2s !important;
}

#search-input textarea:focus {
    border-color: #7c3aed !important;
    box-shadow: 0 0 0 3px rgba(124,58,237,0.1) !important;
}
"""

with gr.Blocks(
    title="🔍 FuckenSearch — Deep Search Engine",
) as demo:

    gr.HTML("""
    <div class="search-header">
        <h1>🔍 FuckenSearch</h1>
        <p>محرك بحث عميق يجمع من <strong>22+ مصدر مجاني</strong> — ويكيبيديا، أبحاث علمية، مجتمعات تقنية، كتب وأرشيف</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=4):
            query_input = gr.Textbox(
                placeholder="ابحث عن أي شيء... (عربي أو إنجليزي)",
                show_label=False,
                elem_id="search-input",
                lines=1,
            )
        with gr.Column(scale=1, min_width=120):
            search_btn = gr.Button("🔍 ابحث", elem_classes=["search-btn"])

    with gr.Accordion("⚙️ إعدادات متقدمة", open=False):
        with gr.Row():
            with gr.Column():
                engines_select = gr.CheckboxGroup(
                    choices=ENGINE_CHOICES,
                    value=DEFAULT_ENGINES,
                    label="📡 المصادر المفعّلة",
                )
            with gr.Column(scale=0, min_width=200):
                num_results_slider = gr.Slider(
                    minimum=10, maximum=200, value=50, step=10,
                    label="📊 عدد النتائج",
                )

    with gr.Row():
        with gr.Column():
            gr.HTML("""
            <div style='display:flex;gap:8px;flex-wrap:wrap;margin:8px 0;'>
                <span style='font-size:12px;color:#64748b;'>أمثلة:</span>
                <span style='background:#f1f5f9;border:1px solid #e2e8f0;padding:2px 10px;
                              border-radius:20px;font-size:12px;cursor:pointer;color:#475569;'>
                    Python machine learning
                </span>
                <span style='background:#f1f5f9;border:1px solid #e2e8f0;padding:2px 10px;
                              border-radius:20px;font-size:12px;cursor:pointer;color:#475569;'>
                    الذكاء الاصطناعي العربي
                </span>
                <span style='background:#f1f5f9;border:1px solid #e2e8f0;padding:2px 10px;
                              border-radius:20px;font-size:12px;cursor:pointer;color:#475569;'>
                    climate change research 2024
                </span>
                <span style='background:#f1f5f9;border:1px solid #e2e8f0;padding:2px 10px;
                              border-radius:20px;font-size:12px;cursor:pointer;color:#475569;'>
                    quantum computing tutorial
                </span>
            </div>
            """)

    results_output = gr.HTML(
        value="""
        <div style='text-align:center;padding:60px;color:#94a3b8;font-family:sans-serif;'>
            <div style='font-size:56px;margin-bottom:16px;'>🔍</div>
            <div style='font-size:20px;font-weight:600;color:#64748b;'>ابدأ بحثك</div>
            <div style='font-size:14px;margin-top:8px;'>
                اكتب استعلامك واضغط على زر البحث للحصول على نتائج من 22+ مصدر
            </div>
        </div>
        """,
    )

    # Trigger on button or Enter
    search_btn.click(
        fn=do_search,
        inputs=[query_input, engines_select, num_results_slider],
        outputs=results_output,
    )
    query_input.submit(
        fn=do_search,
        inputs=[query_input, engines_select, num_results_slider],
        outputs=results_output,
    )

    gr.HTML("""
    <div style='text-align:center;margin-top:24px;padding:16px;
                border-top:1px solid #e2e8f0;color:#94a3b8;font-size:12px;'>
        FuckenSearch v2.0 — Open Source Deep Search Engine |
        <a href='https://github.com/fuckensearch' style='color:#7c3aed;'>GitHub</a>
    </div>
    """)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        show_api=False,
        quiet=False,
        css=CSS,
        theme=gr.themes.Soft(primary_hue="violet", neutral_hue="slate"),
    )
