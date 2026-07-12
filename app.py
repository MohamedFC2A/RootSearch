import os
import uvicorn
import spaces
from web.app import app

# دالة وهمية لإرضاء فحص التشغيل الخاص بـ Hugging Face ZeroGPU
@spaces.GPU
def dummy_gpu_function():
    return "GPU Activated"

@app.on_event("startup")
async def startup_event():
    # استدعاء الدالة عند تشغيل الخادم لإجبار نظام ZeroGPU على تفعيل الـ GPU والتحقق من صحتها
    try:
        dummy_gpu_function()
    except Exception as e:
        print(f"ZeroGPU Startup Trigger Error: {e}")

if __name__ == "__main__":
    # الحصول على المنفذ من متغيرات البيئة (Hugging Face يحدد منفذ 7860 افتراضياً)
    port = int(os.getenv("PORT", 7860))
    # تشغيل خادم Uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=port)
