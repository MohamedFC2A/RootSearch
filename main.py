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

Fucken Search - Deep Search Engine
محرك البحث الخارق: يبحث في أعماق الإنترنت ويحلل كل شيء
"""

import asyncio
import sys
import os
from typing import Optional

# إضافة المسار الحالي
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from core.search_engine import SearchEngine
from core.scraper import DeepScraper
from core.aggregator import ResultAggregator


class FuckenSearch:
    """المحرك الرئيسي - ينسق جميع المكونات"""
    
    def __init__(self):
        self.search_engine = SearchEngine()
        self.scraper = DeepScraper()
        self.aggregator = ResultAggregator()
    
    async def deep_search(self, query: str, deep_analysis: bool = True) -> dict:
        """
        البحث العميق الخارق
        
        Args:
            query: استعلام البحث
            deep_analysis: هل نقوم بتحليل عميق أم بحث سريع
        
        Returns:
            تقرير شامل بنتائج البحث
        """
        print(f"\n[🔍] Fucken Search: بدء البحث العميق...")
        print(f"[📝] الاستعلام: {query}")
        print(f"[⚙️]  الوضع: {'تحليل عميق' if deep_analysis else 'بحث سريع'}")
        
        # 1. البحث في جميع محركات البحث
        print(f"\n[🌐] البحث في {len(config.search_engines)} محركات بحث...")
        results = await self.search_engine.search_all(query)
        print(f"[✅] تم العثور على {len(results)} نتيجة (قبل التصفية)")
        
        if not results:
            return {
                'query': query,
                'results': [],
                'total_results': 0,
                'message': 'لم يتم العثور على نتائج. جرب تغيير صياغة الاستعلام.'
            }
        
        # 2. تسليق المحتوى (إذا كان تحليل عميق)
        if deep_analysis:
            print(f"\n[🕷️]  تسليق المواقع واستخراج المحتوى...")
            enriched_results = await self.scraper.scrape_batch(results, max_pages=30)
            print(f"[✅] تم تسليق {sum(1 for r in enriched_results if r.content)} صفحة بنجاح")
        else:
            enriched_results = results
        
        # 3. تجميع وترتيب وتحليل
        print(f"\n[🧠] تجميع وتحليل النتائج...")
        final_report = await self.aggregator.aggregate(enriched_results, query)
        
        print(f"\n[🏆] اكتمل البحث العميق!")
        print(f"[📊] إجمالي النتائج: {final_report['total_results']}")
        print(f"[📂] التصنيفات: {', '.join(final_report.get('categories', {}).keys())}")
        
        return final_report
    
    async def quick_search(self, query: str) -> dict:
        """بحث سريع بدون تحليل عميق"""
        return await self.deep_search(query, deep_analysis=False)
    
    async def close(self):
        """تنظيف الموارد"""
        await self.search_engine.close()
        await self.scraper.close()


# ===== واجهة سطر الأوامر (CLI) =====

def main():
    """نقطة الدخول الرئيسية - تفوض العمل لـ cli.terminal"""
    from cli.terminal import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
