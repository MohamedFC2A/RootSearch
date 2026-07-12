"""
Fucken Search - Deep Web Scraper Module
متسلق المواقع الخارق: يسحب المحتوى من أعماق الصفحات
"""

import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, urljoin
import socket
import ipaddress

import aiohttp
import aiohttp.abc
from bs4 import BeautifulSoup
import trafilatura
import trafilatura.settings as traf_settings
import httpx
try:
    from fake_useragent import UserAgent
    ua_generator = UserAgent()
except Exception:
    ua_generator = None

from config import config
from core.search_engine import SearchResult


class SafeResolver(aiohttp.abc.AbstractResolver):
    """محلل أسماء نطاقات آمن يمنع SSRF و DNS Rebinding بشكل مطلق"""
    
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        except Exception as e:
            raise OSError(f"DNS resolution failed for {host}: {e}")
            
        safe_infos = []
        for info in infos:
            ip = info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip)
                # منع العناوين المحلية والخاصة والمحجوزة
                if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_multicast or ip_obj.is_reserved:
                    continue
                safe_infos.append(info)
            except ValueError:
                continue
                
        if not safe_infos:
            raise OSError(f"Access denied: Private or invalid IP addresses are blocked for {host}")
            
        return [{
            "hostname": host,
            "host": item[4][0],
            "port": item[4][1],
            "family": item[0],
            "proto": item[2],
            "flags": socket.AI_NUMERICHOST,
        } for item in safe_infos]

    async def close(self) -> None:
        pass


class DeepScraper:
    """متسلق المواقع العميق - يسحب المحتوى من أي صفحة ويب"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._user_agent_index = 0
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)
    
    def _get_next_user_agent(self) -> str:
        if ua_generator:
            try:
                return ua_generator.random
            except Exception:
                pass
        ua = config.user_agents[self._user_agent_index]
        self._user_agent_index = (self._user_agent_index + 1) % len(config.user_agents)
        return ua
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=config.request_timeout)
            resolver = SafeResolver()
            conn = aiohttp.TCPConnector(limit=config.max_concurrent_requests, force_close=True, resolver=resolver)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=conn)
        return self.session
    
    @staticmethod
    def _is_safe_url(url: str) -> bool:
        """تحقق مبدئي سريع من أمان الرابط قبل البدء بالطلب"""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            
            hostname = parsed.hostname
            if not hostname:
                return False
                
            # تصفية سريعة للنصوص الواضحة
            hostname_lower = hostname.lower()
            if hostname_lower in ('localhost', '127.0.0.1', '::1') or hostname_lower.endswith('.local'):
                return False
                
            return True
        except Exception:
            return False

    async def fetch_page(self, url: str) -> Optional[str]:
        """جلب صفحة ويب كاملة بشكل آمن عبر aiohttp لمنع ثغرات SSRF و DNS Rebinding"""
        if not self._is_safe_url(url):
            print(f"[⚠️ SSRF PROTECTION] تم حظر محاولة الوصول إلى رابط غير آمن: {url}")
            return None
            
        async with self.semaphore:
            session = await self._get_session()
            
            headers = {
                "User-Agent": self._get_next_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            # محاولة جلب الصفحة مع إعادة المحاولة وتغيير وكيل المستخدم
            for attempt in range(3):
                try:
                    headers["User-Agent"] = self._get_next_user_agent()
                    async with session.get(url, headers=headers, 
                                           allow_redirects=True,
                                           ssl=False) as response:
                        if response.status == 200:
                            content_type = response.headers.get('Content-Type', '')
                            if any(t in content_type for t in ['text/html', 'application/xhtml', 'application/json']):
                                return await response.text()
                            else:
                                try:
                                    return await response.text()
                                except Exception:
                                    pass
                        elif response.status == 429:
                            wait = min(3 * (attempt + 1), 15)
                            await asyncio.sleep(wait)
                        else:
                            await asyncio.sleep(1 * (attempt + 1))
                except Exception as e:
                    if "Access denied" in str(e) or "blocked" in str(e):
                        print(f"[⚠️ SSRF PROTECTION] تم حظر الطلب من خلال Resolver: {url} -> {e}")
                        return None
                    if attempt == 2:
                        return None
                    await asyncio.sleep(1.5 * (attempt + 1))
            
            return None
    
    def extract_content_trafilatura(self, html: str, url: str) -> Dict[str, Any]:
        """استخراج المحتوى الأساسي باستخدام trafilatura (الأفضل)"""
        try:
            # إعدادات trafilatura للاستخراج العميق
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=False,
                output_format='json',
                with_metadata=True,
                max_tree_size=1000000,  # حد أقصى لحجم الشجرة
                include_processing_instructions=False,
                favor_precision=True,
            )
            
            if result:
                import json
                data = json.loads(result)
                return {
                    'title': data.get('title', ''),
                    'content': data.get('raw_text', ''),
                    'author': data.get('author', ''),
                    'date': data.get('date', ''),
                    'description': data.get('description', ''),
                    'site_name': data.get('sitename', ''),
                    'categories': data.get('categories', []),
                    'tags': data.get('tags', []),
                }
        except Exception:
            pass
        
        return {}
    
    def extract_content_bs4(self, html: str, url: str) -> Dict[str, Any]:
        """استخراج المحتوى باستخدام BeautifulSoup (احتياطي)"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # إزالة العناصر غير المرغوب فيها
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 
                                'iframe', 'noscript', 'svg', 'form', 'aside']):
                element.decompose()
            
            # استخراج العنوان
            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            
            # استخراج الوصف
            description = ''
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or \
                        soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc:
                description = meta_desc.get('content', '')
            
            # استخراج النص الرئيسي
            content_parts = []
            
            # محاولة العثور على المحتوى الرئيسي
            main_selectors = [
                'article', 'main', '[role="main"]', '.post-content', '.article-content',
                '.entry-content', '#content', '.content', '.post', '.article',
                '.story-body', '.story-body__inner', '.detail-body',
                '[itemprop="articleBody"]', '.node-content',
            ]
            
            for selector in main_selectors:
                try:
                    main_content = soup.select_one(selector)
                    if main_content:
                        paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                                                          'li', 'td', 'th', 'blockquote', 'pre', 'code'])
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            if text and len(text) > 20:
                                content_parts.append(text)
                        
                        if content_parts:
                            break
                except Exception:
                    continue
            
            # إذا لم نجد محتوى، نأخذ كل الفقرات
            if not content_parts:
                paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        content_parts.append(text)
            
            content = '\n\n'.join(content_parts)
            
            # تنظيف النص
            content = re.sub(r'\s+', ' ', content)
            content = re.sub(r'\n{3,}', '\n\n', content)
            
            # استخراج الكلمات المفتاحية
            keywords = []
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                kw = meta_keywords.get('content', '')
                keywords = [k.strip() for k in kw.split(',') if k.strip()]
            
            return {
                'title': title,
                'content': content.strip()[:100000],  # حد أقصى 100k حرف
                'description': description,
                'keywords': keywords,
                'extraction_method': 'bs4',
            }
            
        except Exception as e:
            return {'title': '', 'content': '', 'error': str(e)}
    
    async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """تسليق صفحة ويب واستخراج محتواها بالكامل"""
        html = await self.fetch_page(url)
        if not html:
            return None
        
        # استخدام trafilatura أولاً (أفضل جودة)
        extracted = self.extract_content_trafilatura(html, url)
        
        # إذا فشل، استخدم BeautifulSoup
        if not extracted.get('content'):
            extracted = self.extract_content_bs4(html, url)
        
        if extracted.get('content'):
            extracted['url'] = url
            extracted['content_length'] = len(extracted['content'])
            extracted['word_count'] = len(extracted['content'].split())
            extracted['scrape_timestamp'] = datetime.now().isoformat()
            
            # استخراج عنوان الـ IP الفعلي للموقع
            try:
                hostname = urlparse(url).hostname
                if hostname:
                    extracted['resolved_ip'] = socket.gethostbyname(hostname)
                else:
                    extracted['resolved_ip'] = ''
            except Exception:
                extracted['resolved_ip'] = ''
            
            return extracted
        
        return None
    
    async def scrape_batch(self, results: List[SearchResult], max_pages: int = 20) -> List[SearchResult]:
        """تسليق مجموعة من النتائج بشكل متوازي"""
        enriched_results = []
        
        # اختيار أفضل النتائج للتسليق
        sorted_results = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        to_scrape = sorted_results[:max_pages]
        
        # تسليق بشكل متوازي
        tasks = []
        for result in to_scrape:
            tasks.append(self.scrape_url(result.url))
        
        scraped_contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result, content in zip(to_scrape, scraped_contents):
            if isinstance(content, dict) and content.get('content'):
                result.content = content['content']
                result.metadata['scraped'] = True
                result.metadata['word_count'] = content.get('word_count', 0)
                result.metadata['extraction_method'] = content.get('extraction_method', 'trafilatura')
                enriched_results.append(result)
            else:
                # حتى لو فشل التسليق، نضيف النتيجة مع السنبت
                enriched_results.append(result)
        
        return enriched_results
    
    async def deep_scrape(self, url: str, max_depth: int = 2) -> Dict[str, Any]:
        """تسليق عميق - يتابع الروابط الداخلية"""
        result = {
            'main_page': None,
            'related_pages': [],
            'all_content': '',
        }
        
        main_content = await self.scrape_url(url)
        if not main_content:
            return result
        
        result['main_page'] = main_content
        result['all_content'] = main_content.get('content', '')
        
        # البحث عن روابط داخلية ذات صلة
        if max_depth > 1:
            html = await self.fetch_page(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                base_domain = urlparse(url).netloc
                
                internal_links = []
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)
                    
                    # نجمع الروابط الداخلية فقط
                    if parsed.netloc == base_domain and parsed.scheme in ('http', 'https'):
                        # نتجنب الصور والملفات
                        if not any(ext in parsed.path.lower() for ext in ['.jpg', '.png', '.pdf', '.zip', '.mp4']):
                            internal_links.append(full_url)
                
                # نأخذ أقصى 5 روابط داخلية
                internal_links = list(set(internal_links))[:5]
                
                for link in internal_links:
                    content = await self.scrape_url(link)
                    if content:
                        result['related_pages'].append(content)
                        result['all_content'] += '\n\n' + content.get('content', '')
        
        return result
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
