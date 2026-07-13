"""
FuckenSearch — Main Entry Point
يحدد نوع التشغيل: HuggingFace Space (Gradio) أو FastAPI server
"""

import os
import sys

# اختار وضع التشغيل من البيئة
# HF_SPACE=1 or GRADIO=1 or running inside a HF Space (SPACE_ID env var is set)
IS_HF = "SPACE_ID" in os.environ
USE_GRADIO = os.getenv("HF_SPACE", "0") == "1" or os.getenv("GRADIO", "0") == "1" or IS_HF

if USE_GRADIO:
    # وضع HuggingFace Space — Gradio
    from gradio_app import demo
    if IS_HF:
        demo.launch()
    else:
        port = int(os.getenv("PORT", 7860))
        demo.launch(server_name="0.0.0.0", server_port=port, show_api=False)
else:
    # وضع FastAPI server المحلي
    import uvicorn
    from web.app import app

    if __name__ == "__main__":
        port = int(os.getenv("PORT", 6969))
        uvicorn.run("web.app:app", host="0.0.0.0", port=port)
