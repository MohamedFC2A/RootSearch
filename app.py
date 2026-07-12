import os
import uvicorn
from web.app import app

# هذا الملف مخصص للتشغيل على منصة Hugging Face Spaces (Gradio SDK)
# حيث تقوم المنصة بتشغيل ملف app.py في المجلد الرئيسي تلقائياً.

if __name__ == "__main__":
    # الحصول على المنفذ من متغيرات البيئة (Hugging Face يحدد منفذ 7860 افتراضياً)
    port = int(os.getenv("PORT", 7860))
    # تشغيل خادم Uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=port)
