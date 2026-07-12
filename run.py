#!/usr/bin/env python3
"""
Fucken Search - Run Script
مشغل التطبيق: CLI, Web, or Direct Search
"""

import sys
import os
import asyncio

# إضافة المسار الحالي
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.terminal import main as cli_main
from main import FuckenSearch


def print_banner():
    """طباعة الشعار"""
    banner = """
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
██║░░░░░██║░░░░░░╚█████╔╝██║░░██║╚█████╔╝██║░░██║
╚═╝░░░░░╚═╝░░░░░░░╚════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝

    🔥 FUCKEN SEARCH - Deep Search Engine 🔥
    ⚡ البحث الخارق في أعماق الإنترنت ⚡
    💀 Without paid APIs - Pure Python Power 💀
    
    ==============================================
    """
    print(banner)


def main():
    """المشغل الرئيسي"""
    print_banner()
    
    if len(sys.argv) < 2:
        print("\n🔸 استخدم:")
        print("   python run.py cli          - واجهة سطر الأوامر")
        print("   python run.py web          - تشغيل خادم الويب")
        print("   python run.py search <query> - بحث مباشر")
        print("   python run.py --help       - المساعدة")
        return
    
    mode = sys.argv[1].lower()
    
    if mode == "cli":
        print("\n[💻] تشغيل واجهة سطر الأوامر...\n")
        cli_main()
    
    elif mode == "web":
        print("\n[🌐] تشغيل خادم الويب...")
        from web.app import start
        start()
    
    elif mode == "search" and len(sys.argv) > 2:
        query = ' '.join(sys.argv[2:])
        print(f"\n[🔍] بحث مباشر: '{query}'\n")
        asyncio.run(run_direct(query))
    
    elif mode in ["--help", "-h", "help"]:
        print("\n📖 Fucken Search - المساعدة")
        print("=" * 40)
        print("python run.py cli              # واجهة تفاعلية")
        print("python run.py web              # خادم ويب")
        print('python run.py search "query"   # بحث مباشر')
        print("\n⚙️  الإعدادات: config.py")
        print("🌐 الويب: http://localhost:6969")
    
    else:
        print(f"\n[❌] أمر غير معروف: {mode}")
        print("استخدم python run.py --help للمساعدة")


async def run_direct(query: str):
    """تشغيل بحث مباشر"""
    engine = FuckenSearch()
    try:
        import json
        report = await engine.deep_search(query)
        
        print(f"\n{'🔥'*40}")
        print(f"🔥  النتائج لـ: {query}")
        print(f"{'🔥'*40}")
        print(f"📊 إجمالي النتائج: {report.get('total_results', 0)}")
        
        if report.get('analysis'):
            a = report['analysis']
            if a.get('overall_summary'):
                print(f"\n📋 التلخيص: {a['overall_summary'][:300]}...")
        
        print(f"\n📌 أفضل النتائج:")
        for i, r in enumerate(report.get('results', [])[:5], 1):
            print(f"\n  [{i}] {r.get('title', 'N/A')[:70]}")
            print(f"      🔗 {r.get('url', 'N/A')[:70]}")
            print(f"      ⭐ {r.get('relevance_score', 0)*100:.1f}%")
    finally:
        await engine.close()


if __name__ == "__main__":
    main()
