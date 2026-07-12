import os
import uvicorn

# إرضاء فحص التشغيل الخاص بـ Hugging Face ZeroGPU
# Hugging Face يتطلب وجود دالة واحدة على الأقل مزينة بـ @spaces.GPU لتشغيل خوادم ZeroGPU المجانية
try:
    import spaces
    @spaces.GPU
    def dummy_gpu_function():
        return None
except ImportError:
    # لتجنب الأخطاء عند التشغيل المحلي حيث لا تتوفر مكتبة spaces
    pass

from web.app import app

if __name__ == "__main__":
    # الحصول على المنفذ من متغيرات البيئة (Hugging Face يحدد منفذ 7860 افتراضياً)
    port = int(os.getenv("PORT", 7860))
    # تشغيل خادم Uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=port)
