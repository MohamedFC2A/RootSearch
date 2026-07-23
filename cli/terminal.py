"""
RootSearch - Beautiful Interactive Terminal interface
واجهة الطرفية التفاعلية الخارقة لمحرك البحث
"""

import asyncio
import os
import sys
import json
import urllib.parse
from typing import List, Dict, Any, Optional

# إضافة المسار الحالي
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import config
from main import RootSearch

# أكواد الألوان لتهيئة الطرفية الملونة
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_UNDERLINE = "\033[4m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_GRAY = "\033[90m"

# خلفيات ملونة للتنبيهات
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"


def color_text(text: str, color: str, bold: bool = False, underline: bool = False) -> str:
    """تنسيق النص بالألوان والتأثيرات"""
    style = ""
    if bold:
        style += CLR_BOLD
    if underline:
        style += CLR_UNDERLINE
    return f"{style}{color}{text}{CLR_RESET}"


def print_header(title: str):
    """طباعة عنوان قسم بشكل منسق"""
    width = 65
    print("\n" + color_text("═" * width, CLR_GRAY))
    print(color_text(f" {title.center(width - 2)} ", CLR_CYAN, bold=True))
    print(color_text("═" * width, CLR_GRAY))


def print_banner():
    """طباعة شعار البحث الخارق باللون الأحمر والوردي"""
    banner = f"""
{color_text("███████╗██╗░░░██╗░█████╗░██╗░░██╗███████╗███╗░░██╗", CLR_RED, bold=True)}
{color_text("██╔════╝██║░░░██║██╔══██╗██║░██╔╝██╔════╝████╗░██║", CLR_RED, bold=True)}
{color_text("█████╗░░██║░░░██║██║░░╚═╝█████═╝░█████╗░░██╔██╗██║", CLR_MAGENTA, bold=True)}
{color_text("██╔══╝░░██║░░░██║██║░░██╗██╔═██╗░██╔══╝░░██║╚████║", CLR_MAGENTA, bold=True)}
{color_text("██║░░░░░╚██████╔╝╚█████╔╝██║░╚██╗███████╗██║░╚███║", CLR_CYAN, bold=True)}
{color_text("╚═╝░░░░░░╚═════╝░░╚════╝░╚═╝░░╚═╝╚══════╝╚═╝░░╚══╝", CLR_CYAN, bold=True)}

{color_text("███████╗███████╗░█████╗░██████╗░░█████╗░██╗░░██╗", CLR_RED, bold=True)}
{color_text("██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║░░██║", CLR_RED, bold=True)}
{color_text("█████╗░░█████╗░░██║░░╚═╝██████╔╝██║░░╚═╝███████║", CLR_MAGENTA, bold=True)}
{color_text("██╔══╝░░██╔══╝░░██║░░██╗██╔══██╗██║░░██╗██╔══██║", CLR_MAGENTA, bold=True)}
{color_text("██║░░░░░██║░░░░░░╚█████╔╝██║░░██║╚█████╔╝██║░░██║", CLR_CYAN, bold=True)}
{color_text("╚═╝░░░░░╚═╝░░░░░░░╚════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝", CLR_CYAN, bold=True)}

          🔥 {color_text("ROOTSEARCH", CLR_RED, bold=True)} - {color_text("محرك البحث الخارق", CLR_YELLOW, bold=True)} 🔥
          ⚡ {color_text("البحث التحليلي العميق في خبايا الإنترنت", CLR_GREEN)} ⚡
          💀 {color_text("Without paid APIs - Pure Python Power", CLR_GRAY, bold=True)} 💀
    =============================================================
    """
    print(banner)


async def spinner_animation(message: str, stop_event: asyncio.Event):
    """حركة مؤشر تحميل متحرك أثناء العمليات غير المتزامنة"""
    spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0
    while not stop_event.is_set():
        symbol = spinners[idx % len(spinners)]
        sys.stdout.write(f"\r{color_text(symbol, CLR_CYAN, bold=True)} {message}...")
        sys.stdout.flush()
        idx += 1
        await asyncio.sleep(0.08)
    sys.stdout.write("\r" + " " * (len(message) + 15) + "\r")
    sys.stdout.flush()


async def run_with_spinner(coro, message: str) -> Any:
    """تشغيل مهمة غير متزامنة مع عرض مؤشر تحميل"""
    stop_event = asyncio.Event()
    spinner_task = asyncio.create_task(spinner_animation(message, stop_event))
    try:
        result = await coro
        return result
    finally:
        stop_event.set()
        await spinner_task


def display_results(results: List[Dict[str, Any]]):
    """عرض قائمة نتائج البحث منسقة ومجملة"""
    print(f"\n📌 {color_text('أفضل النتائج التي تم العثور عليها:', CLR_YELLOW, bold=True)}")
    print(color_text("─" * 65, CLR_GRAY))
    
    for i, r in enumerate(results[:15], 1):
        idx = color_text(f"[{i}]", CLR_CYAN, bold=True)
        title = color_text(r.get('title', 'بدون عنوان')[:80], CLR_WHITE, bold=True)
        url = color_text(r.get('url', '')[:75], CLR_GREEN, underline=True)
        source = color_text(f"📰 {r.get('source', 'غير معروف')}", CLR_YELLOW)
        score = color_text(f"⭐ {r.get('relevance_score', 0)*100:.1f}%", CLR_MAGENTA)
        
        print(f"\n {idx} {title}")
        print(f"     🔗 {url}")
        print(f"     {source}  |  {score}")
        
        snippet = r.get('snippet', '')
        if snippet:
            # تنظيف السنبت
            snippet_cleaned = snippet.replace('\n', ' ').strip()
            print(f"     {color_text('📝', CLR_GRAY)} {color_text(snippet_cleaned[:120] + '...', CLR_GRAY)}")
            
    print("\n" + color_text("─" * 65, CLR_GRAY))


def display_analysis_report(analysis: Dict[str, Any]):
    """عرض تقرير التحليل الشامل AI/NLP"""
    if not analysis:
        print(color_text("\n[⚠️] لا تتوفر بيانات تحليلية لهذه العملية.", CLR_YELLOW))
        return
        
    print_header("📊 التقرير التحليلي الشامل")
    
    # 1. التلخيص الشامل
    if analysis.get('overall_summary'):
        print(f"\n📝 {color_text('التلخيص الشامل للموضوع:', CLR_CYAN, bold=True)}")
        print(color_text("─" * 40, CLR_GRAY))
        print(color_text(analysis['overall_summary'], CLR_WHITE))
        print(color_text("─" * 40, CLR_GRAY))
        
    # 2. الكلمات المفتاحية
    if analysis.get('keywords'):
        print(f"\n🏷️  {color_text('أهم الكلمات المفتاحية المستخلصة:', CLR_CYAN, bold=True)}")
        kws = [color_text(k if isinstance(k, str) else k.get('word', ''), CLR_YELLOW) for k in analysis['keywords'][:15]]
        print("  " + " | ".join(kws))
        
    # 3. تحليل المشاعر
    if analysis.get('sentiment_overview'):
        sent = analysis['sentiment_overview']
        overall = sent.get('overall', 'محايد')
        score = sent.get('score', 0.0)
        
        if overall == 'إيجابي':
            overall_disp = color_text("إيجابي 😊", CLR_GREEN, bold=True)
        elif overall == 'سلبي':
            overall_disp = color_text("سلبي 😡", CLR_RED, bold=True)
        else:
            overall_disp = color_text("محايد 😐", CLR_YELLOW, bold=True)
            
        print(f"\n💭 {color_text('تحليل المشاعر العامة:', CLR_CYAN, bold=True)} {overall_disp} (الدرجة: {color_text(str(score), CLR_MAGENTA)})")
        
    # 4. الكيانات المستخرجة
    if analysis.get('entities'):
        ent = analysis['entities']
        print(f"\n🔍 {color_text('أهم الكيانات المستخرجة:', CLR_CYAN, bold=True)}")
        
        categories = {
            'persons': ('👤 الأشخاص', CLR_GREEN),
            'organizations': ('🏢 المنظمات', CLR_BLUE),
            'locations': ('📍 الأماكن', CLR_YELLOW),
            'dates': ('📅 التواريخ', CLR_WHITE),
        }
        
        for key, (label, color) in categories.items():
            vals = ent.get(key, [])
            if vals:
                clean_vals = [color_text(v, color) for v in vals[:6]]
                print(f"   {label}: {', '.join(clean_vals)}")
                
    # 5. الإحصائيات
    if analysis.get('statistics'):
        stats = analysis['statistics']
        print(f"\n📈 {color_text('إحصائيات البحث والمسح:', CLR_CYAN, bold=True)}")
        print(f"   - عدد نتائج البحث الكلية: {color_text(str(stats.get('total_results', 0)), CLR_WHITE, bold=True)}")
        print(f"   - إجمالي الكلمات التي تم تحليلها: {color_text(f'{stats.get('total_words_analyzed', 0):,}', CLR_WHITE, bold=True)}")
        print(f"   - عدد محركات البحث المستخدمة: {color_text(str(stats.get('engines_count', 0)), CLR_WHITE, bold=True)}")
        print(f"   - متوسط أهمية ومطابقة النتائج: {color_text(f'{stats.get('average_relevance', 0)*100:.1f}%', CLR_WHITE, bold=True)}")
        
    print("\n" + color_text("═" * 65, CLR_GRAY))


def read_scraped_page(result: Dict[str, Any]):
    """قراءة نص الصفحة الممسوحة بشكل صفحة صفحة"""
    content = result.get('content', '')
    if not content:
        # محاولة البحث في content_preview أو السنبت
        content = result.get('content_preview', '') or result.get('snippet', '')
        
    if not content:
        print(color_text("\n[❌] عذراً، لا يتوفر محتوى نصي ممسوح لهذه الصفحة.", CLR_RED))
        return
        
    print_header(f"📖 قراءة: {result.get('title', 'بدون عنوان')}")
    print(color_text(f"المصدر: {result.get('url')}\n", CLR_GREEN))
    
    # تقسيم النص إلى فقرات أو صفحات
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    
    if not paragraphs:
        paragraphs = [content]
        
    page_size = 6  # عدد الفقرات المعروضة في الصفحة الواحدة
    total_pages = (len(paragraphs) + page_size - 1) // page_size
    
    current_page = 0
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(paragraphs))
        
        print(color_text(f"--- الصفحة {current_page + 1} من {total_pages} ---", CLR_YELLOW).center(75))
        print()
        
        for p in paragraphs[start_idx:end_idx]:
            print(p)
            print()
            
        print(color_text("─" * 65, CLR_GRAY))
        
        if total_pages <= 1:
            input(color_text("اضغط Enter للعودة للقائمة... ", CLR_CYAN))
            break
            
        opts = []
        if current_page < total_pages - 1:
            opts.append(color_text("[N] التالي", CLR_GREEN))
        if current_page > 0:
            opts.append(color_text("[P] السابق", CLR_GREEN))
        opts.append(color_text("[Q] خروج للنتائج", CLR_RED))
        
        cmd = input(f"خيارات القراءة ({', '.join(opts)}): ").strip().lower()
        
        if cmd == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif cmd == 'p' and current_page > 0:
            current_page -= 1
        elif cmd in ['q', 'exit', 'خروج']:
            break
        else:
            print(color_text("أمر غير صالح.", CLR_RED))


def export_results_file(report: Dict[str, Any]):
    """تصدير نتائج البحث إلى ملف"""
    print(f"\n📂 {color_text('تصدير التقرير والنتائج:', CLR_YELLOW, bold=True)}")
    print("   [1] تصدير كملف JSON")
    print("   [2] تصدير كملف نصي عادي (.txt)")
    print("   [B] إلغاء العودة للنتائج")
    
    choice = input("\nاختر صيغة التصدير (1/2/B): ").strip().lower()
    
    if choice == 'b':
        return
        
    query_safe = urllib.parse.quote_plus(report.get('query', 'search')).replace('%', '_')[:30]
    timestamp = report.get('timestamp', 'export').replace(':', '-').replace('.', '-')[:19]
    
    if choice == '1':
        filename = f"rootsearch_{query_safe}_{timestamp}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=4)
            print(color_text(f"\n[✅] تم تصدير النتائج بنجاح إلى الملف: {filename}", CLR_GREEN, bold=True))
        except Exception as e:
            print(color_text(f"\n[❌] فشل التصدير: {e}", CLR_RED))
            
    elif choice == '2':
        filename = f"rootsearch_{query_safe}_{timestamp}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"=============================================================\n")
                f.write(f"           ROOTSEARCH REPORT - تقرير بحث خارق             \n")
                f.write(f"=============================================================\n")
                f.write(f"الاستعلام: {report.get('query')}\n")
                f.write(f"التاريخ: {report.get('timestamp')}\n")
                f.write(f"إجمالي النتائج الفريدة: {report.get('total_unique', 0)}\n")
                f.write(f"-------------------------------------------------------------\n\n")
                
                if report.get('analysis') and report['analysis'].get('overall_summary'):
                    f.write(f"📋 التلخيص الشامل:\n")
                    f.write(f"{report['analysis']['overall_summary']}\n\n")
                    f.write(f"-------------------------------------------------------------\n\n")
                    
                f.write(f"📌 النتائج المكتشفة:\n")
                for idx, r in enumerate(report.get('results', []), 1):
                    f.write(f"[{idx}] {r.get('title')}\n")
                    f.write(f"    🔗 الرابط: {r.get('url')}\n")
                    f.write(f"    📰 المصدر: {r.get('source')} | الأهمية: {r.get('relevance_score', 0)*100:.1f}%\n")
                    f.write(f"    📝 نبذة: {r.get('snippet')}\n\n")
            print(color_text(f"\n[✅] تم تصدير النتائج بنجاح إلى الملف: {filename}", CLR_GREEN, bold=True))
        except Exception as e:
            print(color_text(f"\n[❌] فشل التصدير: {e}", CLR_RED))


async def interactive_results_loop(report: Dict[str, Any]):
    """الحلقة التفاعلية للخيارات بعد انتهاء عملية البحث"""
    results = report.get('results', [])
    
    while True:
        print(f"\n🛠  {color_text('الخيارات التفاعلية المتوفرة:', CLR_CYAN, bold=True)}")
        print(f"   * لقراءة صفحة معينة: أدخل رقم النتيجة {color_text('[1-' + str(len(results)) + ']', CLR_GREEN)}")
        print(f"   * {color_text('[A]', CLR_GREEN)} - عرض تقرير التحليل الشامل AI")
        print(f"   * {color_text('[E]', CLR_GREEN)} - تصدير النتائج إلى ملف JSON أو نصي")
        print(f"   * {color_text('[S]', CLR_GREEN)} - بدء استعلام بحث جديد")
        print(f"   * {color_text('[Q]', CLR_RED)} - الخروج من البرنامج")
        
        choice = input("\nأدخل اختيارك: ").strip().lower()
        
        if not choice:
            continue
            
        if choice == 'q':
            print(color_text("\n👋 شكراً لاستخدامك محرك البحث الخارق. مع السلامة!", CLR_YELLOW))
            sys.exit(0)
            
        elif choice == 's':
            break  # العودة لحلقة البحث الرئيسية
            
        elif choice == 'a':
            display_analysis_report(report.get('analysis', {}))
            
        elif choice == 'e':
            export_results_file(report)
            
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                read_scraped_page(results[idx])
            else:
                print(color_text(f"[❌] رقم غير صالح. أدخل رقم بين 1 و {len(results)}", CLR_RED))
        else:
            print(color_text("[❌] اختيار غير معروف. حاول مجدداً.", CLR_RED))


async def run_cli_interactive():
    """تشغيل الواجهة التفاعلية الرئيسية للطرفية"""
    print_banner()
    
    engine = RootSearch()
    try:
        while True:
            query = input(f"\n🔍 {color_text('أدخل موضوع البحث (أو اكتب exit للخروج): ', CLR_WHITE, bold=True)}").strip()
            
            if not query:
                continue
            if query.lower() in ['exit', 'quit', 'خروج', 'q']:
                print(color_text("\n👋 مع السلامة!", CLR_YELLOW))
                break
                
            print(f"\n⚙️  {color_text('وضع البحث:', CLR_CYAN)}")
            print("   [1] بحث سريع (نتائج سريعة بدون تسليق وتحليل عميق للمحتوى)")
            print("   [2] بحث عميق خارق (تسليق الصفحات + تحليل AI + مشاعر + كلمات مفتاحية)")
            
            mode = input("\nاختر وضع البحث (1/2) [الافتراضي: 2]: ").strip()
            deep = mode != '1'
            
            try:
                msg = "جاري إجراء البحث الاستكشافي والتسليق العميق" if deep else "جاري إجراء البحث السريع الخارق"
                report = await run_with_spinner(engine.deep_search(query, deep_analysis=deep), msg)
                
                # طباعة إحصاء سريع
                total = report.get('total_results', 0)
                print(color_text(f"\n[✅] تم البحث بنجاح! العثور على {total} نتيجة فريدة.", CLR_GREEN, bold=True))
                
                if total > 0:
                    display_results(report.get('results', []))
                    await interactive_results_loop(report)
                else:
                    print(color_text("\n[ℹ️] لم يتم العثور على أي نتائج لهذا الاستعلام. جرب صياغة أخرى.", CLR_YELLOW))
                    
            except Exception as e:
                print(color_text(f"\n[❌] حدث خطأ أثناء إجراء البحث: {e}", CLR_RED, bold=True))
                import traceback
                traceback.print_exc()
    finally:
        await engine.close()


async def run_direct_cli_search(query: str, deep: bool = True):
    """تشغيل بحث مباشر سريع بدون الحلقة التفاعلية"""
    engine = RootSearch()
    try:
        msg = f"جاري البحث المباشر عن: '{query}'"
        report = await run_with_spinner(engine.deep_search(query, deep_analysis=deep), msg)
        
        # إذا تطلب الأمر، طباعة JSON
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.close()


def main():
    """نقطة الدخول لسطر الأوامر للطرفية"""
    # تنظيف الشاشة إن أمكن
    if os.name == 'nt':
        os.system('color')  # تفعيل ألوان ANSI في نظام ويندوز
        
    # التحقق من وجود وسائط لتشغيل بحث مباشر
    # تذكر: run.py يمرر "cli" كوسيط أول، والوسائط الباقية هي الاستعلام
    args = sys.argv[1:]
    
    # فلترة كلمة 'cli' إن وجدت في البداية لتجنب الخلل
    if args and args[0].lower() == 'cli':
        args = args[1:]
        
    if args:
        # يوجد استعلام بحث مباشر
        deep = True
        if '--fast' in args:
            deep = False
            args.remove('--fast')
        elif '-f' in args:
            deep = False
            args.remove('-f')
            
        query = " ".join(args).strip()
        if query:
            asyncio.run(run_direct_cli_search(query, deep))
            return
            
    # تشغيل الوضع التفاعلي المعتاد
    asyncio.run(run_cli_interactive())


if __name__ == "__main__":
    main()
