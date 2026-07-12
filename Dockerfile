FROM python:3.10-slim

# منع بايثون من كتابة ملفات pyc وكتابة المخرجات مباشرة
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

WORKDIR /app

# تثبيت التبعيات الأساسية للنظام (مطلوبة لـ lxml وبعض المكتبات الأخرى)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً لتسريع الكاش
COPY requirements.txt .

# تثبيت مكتبات بايثون
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# إنشاء مجلدات وتحديد الصلاحيات لضمان عمل التطبيق بدون مشاكل صلاحيات في Hugging Face
RUN mkdir -p /app/web/static && chmod -R 777 /app

# منفذ Hugging Face Spaces الافتراضي
EXPOSE 7860

# أمر تشغيل التطبيق
CMD ["python", "run.py", "web"]
