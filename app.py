"""
app.py
------
Entrypoint multi-platform ReconAuto.ID:
1. Mendukung Streamlit Cloud (`streamlit run app.py` / `streamlit run streamlit_app.py`).
2. Mendukung Hugging Face Spaces / Gradio (`python app.py`).
3. Mendukung FastAPI Uvicorn untuk deployment production berbayar (`uvicorn main:app`).
"""

import sys

# Deteksi apakah dijalankan dalam konteks Streamlit
is_streamlit = False
try:
    if any("streamlit" in arg for arg in sys.argv):
        is_streamlit = True
    else:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is not None:
            is_streamlit = True
except Exception:
    pass

if is_streamlit:
    import streamlit_app
else:
    # Mode Standalone / Hugging Face Spaces Gradio
    try:
        import gradio as gr
        from main import app as fastapi_app

        with gr.Blocks(title="ReconAuto.ID - Platform Rekonsiliasi Keuangan Dua Arah Otomatis") as demo:
            gr.HTML("""
                <div style="text-align: center; padding: 20px;">
                    <p>Memuat Dashboard ReconAuto.ID...</p>
                </div>
            """)

        for route in fastapi_app.router.routes:
            demo.app.router.routes.insert(0, route)

        if __name__ == "__main__":
            demo.launch(ssr_mode=False)
    except Exception:
        # Fallback aman ke dashboard Streamlit
        import streamlit_app
