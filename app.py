"""
app.py
------
Entrypoint resmi untuk Hugging Face Spaces (SDK: Gradio).
Memadukan backend & frontend FastAPI ReconAuto.ID langsung ke dalam runtime Gradio.
"""

import gradio as gr
from main import app as fastapi_app

# Inisialisasi antarmuka Gradio
with gr.Blocks(title="ReconAuto.ID - Platform Rekonsiliasi Keuangan Dua Arah Otomatis") as demo:
    gr.HTML("""
        <div style="text-align: center; padding: 20px;">
            <p>Memuat Dashboard ReconAuto.ID...</p>
        </div>
    """)

# Daftarkan seluruh rute ReconAuto.ID (Dashboard, API, Static Files) ke demo.app
for route in fastapi_app.router.routes:
    demo.app.router.routes.insert(0, route)

if __name__ == "__main__":
    demo.launch(ssr_mode=False)
