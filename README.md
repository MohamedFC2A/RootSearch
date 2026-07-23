---
title: DeepSearch
emoji: 🔍
colorFrom: purple
colorTo: indigo
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: true
license: mit
short_description: محرك بحث عميق يجمع من 22+ مصدر مجاني بدون API keys
---

# 🔍 RootSearch — محرك البحث العميق

**محرك بحث متكامل** يجمع النتائج من **22+ مصدر مجاني** في وقت واحد — بدون أي API keys مدفوعة.

---

## ⚡ المصادر المدعومة (22+ مصدر)

### 🔍 محركات البحث العامة
| المصدر | النوع | الحالة |
|--------|-------|--------|
| DuckDuckGo | Web scraping | ✅ |
| Startpage | Google proxy (بدون CAPTCHA) | ✅ |
| Bing | Web scraping | ✅ |
| Brave Search | Web scraping | ✅ |
| Mojeek | محرك مستقل | ✅ |
| Qwant | JSON API | ✅ |
| Ecosia | Web scraping | ✅ |
| SearXNG | Meta-search | ✅ |

### 📚 موسوعات وبيانات
| المصدر | النوع | الحالة |
|--------|-------|--------|
| Wikipedia | REST API (عربي + إنجليزي) | ✅ |
| Wikidata | Search API | ✅ |

### 🔬 أبحاث علمية (APIs مجانية 100%)
| المصدر | النوع | الحالة |
|--------|-------|--------|
| arXiv | Atom/XML API | ✅ |
| OpenAlex | REST API | ✅ |
| Semantic Scholar | REST API | ✅ |
| PubMed / NCBI | E-utilities API | ✅ |
| CrossRef | REST API | ✅ |
| CORE | REST API | ✅ |

### 💬 مجتمعات تقنية
| المصدر | النوع | الحالة |
|--------|-------|--------|
| Stack Exchange | REST API | ✅ |
| Reddit | JSON endpoint | ✅ |
| Hacker News | Algolia API | ✅ |

### 📖 كتب وأرشيف
| المصدر | النوع | الحالة |
|--------|-------|--------|
| Open Library | REST API | ✅ |
| Internet Archive | Search API | ✅ |
| Jina AI Search | AI-powered | ✅ |

---

## 🚀 التشغيل المحلي

```bash
git clone https://github.com/your-username/RootSearch
cd RootSearch
pip install -r requirements.txt

# تشغيل Gradio (HuggingFace-style)
python gradio_app.py

# تشغيل FastAPI (local server)
python run.py web
```

---

## 🏗️ هيكل المشروع

```
RootSearch/
├── gradio_app.py        # 🎯 HuggingFace Space entry point
├── app.py               # 🚀 Multi-mode entry point
├── config.py            # ⚙️ الإعدادات (22 مصدر)
├── requirements.txt     # 📦 المتطلبات
├── core/
│   ├── search_engine.py # 🔍 22+ محرك بحث
│   ├── scraper.py       # 🕷️ متسلق المواقع
│   ├── analyzer.py      # 🧠 محلل AI
│   └── aggregator.py    # 📊 مجمع النتائج
├── web/                 # 🌐 FastAPI web server
└── cli/                 # 💻 واجهة سطر الأوامر
```

---

## 🧠 التقنيات

- **Python + asyncio** — بحث متوازي عالي الأداء
- **aiohttp** — طلبات HTTP غير متزامنة
- **BeautifulSoup4** — تحليل HTML
- **trafilatura** — استخراج المحتوى
- **Gradio** — واجهة HuggingFace Space
- **FastAPI** — خادم API

---

## ⚠️ ملاحظة

هذا المشروع للأغراض التعليمية والبحثية. يرجى احترام شروط خدمة المصادر المستخدمة.

**MIT License** — مجاني، مفتوح المصدر، للجميع.
