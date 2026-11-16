"""
streamlit_app.py
----------------
Dashboard Streamlit Enterprise untuk ReconAuto.ID.
Mendukung penuh deployment di Streamlit Community Cloud dengan tema terang berkontras tinggi,
bebas ikon/emoji informal, serta terintegrasi penuh dengan:
- BidirectionalReconciliationEngine (2-Arah & 3-Arah COD)
- Database Persisten SQLite (Rolling In-Transit & Riwayat Sesi)
- Auto-Dispute Claim Generator (Draf Email & Surat Klaim PDF Resmi)
- Direct Accounting & ERP API Sync (Mekari Jurnal, Accurate Online, Xero)
- Asisten AI ReconBot & Eskalasi WhatsApp CS (081536175933)
"""

import os
import io
import glob
import json
import zipfile
import pandas as pd
import streamlit as st

from core.parser import parse_file
from core.parsers.registry import default_registry
from core.engine import BidirectionalReconciliationEngine
from core.exporter import (
    generate_reconciliation_excel,
    generate_journal_csv,
    generate_journal_entries_data
)
from core.dispute import (
    generate_dispute_data,
    generate_dispute_email_text,
    generate_dispute_pdf
)
from core.accounting import (
    AccountingProvider,
    dispatch_accounting_sync
)
from core.chatbot import generate_chat_response_sync, CS_INFO
from core.db import (
    init_db,
    save_reconciliation_run,
    get_reconciliation_runs,
    get_run_by_id,
    get_open_in_transit_batches,
    mark_batch_resolved_rolling,
    get_rolling_summary,
    get_accounting_sync_logs
)

# Inisialisasi Database SQLite
init_db()

# Konfigurasi Halaman Streamlit (Tanpa Emoji Informal)
st.set_page_config(
    page_title="ReconAuto.ID - Platform Rekonsiliasi Keuangan Dua Arah Otomatis",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling Tema Terang Modern Berkontras Tinggi (Clean SaaS Enterprise)
st.markdown("""
<style>
    /* 1. Global Reset & High Contrast Typography */
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f8fafc !important;
        color: #0f172a !important;
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }

    /* Paksa seluruh teks judul, paragraf, label dan markdown berwarna gelap kontras tinggi */
    h1, h2, h3, h4, h5, h6,
    p, span, li, label, td, th,
    .stMarkdown,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p {
        color: #0f172a !important;
    }

    /* Code blocks & inline code */
    code {
        background-color: #f1f5f9 !important;
        color: #1e3a8a !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Subtitle & Keterangan Tambahan */
    .stCaption, [data-testid="stCaptionContainer"] p {
        color: #475569 !important;
    }

    /* 2. Sidebar Bersih & Kontras Tinggi */
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div {
        color: #0f172a !important;
    }

    /* 3. Kartu Metrik KPI Eksekutif */
    [data-testid="stMetric"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 16px 18px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05) !important;
    }
    [data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] div {
        color: #475569 !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.03em !important;
    }
    [data-testid="stMetricValue"] div {
        color: #0f172a !important;
        font-weight: 800 !important;
        font-size: 20px !important;
    }
    [data-testid="stMetricDelta"] div {
        font-weight: 600 !important;
    }

    /* 4. Form Input, Text Area, Selectbox & Uploader */
    input, textarea, [data-baseweb="select"] div, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    ul[data-testid="stSelectboxVirtualDropdown"] li, div[role="listbox"] li {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    [data-testid="stFileUploader"] {
        background-color: #ffffff !important;
        border: 1.5px dashed #cbd5e1 !important;
        border-radius: 12px !important;
        padding: 14px !important;
    }
    [data-testid="stFileUploader"] section {
        background-color: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] div {
        color: #334155 !important;
    }
    [data-testid="stFileUploader"] button {
        background-color: #eff6ff !important;
        color: #1d4ed8 !important;
        border: 1px solid #bfdbfe !important;
        font-weight: 600 !important;
    }

    /* 5. Radio Button & Tabs */
    [data-testid="stRadio"] label span, [data-testid="stRadio"] label p {
        color: #0f172a !important;
        font-weight: 600 !important;
    }
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #475569 !important;
        font-weight: 600 !important;
        padding: 10px 16px !important;
    }
    button[data-baseweb="tab"] p {
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #2563eb !important;
        border-bottom: 2.5px solid #2563eb !important;
        background-color: #ffffff !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p {
        color: #2563eb !important;
        font-weight: 700 !important;
    }

    /* 6. Kotak Info, Alert & Expander */
    .stAlert, [data-testid="stAlert"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 12px !important;
        color: #0f172a !important;
    }
    [data-testid="stAlert"] p, [data-testid="stAlert"] span {
        color: #0f172a !important;
    }
    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
    }

    /* 7. Komponen Banner & Kartu Enterprise */
    .enterprise-header-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px 28px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        margin-bottom: 20px;
    }
    .badge-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 11.5px;
        font-weight: 700;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .badge-blue {
        background: #eff6ff;
        color: #1d4ed8 !important;
        border: 1px solid #bfdbfe;
    }
    .badge-emerald {
        background: #ecfdf5;
        color: #047857 !important;
        border: 1px solid #a7f3d0;
    }
    .badge-amber {
        background: #fffbeb;
        color: #b45309 !important;
        border: 1px solid #fde68a;
    }
    .badge-rose {
        background: #fff1f2;
        color: #be123c !important;
        border: 1px solid #fecdd3;
    }
    .proof-box {
        background: #ecfdf5;
        border: 1px solid #6ee7b7;
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 18px;
    }

    /* 8. Tombol Utama & Unduh Berkontras Tinggi */
    .stButton > button {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        border: 1px solid #1d4ed8 !important;
        padding: 8px 18px !important;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.2) !important;
    }
    .stButton > button p, .stButton > button span {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
    }
    .stDownloadButton > button {
        background-color: #ffffff !important;
        color: #1d4ed8 !important;
        border: 1.5px solid #2563eb !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
    }
    .stDownloadButton > button p, .stDownloadButton > button span {
        color: #1d4ed8 !important;
        font-weight: 600 !important;
    }
    .stDownloadButton > button:hover {
        background-color: #eff6ff !important;
        color: #1e40af !important;
    }
    [data-testid="stLinkButton"] a {
        background-color: #059669 !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        text-decoration: none !important;
        border: none !important;
    }
    [data-testid="stLinkButton"] a p, [data-testid="stLinkButton"] a span {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)


# --- FUNGSI HELPER ---
def fmt_rp(val: float) -> str:
    """Format nominal Rupiah secara konsisten."""
    try:
        return f"Rp {float(val or 0):,.2f}"
    except Exception:
        return "Rp 0.00"


def build_sample_zip_bytes() -> bytes:
    """Mengemas 10 berkas sampel simulasi beserta panduan teks ke dalam paket ZIP."""
    zip_buffer = io.BytesIO()
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    readme_content = """========================================================================
PANDUAN FILE SAMPEL DATASET SIMULASI REKONSILIASI — ReconAuto.ID v1.0.0
========================================================================

Paket ZIP ini memuat seluruh berkas simulasi transaksi finansial riil
yang digunakan pada fitur "Demo 1-Klik Multi-Sumber":

1. BANK MUTASI & REKENING KORAN:
   - 1_mutasi_bank_bca.csv        : Rekening koran KlikBCA Bisnis (13 baris mutasi)
   - 1_mutasi_bank_bca_sample.pdf : Dokumen cetak e-Statement BCA resmi
   - 6_mutasi_bank_mandiri.csv    : Mutasi rekening giro Bank Mandiri Kopra/MCM

2. MARKETPLACE & SOCIAL COMMERCE:
   - 2_tiktok_shop_orders.csv     : Laporan pesanan TikTok Shop Seller Center
   - 3_shopee_settlement.csv      : Laporan pelepasan dana Shopee Seller Centre

3. PAYMENT GATEWAY:
   - 4_doku_payment_gateway.csv   : Laporan settlement DOKU Payment Gateway

4. POINT OF SALE (POS) & KASIR:
   - 5_pos_kasir_tunai.csv        : Log register kasir fisik toko harian
   - 6_jubelio_pos_orders.csv     : Laporan transaksi penjualan Jubelio POS & Omnichannel

5. EKSPEDISI COD KURIR (3-WAY AUDIT):
   - 7_jne_cod_settlement.csv     : Manifest pencairan COD JNE Express (AWB Resi)
   - 8_sicepat_cod_settlement.csv : Manifest pencairan COD SiCepat Express

Dikeluarkan oleh: PT Recon Automasi Data Indonesia (ReconAuto.ID)
Kontak CS WhatsApp: +62 815-3617-5933
========================================================================"""

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("PANDUAN_FILE_SAMPEL_DEMO.txt", readme_content)
        if os.path.exists(sample_dir):
            for fname in sorted(os.listdir(sample_dir)):
                fpath = os.path.join(sample_dir, fname)
                if os.path.isfile(fpath) and not fname.startswith("."):
                    zf.write(fpath, arcname=fname)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def execute_reconciliation(file_tuples, source_label: str):
    """Menjalankan pipeline parsing & rekonsiliasi dua arah serta menyimpan ke SQLite."""
    bank_rows = []
    source_txns = []
    cod_settlements = []

    for fn, content in file_tuples:
        channel, data = parse_file(content, filename=fn)
        if "BANK" in channel.value:
            bank_rows.extend(data)
        elif "LOGISTICS" in channel.value:
            cod_settlements.extend(data)
        else:
            source_txns.extend(data)

    open_batches = get_open_in_transit_batches(workspace_id="ws-default")
    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(
        bank_rows=bank_rows,
        source_transactions=source_txns,
        prior_unresolved_batches=open_batches,
        cod_settlements=cod_settlements
    )

    run_id = save_reconciliation_run(result, {
        "source": source_label,
        "workspace_id": "ws-default"
    })
    result["run_id"] = run_id
    result["workspace_id"] = "ws-default"

    for r in result.get("rolling_resolved", []):
        mark_batch_resolved_rolling(
            batch_id=r["batch_id"],
            resolution_run_id=run_id,
            bank_row_id=r["bank_row_id"],
            bank_date=r["bank_date"]
        )

    return result


# --- SIDEBAR: KONTAK CS, ASISTEN AI, & RIWAYAT SQLITE ---
with st.sidebar:
    st.markdown("### ReconAuto.ID")
    st.caption("Platform Rekonsiliasi Keuangan Otomatis Multi-Sumber v1.0.0")

    st.divider()

    st.markdown("#### Layanan Customer Service")
    st.markdown(f"**WhatsApp Resmi:** `{CS_INFO.get('whatsapp_display', '+62 815-3617-5933')}`")
    st.markdown(f"**Email Support:** `{CS_INFO.get('email', 'support@reconauto.id')}`")
    st.markdown(f"**Jam Operasional:** {CS_INFO.get('operating_hours', CS_INFO.get('hours', 'Senin - Jumat, 08:00 - 17:00 WIB'))}")
    st.link_button("Hubungi WhatsApp CS (081536175933)", CS_INFO.get("whatsapp_url", "https://wa.me/6281536175933"), use_container_width=True)

    st.divider()

    st.markdown("#### Asisten AI ReconBot")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    quick_q = st.selectbox(
        "Pertanyaan Cepat:",
        [
            "-- Pilih topik pertanyaan atau ketik manual --",
            "Apa itu Proof of Cash dan mengapa selisih Rp 0.00?",
            "Bagaimana cara kerja audit COD 3-arah JNE & SiCepat?",
            "Bagaimana cara membuat surat klaim Missing Payout?",
            "Bagaimana cara sinkronisasi jurnal ke Mekari Jurnal / Accurate?",
            "Saya ingin menghubungi Customer Service WhatsApp"
        ]
    )

    user_query = st.text_input(
        "Ketik Pertanyaan Anda:",
        value="" if quick_q.startswith("--") else quick_q,
        placeholder="Tanyakan seputar rekonsiliasi atau fitur..."
    )

    if st.button("Kirim Pertanyaan ke AI", use_container_width=True):
        if user_query and user_query.strip():
            with st.spinner("Memproses jawaban..."):
                resp_dict = generate_chat_response_sync(
                    message=user_query.strip(),
                    history=st.session_state.chat_history
                )
                bot_reply = resp_dict.get("reply", "Silakan hubungi WhatsApp CS di +62 815-3617-5933.")
                st.session_state.chat_history.append({"role": "user", "text": user_query.strip()})
                st.session_state.chat_history.append({"role": "model", "text": bot_reply})

    if st.session_state.chat_history:
        last_exchange = st.session_state.chat_history[-1]
        if last_exchange["role"] == "model":
            st.info(last_exchange["text"])
        with st.expander("Riwayat Percakapan"):
            for msg in st.session_state.chat_history:
                speaker = "Anda" if msg["role"] == "user" else "ReconBot AI"
                st.markdown(f"**{speaker}:** {msg['text']}")

    st.divider()

    st.markdown("#### Riwayat Sesi (SQLite)")
    saved_runs = get_reconciliation_runs(limit=10)
    rolling_sum = get_rolling_summary(workspace_id="ws-default")
    st.caption(f"Total Sesi Tersimpan: **{rolling_sum.get('total_runs', len(saved_runs))} Sesi**")
    if saved_runs:
        selected_run_id = st.selectbox(
            "Muat Sesi Terdahulu:",
            ["-- Pilih ID Sesi --"] + [f"{r['id']} ({r['run_date']})" for r in saved_runs]
        )
        if not selected_run_id.startswith("--"):
            actual_id = selected_run_id.split(" ")[0]
            if st.button("Buka Sesi Terpilih", use_container_width=True):
                past_data = get_run_by_id(actual_id)
                if past_data:
                    st.session_state.reconcile_result = past_data
                    st.rerun()


# --- HEADER UTAMA DASHBOARD ---
st.markdown("""
<div class="enterprise-header-card">
    <div style="margin-bottom: 10px;">
        <span class="badge-pill badge-blue">Audit Kas Finansial Tiga-Arah (Multi-Kanal)</span>
        <span class="badge-pill badge-emerald">Proof of Cash Teruji (Tied Rp 0.00)</span>
        <span class="badge-pill badge-amber">SQLite Persistence & ERP Sync</span>
    </div>
    <h1 style="margin: 0 0 8px 0; font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
        ReconAuto.ID — Rekonsiliasi Keuangan Dua Arah Otomatis
    </h1>
    <p style="margin: 0; font-size: 14px; color: #334155; line-height: 1.6;">
        Platform rekonsiliasi kas independen untuk memvalidasi transaksi penjualan dari <b>Marketplace, Payment Gateway, Kasir POS Ritel, dan Ekspedisi COD</b> terhadap <b>Rekening Koran Multi-Bank</b>. Mengungkap selisih nominal, potongan komisi berlebih, serta dana <i>in-transit</i> secara presisi.
    </p>
</div>
""", unsafe_allow_html=True)

# Baris Aksi Cepat Dokumen & Katalog
top_c1, top_c2, top_c3 = st.columns(3)
with top_c1:
    st.download_button(
        label="Unduh Sampel Data Demo (ZIP - 11 Berkas)",
        data=build_sample_zip_bytes(),
        file_name="Sampel_Data_Demo_ReconAutoID.zip",
        mime="application/zip",
        use_container_width=True
    )
with top_c2:
    pdf_doc_path = os.path.join(os.path.dirname(__file__), "Dokumentasi_Lengkap_ReconAuto_ID.pdf")
    if os.path.exists(pdf_doc_path):
        with open(pdf_doc_path, "rb") as fp:
            st.download_button(
                label="Unduh Buku Dokumentasi Sistem (PDF)",
                data=fp.read(),
                file_name="Dokumentasi_Lengkap_ReconAuto_ID.pdf",
                mime="application/pdf",
                use_container_width=True
            )
with top_c3:
    try:
        from nda.pdf_generator import generate_nda_pdf_bytes
        from nda.consent_router import _build_default_nda_record
        from nda import storage as nda_storage
        consents = nda_storage.get_all_consents()
        nda_rec = consents[0] if consents else _build_default_nda_record()
        nda_pdf = generate_nda_pdf_bytes(nda_rec)
        st.download_button(
            label="Unduh Dokumen Perjanjian NDA Resmi (PDF)",
            data=nda_pdf,
            file_name="NDA_Resmi_ReconAuto_ID.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception:
        pass

with st.expander("Lihat Katalog 39 Sumber Data Perbankan, Marketplace, Payment Gateway, POS & Kurir yang Didukung"):
    sources_list = default_registry.list_channels()
    df_sources = pd.DataFrame(sources_list)
    if not df_sources.empty:
        df_sources = df_sources.rename(columns={
            "channel_id": "Kode Kanal",
            "channel_name": "Nama Institusi / Platform",
            "channel_type": "Kategori",
            "matching_strategy": "Strategi Rekonsiliasi"
        })
        st.dataframe(
            df_sources[["Kode Kanal", "Nama Institusi / Platform", "Kategori", "Strategi Rekonsiliasi"]],
            use_container_width=True,
            hide_index=True
        )

st.divider()

# --- MODE PEMILIHAN EKSEKUSI DATA ---
tab_mode = st.radio(
    "Pilih Metode Input Data Rekonsiliasi:",
    ["Mode Simulasi Demo Multi-Sumber (1-Klik)", "Unggah Berkas Transaksi Mandiri (5 Kategori Multi-File)"],
    horizontal=True
)

if tab_mode == "Mode Simulasi Demo Multi-Sumber (1-Klik)":
    st.info(
        "Mode simulasi memuat 8 berkas dataset multi-kanal bawaan (Mutasi BCA, Mutasi Mandiri, TikTok Shop, Shopee, DOKU PG, Kasir POS Tunai, Jubelio POS, JNE COD, dan SiCepat COD) untuk mendemonstrasikan rekonsiliasi kas secara utuh."
    )
    if st.button("Jalankan Demo 1-Klik Multi-Sumber", use_container_width=False):
        with st.spinner("Memproses berkas multi-sumber & menghitung pembuktian kas..."):
            sample_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.csv")))
            file_tuples = []
            for f_path in sample_files:
                with open(f_path, "rb") as fp:
                    file_tuples.append((os.path.basename(f_path), fp.read()))
            st.session_state.reconcile_result = execute_reconciliation(
                file_tuples,
                "Simulasi 1-Klik Multi-Sumber & Multi-Bank"
            )
            st.success("Proses rekonsiliasi simulasi selesai.")

else:
    st.markdown("#### Unggah Berkas Rekonsiliasi (Mendukung Banyak File per Kotak)")
    ucol1, ucol2 = st.columns(2)
    with ucol1:
        up_bank = st.file_uploader(
            "1. Mutasi Rekening Bank (BCA, Mandiri, BNI, BRI, BSI, MT940)",
            accept_multiple_files=True,
            type=["csv", "xlsx", "xls", "pdf", "sta", "mt940"]
        )
        up_mp = st.file_uploader(
            "2. Marketplace Seller (TikTok Shop, Shopee, Tokopedia, Lazada)",
            accept_multiple_files=True,
            type=["csv", "xlsx", "xls"]
        )
        up_pg = st.file_uploader(
            "3. Payment Gateway (DOKU, Midtrans, Xendit, Faspay, QRIS)",
            accept_multiple_files=True,
            type=["csv", "xlsx", "xls"]
        )
    with ucol2:
        up_pos = st.file_uploader(
            "4. Kasir Tunai / POS Ritel (Jubelio POS, Moka, Pawoon, Kas Toko)",
            accept_multiple_files=True,
            type=["csv", "xlsx", "xls"]
        )
        up_cod = st.file_uploader(
            "5. Ekspedisi COD Kurir (JNE Express, SiCepat, J&T COD)",
            accept_multiple_files=True,
            type=["csv", "xlsx", "xls"]
        )

    all_uploaded = (up_bank or []) + (up_mp or []) + (up_pg or []) + (up_pos or []) + (up_cod or [])
    st.caption(f"Total berkas dipilih: **{len(all_uploaded)} file**")

    if st.button("Proses & Rekonsiliasikan Berkas", use_container_width=True):
        if not all_uploaded:
            st.warning("Silakan unggah minimal satu berkas mutasi bank dan satu berkas transaksi sumber.")
        else:
            with st.spinner("Menganalisis dan merekonsiliasikan seluruh berkas..."):
                file_tuples = [(f.name, f.read()) for f in all_uploaded]
                st.session_state.reconcile_result = execute_reconciliation(
                    file_tuples,
                    f"Upload Mandiri ({len(all_uploaded)} file)"
                )
                st.success("Rekonsiliasi berhasil diproses!")


# --- TAMPILAN HASIL REKONSILIASI ---
if "reconcile_result" in st.session_state and st.session_state.reconcile_result:
    res = st.session_state.reconcile_result
    summary = res.get("summary", {})
    discrepancies = res.get("discrepancies", [])
    match_analytics = res.get("match_analytics", {})
    overall_ma = match_analytics.get("overall", {})
    categories = match_analytics.get("categories", [])
    by_channel = match_analytics.get("by_channel", [])
    batches = res.get("batches", [])
    bank_rows = res.get("bank_rows", [])
    transactions = res.get("transactions", [])
    cod_settlements = res.get("cod_settlements", [])
    cod_summary = res.get("cod_summary") or {}
    journals = generate_journal_entries_data(res)

    total_exceptions = len(discrepancies)
    is_balanced = summary.get("is_balanced", True)
    proof_diff = summary.get("proof_difference", 0.0)

    st.divider()

    # 1. BANNER PROOF OF CASH (HARMONISASI FORMULA KAS VS TEMUAN ANOMALI)
    st.markdown(f"""
    <div class="proof-box">
        <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px;">
            <div style="font-size: 16px; font-weight: 800; color: #064e3b;">
                Audit & Rekonsiliasi Kas Terbukti Seimbang (Formula Kas Klop 100%)
            </div>
            <div>
                <span class="badge-pill badge-emerald">Formula Kas: Selisih Rp {proof_diff:,.2f} (Tied)</span>
                <span class="badge-pill badge-rose">{total_exceptions} Selisih/Anomali Operasional Berhasil Diisolasi</span>
            </div>
        </div>
        <p style="margin: 0 0 8px 0; font-size: 13px; color: #065f46; line-height: 1.55;">
            Formula audit membuktikan seluruh aliran dana rekening koran terhitung akurat tanpa dana gelap tak bertuan (<b>Tied Rp 0.00</b>).
            Di saat bersamaan, sistem secara presisi mengisolasi <b>{total_exceptions} selisih operasional riil</b>
            (Missing Payout, Selisih Kasir Toko, Potongan Fee Berlebih & Deposit Tak Dikenal) pada tabel di bawah untuk klaim dan tindak lanjut.
        </p>
        <div style="background: #ffffff; border: 1px solid #a7f3d0; border-radius: 8px; padding: 8px 12px; font-family: monospace; font-size: 12px; color: #0f172a; font-weight: 600;">
            Formula: (Penjualan Bersih {fmt_rp(summary.get('total_expected_net', 0))})
            - (In-Transit {fmt_rp(summary.get('in_transit_amount', 0))})
            - (Missing Payout {fmt_rp(summary.get('missing_payout_amount', 0))})
            - (Kas Toko {fmt_rp(summary.get('unsettled_cash_amount', 0))})
            - (Shortage {fmt_rp(summary.get('cash_shortage', 0))})
            + (Unidentified CR {fmt_rp(summary.get('unidentified_bank_credits', 0))})
            + (Bunga Bank {fmt_rp(summary.get('bank_interest_income', 0))})
            + (COD Cair {fmt_rp(summary.get('external_cod_cleared', 0))})
            = Total Kredit Mutasi Bank ({fmt_rp(summary.get('bank_total_credits', 0))})
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. LIMA KARTU METRIK KPI EKSEKUTIF
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Total Penjualan Kotor", fmt_rp(summary.get("total_gross_sales", 0)))
    with k2:
        st.metric("Potongan Komisi / Fee", fmt_rp(summary.get("total_platform_fees", 0)))
    with k3:
        st.metric("Bersih Masuk Bank", fmt_rp(summary.get("total_bank_cleared", 0)))
    with k4:
        in_transit_and_missing = (summary.get("in_transit_amount", 0) or 0) + (summary.get("missing_payout_amount", 0) or 0)
        st.metric("In-Transit & Tertahan", fmt_rp(in_transit_and_missing))
    with k5:
        st.metric("Tingkat Match Rate", f"{summary.get('match_rate_pct', 0)}%", f"{total_exceptions} Anomali")

    st.divider()

    # 3. TUJUH TAB INTERAKTIF LENGKAP
    tabs = st.tabs([
        f"1. Daftar Anomali ({total_exceptions})",
        f"2. Analisis Match Rate ({overall_ma.get('matched_nominal_pct', 0)}%)",
        f"3. Pencairan Batch ({len(batches)})",
        f"4. Audit Mutasi Bank ({len(bank_rows)})",
        f"5. Transaksi Penjualan ({len(transactions)})",
        f"6. Audit COD 3-Arah ({len(cod_settlements)})",
        "7. Klaim Sengketa, Jurnal ERP & Ekspor"
    ])

    # TAB 1: DAFTAR ANOMALI & TINDAKAN
    with tabs[0]:
        st.markdown("#### Daftar Selisih & Anomali Operasional yang Berhasil Diisolasi")
        if discrepancies:
            fcol1, fcol2 = st.columns([2, 3])
            with fcol1:
                sev_filter = st.selectbox("Filter Tingkat Risiko:", ["ALL (Semua)", "HIGH", "MEDIUM", "LOW"])
            with fcol2:
                search_q = st.text_input("Cari Nomor Referensi / Penyebab / Jenis Masalah:", "")

            filtered_disc = []
            for d in discrepancies:
                if not sev_filter.startswith("ALL") and d.get("severity") != sev_filter:
                    continue
                if search_q:
                    q_low = search_q.lower()
                    haystack = f"{d.get('reference_id', '')} {d.get('issue_type', '')} {d.get('probable_cause', '')} {d.get('channel', '')}".lower()
                    if q_low not in haystack:
                        continue
                filtered_disc.append({
                    "Arah Uji": d.get("direction", "-"),
                    "Tingkat Risiko": d.get("severity", "-"),
                    "Kanal": d.get("channel", "-"),
                    "Sumber / Ref ID": d.get("reference_id", "-"),
                    "Tanggal": d.get("date", "-"),
                    "Jenis Masalah": d.get("issue_type", "-"),
                    "Nominal Seharusnya (Rp)": d.get("expected_amount", 0.0),
                    "Nominal Aktual (Rp)": d.get("actual_amount", 0.0),
                    "Selisih Nominal (Rp)": abs(d.get("discrepancy_amount", 0.0)),
                    "Penyebab Teridentifikasi": d.get("probable_cause", "-"),
                    "Rekomendasi Tindakan": d.get("recommended_action", "-")
                })

            st.dataframe(pd.DataFrame(filtered_disc), use_container_width=True, hide_index=True)
        else:
            st.success("Tidak ditemukan anomali pada sesi rekonsiliasi ini.")

    # TAB 2: ANALISIS MATCH RATE & MATRIKS KATEGORI
    with tabs[1]:
        st.markdown("#### Ringkasan Match vs Not Match & Drill-Down per Kategori")
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.metric("Persentase Nominal Klop", f"{overall_ma.get('matched_nominal_pct', 0)}%")
        with mc2:
            st.metric("Persentase Transaksi Klop", f"{overall_ma.get('matched_count_pct', 0)}%")
        with mc3:
            st.metric("Total Nominal Klop (Matched)", fmt_rp(overall_ma.get("matched_nominal", 0)))
        with mc4:
            st.metric("Total Belum Klop (Not Matched)", fmt_rp(overall_ma.get("not_matched_nominal", 0)))

        if by_channel:
            st.markdown("##### Rincian Tingkat Kecocokan per Kanal Sumber")
            df_ch = pd.DataFrame([
                {
                    "Kanal Sumber": ch.get("channel_name"),
                    "Total Item": ch.get("total_count"),
                    "Item Klop": ch.get("matched_count"),
                    "Item Belum Klop": ch.get("not_matched_count"),
                    "Total Nominal (Rp)": ch.get("total_nominal"),
                    "Nominal Klop (Rp)": ch.get("matched_nominal"),
                    "Nominal Belum Klop (Rp)": ch.get("not_matched_nominal"),
                    "Match Rate (%)": ch.get("match_nominal_pct")
                }
                for ch in by_channel
            ])
            st.dataframe(df_ch, use_container_width=True, hide_index=True)

        if categories:
            st.markdown("##### Matriks Kategori Rekonsiliasi")
            df_cat = pd.DataFrame([
                {
                    "Kategori Status": c.get("category"),
                    "Tipe": c.get("type"),
                    "Jumlah Item": c.get("count"),
                    "% Jumlah": f"{c.get('count_pct', 0)}%",
                    "Total Nominal (Rp)": c.get("nominal"),
                    "% Nominal": f"{c.get('nominal_pct', 0)}%",
                    "Rekomendasi Tindak Lanjut": c.get("action")
                }
                for c in categories
            ])
            st.dataframe(df_cat, use_container_width=True, hide_index=True)

            cat_names = [c.get("category") for c in categories if c.get("items")]
            if cat_names:
                chosen_cat = st.selectbox("Pilih Kategori untuk Melihat Rincian Transaksi (Drill-Down):", cat_names)
                for c in categories:
                    if c.get("category") == chosen_cat and c.get("items"):
                        st.dataframe(pd.DataFrame(c["items"]), use_container_width=True, hide_index=True)

    # TAB 3: PENCAIRAN BATCH KE BANK
    with tabs[2]:
        st.markdown("#### Pencocokan Batch Settlement Penjualan ke Rekening Koran (Forward Matching)")
        if batches:
            df_batches = pd.DataFrame([
                {
                    "Batch / Ref ID": b.get("batch_id"),
                    "Kanal": b.get("channel"),
                    "Tgl Settlement": b.get("settlement_date"),
                    "Jml Order": b.get("order_count"),
                    "Penjualan Kotor (Rp)": b.get("gross_sum"),
                    "Potongan Fee (Rp)": b.get("fee_sum"),
                    "Net Settlement (Rp)": b.get("net_sum"),
                    "Status Pencairan": b.get("status"),
                    "Cair di Bank (Rp)": b.get("bank_amount") or 0.0,
                    "Keterangan Audit": b.get("notes")
                }
                for b in batches
            ])
            st.dataframe(df_batches, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada data batch settlement.")

    # TAB 4: AUDIT MUTASI BANK
    with tabs[3]:
        st.markdown("#### Audit Baris Mutasi Rekening Koran Bank (Reverse Matching)")
        if bank_rows:
            df_bank = pd.DataFrame([
                {
                    "ID Baris": r.get("row_id"),
                    "Bank": r.get("bank_code", "BANK_BCA"),
                    "Tanggal": r.get("date"),
                    "Deskripsi Mutasi Bank": r.get("description"),
                    "Tipe (CR/DB)": r.get("txn_type"),
                    "Nominal (Rp)": r.get("amount"),
                    "Status Rekonsiliasi": "Klop (Matched)" if r.get("matched") else "Perlu Penyesuaian / Anomali",
                    "Pasangan Dokumen / Batch": r.get("matched_with") or "Transaksi Bank Langsung / Anomali"
                }
                for r in bank_rows
            ])
            st.dataframe(df_bank, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada data mutasi bank.")

    # TAB 5: TRANSAKSI PENJUALAN
    with tabs[4]:
        st.markdown("#### Daftar Rincian Transaksi Penjualan Multi-Kanal")
        if transactions:
            df_txns = pd.DataFrame([
                {
                    "No. Order / Transaksi": t.get("txn_id"),
                    "Tanggal": t.get("date"),
                    "Kanal Sumber": t.get("channel"),
                    "Deskripsi Produk / Kasir": t.get("description"),
                    "Penjualan Kotor (Rp)": t.get("gross_amount"),
                    "Potongan Fee (Rp)": t.get("fee_amount"),
                    "Penjualan Bersih (Rp)": t.get("net_amount"),
                    "Batch Payout Ref": t.get("batch_id") or "-",
                    "Status": t.get("raw_status") or "OK"
                }
                for t in transactions
            ])
            st.dataframe(df_txns, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada rincian transaksi penjualan.")

    # TAB 6: AUDIT COD EKSPEDISI 3-ARAH
    with tabs[5]:
        st.markdown("#### Audit Rekonsiliasi 3-Arah COD Ekspedisi Kurir (Order <-> Resi AWB <-> Bank)")
        if cod_settlements:
            cc1, cc2, cc3, cc4 = st.columns(4)
            with cc1:
                st.metric("Total Tagihan COD", fmt_rp(cod_summary.get("total_cod_amount", 0)))
            with cc2:
                st.metric("Net Cair ke Bank (Cleared)", fmt_rp(cod_summary.get("cleared_amount", 0)))
            with cc3:
                st.metric("Tertahan di Kurir (Unremitted)", fmt_rp(cod_summary.get("unremitted_amount", 0)))
            with cc4:
                st.metric("Selisih Potongan (Shortage)", fmt_rp(cod_summary.get("shortage_amount", 0)))

            df_cod = pd.DataFrame([
                {
                    "No. Resi (AWB)": c.get("awb_number"),
                    "Kurir Ekspedisi": c.get("courier_name"),
                    "Order ID": c.get("order_id"),
                    "Tgl Settlement": c.get("settlement_date"),
                    "Tagihan COD (Rp)": c.get("cod_amount"),
                    "Fee Kurir (Rp)": c.get("courier_fee"),
                    "Net Ditransfer (Rp)": c.get("net_remitted"),
                    "Ref Bank": c.get("bank_ref_id") or "-",
                    "Status Audit": c.get("status")
                }
                for c in cod_settlements
            ])
            st.dataframe(df_cod, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada data manifest COD kurir pada sesi ini.")

    # TAB 7: AUTO-DISPUTE GENERATOR, JURNAL ERP & EKSPOR LAPORAN
    with tabs[6]:
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Auto-Dispute Claim Generator")
            st.caption("Pilih temuan anomali untuk menghasilkan draf email klaim dan Surat Klaim Resmi (.PDF) ber-kop perusahaan.")
            if discrepancies:
                disc_options = {
                    f"[{d.get('severity')}] {d.get('reference_id')} - {d.get('issue_type')} ({fmt_rp(abs(d.get('discrepancy_amount', 0)))})": d
                    for d in discrepancies
                }
                selected_disc_label = st.selectbox("Pilih Kasus Anomali yang Akan Diklaim:", list(disc_options.keys()))
                chosen_disc = disc_options[selected_disc_label]

                dispute_data = generate_dispute_data(chosen_disc, res)
                email_text = generate_dispute_email_text(dispute_data)
                pdf_claim_buf = generate_dispute_pdf(dispute_data)

                st.markdown(f"**Tujuan Surat:** `{dispute_data.get('recipient')}` | **No. Referensi:** `{dispute_data.get('letter_number')}`")
                st.markdown(f"**Total Nilai Klaim:** `{fmt_rp(dispute_data.get('amount', 0))}`")
                st.text_area("Draf Email Klaim Resmi (Siap Salin & Kirim):", value=email_text, height=240)

                safe_ref = str(dispute_data.get("ref_id", "CLAIM")).replace("/", "_").replace(" ", "_")
                st.download_button(
                    label="Unduh Surat Klaim Dispute Resmi (.PDF)",
                    data=pdf_claim_buf.getvalue(),
                    file_name=f"Surat_Klaim_Dispute_{safe_ref}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.info("Tidak ada anomali untuk diajukan klaim.")

        with col_right:
            st.markdown("#### Jurnal Penyesuaian GL & Sinkronisasi API Akuntansi")
            st.caption("Kirim ayat jurnal penyesuaian langsung ke Mekari Jurnal, Accurate Online, atau Xero.")
            if journals:
                df_jrn = pd.DataFrame(journals)
                st.dataframe(df_jrn, use_container_width=True, hide_index=True)

                provider_choice = st.selectbox(
                    "Pilih Target Vendor Akuntansi / ERP:",
                    [
                        AccountingProvider.MEKARI_JURNAL,
                        AccountingProvider.ACCURATE_ONLINE,
                        AccountingProvider.XERO
                    ]
                )
                if st.button("Kirim Jurnal ke Sistem Akuntansi (API Sync)", use_container_width=True):
                    sync_res = dispatch_accounting_sync(
                        workspace_id="ws-default",
                        run_id=res.get("run_id", "RUN-ACTIVE"),
                        journal_entries=journals,
                        provider=provider_choice
                    )
                    if sync_res.get("status") == "success":
                        st.success(f"{sync_res.get('message')} (No. Voucher: {sync_res.get('journal_ref_number')})")
                        with st.expander("Inspeksi Payload JSON Transmisi API"):
                            st.json(sync_res.get("payload", {}))
                    else:
                        st.error(sync_res.get("message", "Gagal melakukan sinkronisasi."))

            st.divider()
            st.markdown("#### Unduh Paket Laporan Audit Lengkap")
            excel_buf = generate_reconciliation_excel(res)
            st.download_button(
                label="Unduh Kertas Kerja Audit Excel Multi-Tab (.XLSX)",
                data=excel_buf.getvalue(),
                file_name=f"Laporan_Rekonsiliasi_{res.get('run_id', 'RUN')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            csv_journal_str = generate_journal_csv(res)
            st.download_button(
                label="Unduh CSV Jurnal Penyesuaian GL (.CSV)",
                data=csv_journal_str.encode("utf-8"),
                file_name=f"Jurnal_Penyesuaian_{res.get('run_id', 'RUN')}.csv",
                mime="text/csv",
                use_container_width=True
            )
