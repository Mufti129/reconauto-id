"""
main.py
-------
Server Web FastAPI untuk Platform Rekonsiliasi Otomatis Multi-Sumber (Uji Dua Arah).
"""

import os
import io
import glob
import zipfile
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.parser import parse_file
from core.parsers.registry import default_registry
from core.engine import BidirectionalReconciliationEngine
from core.exporter import (
    generate_reconciliation_excel,
    generate_journal_csv,
    generate_journal_entries_data
)
from core.models import SourceChannel, CodSettlementRow
from core.dispute import (
    generate_dispute_data,
    generate_dispute_email_text,
    generate_dispute_pdf
)
from core.db import (
    init_db,
    save_reconciliation_run,
    get_reconciliation_runs,
    get_run_by_id,
    get_open_in_transit_batches,
    mark_batch_resolved_rolling,
    get_rolling_summary,
    get_workspaces,
    get_workspace_by_id,
    save_workspace,
    save_accounting_sync_log,
    get_accounting_sync_logs,
    get_cod_settlements
)
from core.accounting import (
    AccountingProvider,
    build_accounting_payload,
    dispatch_accounting_sync
)
from core.chatbot import generate_chat_response, CS_INFO


# Inisialisasi Database SQLite lokal
init_db()

app = FastAPI(title="ReconAuto.ID - Platform Rekonsiliasi Otomatis Multi-Sumber", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrasi Router NDA Digital
from nda.consent_router import router as nda_router
app.include_router(nda_router)

# Mount folder static
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# In-memory cache untuk menyimpan hasil rekonsiliasi terakhir agar bisa diunduh
LATEST_RESULT = None

# ==========================================
# 1. ENDPOINTS REKONSILIASI DUA ARAH & MULTI-SUMBER
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/sources")
async def get_supported_sources():
    """Mengembalikan daftar seluruh kanal sumber data yang didukung oleh Adapter Strategy Pattern."""
    sources = default_registry.list_channels()
    return {
        "status": "success",
        "sources": sources,
        "total_sources": len(sources)
    }

@app.get("/api/demo")
async def run_demo(workspace_id: str = "ws-default"):
    """Memuat dataset simulasi dummy dari folder sample_data/ dan langsung menjalankan rekonsiliasi."""
    global LATEST_RESULT
    sample_files = glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.csv"))
    
    if not sample_files:
        return {"status": "error", "message": "File sample_data/*.csv tidak ditemukan. Jalankan data_generator.py terlebih dahulu."}

    bank_rows = []
    source_txns = []
    cod_settlements = []

    for f_path in sorted(sample_files):
        filename = os.path.basename(f_path)
        with open(f_path, "rb") as fp:
            content = fp.read()
            channel, data = parse_file(content, filename=filename)
            if "BANK" in channel.value:
                bank_rows.extend(data)
            elif "LOGISTICS" in channel.value:
                cod_settlements.extend(data)
            else:
                source_txns.extend(data)

    open_batches = get_open_in_transit_batches(workspace_id=workspace_id)
    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(
        bank_rows=bank_rows,
        source_transactions=source_txns,
        prior_unresolved_batches=open_batches,
        cod_settlements=cod_settlements
    )

    # Simpan sesi rekonsiliasi ke SQLite dengan workspace_id
    run_id = save_reconciliation_run(result, {
        "source": "Simulasi 1-Klik Multi-Sumber & Multi-Bank (8 File)",
        "workspace_id": workspace_id
    })
    result["run_id"] = run_id
    result["workspace_id"] = workspace_id

    for r in result.get("rolling_resolved", []):
        mark_batch_resolved_rolling(
            batch_id=r["batch_id"],
            resolution_run_id=run_id,
            bank_row_id=r["bank_row_id"],
            bank_date=r["bank_date"]
        )

    LATEST_RESULT = result
    journals = generate_journal_entries_data(result)

    return {
        "status": "success",
        "run_id": run_id,
        "workspace_id": workspace_id,
        "data": result,
        "journals": journals,
        "rolling_summary": get_rolling_summary(workspace_id=workspace_id)
    }

@app.get("/api/sample-data/download")
def download_sample_data_zip():
    """Mengemas seluruh berkas sampel dataset simulasi demo ke dalam file ZIP untuk diunduh nasabah."""
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

SKENARIO ANOMALI YANG DAPAT DIUJI:
- In-Transit Lag       : Payout platform yang baru cair beberapa hari kemudian
- Missing Bank Payout  : Dana sudah selesai di marketplace tapi belum masuk bank
- Fee Overcharge       : Potongan komisi platform melebihi batas kategori (misal 9% vs 5%)
- Cash Shortage Kasir  : Setoran fisik kasir ke CDM bank kurang Rp 200.000
- Unidentified Credit  : Transfer masuk bank tanpa nomor invoice / pesanan
- Bunga & Biaya Bank   : Pendapatan bunga giro & administrasi bank

Seluruh berkas ini dapat langsung diunggah ke 5 kotak upload di antarmuka ReconAuto.ID.
Dikeluarkan oleh: PT Recon Automasi Data Indonesia (ReconAuto.ID)
========================================================================"""

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("PANDUAN_FILE_SAMPEL_DEMO.txt", readme_content)
        if os.path.exists(sample_dir):
            for fname in sorted(os.listdir(sample_dir)):
                fpath = os.path.join(sample_dir, fname)
                if os.path.isfile(fpath) and not fname.startswith("."):
                    zip_file.write(fpath, arcname=fname)
                    
    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="Sampel_Data_Demo_ReconAutoID.zip"',
            "Cache-Control": "no-cache"
        }
    )

@app.post("/api/reconcile")
async def reconcile_files(request: Request, files: List[UploadFile] = File(...)):
    """Menerima berkas upload pengguna dari berbagai kanal dan melakukan rekonsiliasi dua arah."""
    global LATEST_RESULT
    if not files:
        return {"status": "error", "message": "Tidak ada file yang diunggah."}

    workspace_id = request.query_params.get("workspace_id", "ws-default")

    bank_rows = []
    source_txns = []
    cod_settlements = []

    for uf in files:
        content = await uf.read()
        channel, data = parse_file(content, filename=uf.filename)
        if "BANK" in channel.value:
            bank_rows.extend(data)
        elif "LOGISTICS" in channel.value:
            cod_settlements.extend(data)
        else:
            source_txns.extend(data)

    if not bank_rows and not source_txns and not cod_settlements:
        return {
            "status": "error",
            "message": "Format file tidak dikenali atau tidak ada data yang valid."
        }

    open_batches = get_open_in_transit_batches(workspace_id=workspace_id)
    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(
        bank_rows=bank_rows,
        source_transactions=source_txns,
        prior_unresolved_batches=open_batches,
        cod_settlements=cod_settlements
    )

    # Simpan sesi rekonsiliasi ke SQLite
    run_id = save_reconciliation_run(result, {
        "source": f"Upload Mandiri ({len(files)} file)",
        "workspace_id": workspace_id
    })
    result["run_id"] = run_id
    result["workspace_id"] = workspace_id

    for r in result.get("rolling_resolved", []):
        mark_batch_resolved_rolling(
            batch_id=r["batch_id"],
            resolution_run_id=run_id,
            bank_row_id=r["bank_row_id"],
            bank_date=r["bank_date"]
        )

    LATEST_RESULT = result
    journals = generate_journal_entries_data(result)

    return {
        "status": "success",
        "run_id": run_id,
        "workspace_id": workspace_id,
        "data": result,
        "journals": journals,
        "rolling_summary": get_rolling_summary(workspace_id=workspace_id)
    }

@app.post("/api/reconcile/cod")
async def reconcile_cod_logistics(
    request: Request,
    courier_files: List[UploadFile] = File(...),
    bank_files: Optional[List[UploadFile]] = File(None),
    sales_files: Optional[List[UploadFile]] = File(None)
):
    """
    Endpoint khusus Rekonsiliasi 3-Arah COD Logistik Ekspedisi (JNE, SiCepat, dll).
    Mencocokkan pesanan penjualan <-> resi kurir COD <-> pencairan kredit mutasi bank.
    """
    global LATEST_RESULT
    workspace_id = request.query_params.get("workspace_id", "ws-default")
    
    cod_settlements = []
    bank_rows = []
    source_txns = []
    
    for uf in courier_files:
        content = await uf.read()
        ch, data = parse_file(content, filename=uf.filename)
        if "LOGISTICS" in ch.value:
            cod_settlements.extend(data)
        else:
            cod_settlements.extend(data)
            
    if bank_files:
        for uf in bank_files:
            content = await uf.read()
            ch, data = parse_file(content, filename=uf.filename)
            if "BANK" in ch.value:
                bank_rows.extend(data)
                
    if sales_files:
        for uf in sales_files:
            content = await uf.read()
            ch, data = parse_file(content, filename=uf.filename)
            if "BANK" not in ch.value and "LOGISTICS" not in ch.value:
                source_txns.extend(data)
                
    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(
        bank_rows=bank_rows,
        source_transactions=source_txns,
        cod_settlements=cod_settlements
    )
    
    run_id = save_reconciliation_run(result, {
        "source": f"Audit COD Ekspedisi ({len(courier_files)} file kurir)",
        "workspace_id": workspace_id
    })
    result["run_id"] = run_id
    result["workspace_id"] = workspace_id
    LATEST_RESULT = result
    
    return {
        "status": "success",
        "run_id": run_id,
        "workspace_id": workspace_id,
        "data": result,
        "cod_summary": result.get("cod_summary")
    }

@app.post("/api/reconcile/multi-bank")
async def reconcile_multi_bank_consolidation(
    request: Request,
    bank_files: List[UploadFile] = File(...),
    source_files: Optional[List[UploadFile]] = File(None)
):
    """
    Endpoint Konsolidasi Multi-Bank: Memproses mutasi dari berbagai bank (BCA, Mandiri, BNI, BRI, SWIFT MT940)
    secara bersamaan dan merekonsiliasikannya ke seluruh kanal penjualan.
    """
    global LATEST_RESULT
    workspace_id = request.query_params.get("workspace_id", "ws-default")
    
    bank_rows = []
    source_txns = []
    cod_settlements = []
    
    for uf in bank_files:
        content = await uf.read()
        ch, data = parse_file(content, filename=uf.filename)
        if "BANK" in ch.value:
            bank_rows.extend(data)
            
    if source_files:
        for uf in source_files:
            content = await uf.read()
            ch, data = parse_file(content, filename=uf.filename)
            if "BANK" in ch.value:
                bank_rows.extend(data)
            elif "LOGISTICS" in ch.value:
                cod_settlements.extend(data)
            else:
                source_txns.extend(data)
                
    open_batches = get_open_in_transit_batches(workspace_id=workspace_id)
    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(
        bank_rows=bank_rows,
        source_transactions=source_txns,
        prior_unresolved_batches=open_batches,
        cod_settlements=cod_settlements
    )
    
    run_id = save_reconciliation_run(result, {
        "source": f"Konsolidasi Multi-Bank ({len(bank_files)} rekening koran)",
        "workspace_id": workspace_id
    })
    result["run_id"] = run_id
    result["workspace_id"] = workspace_id
    LATEST_RESULT = result
    journals = generate_journal_entries_data(result)
    
    return {
        "status": "success",
        "run_id": run_id,
        "workspace_id": workspace_id,
        "data": result,
        "journals": journals,
        "rolling_summary": get_rolling_summary(workspace_id=workspace_id)
    }

@app.get("/api/history")
async def get_history(workspace_id: Optional[str] = None):
    """Mengambil daftar riwayat sesi rekonsiliasi dari database SQLite."""
    runs = get_reconciliation_runs(limit=50, workspace_id=workspace_id)
    summary = get_rolling_summary(workspace_id=workspace_id)
    return {
        "status": "success",
        "runs": runs,
        "rolling_summary": summary
    }

@app.get("/api/history/{run_id}")
async def load_history_run(run_id: str):
    """Memuat data sesi rekonsiliasi lampau dari database SQLite ke tampilan aktif."""
    global LATEST_RESULT
    run_data = get_run_by_id(run_id)
    if not run_data:
        return {"status": "error", "message": f"Sesi rekonsiliasi {run_id} tidak ditemukan di database."}

    LATEST_RESULT = run_data
    journals = generate_journal_entries_data(run_data)
    ws_id = run_data.get("workspace_id", "ws-default")
    return {
        "status": "success",
        "run_id": run_id,
        "workspace_id": ws_id,
        "data": run_data,
        "journals": journals,
        "rolling_summary": get_rolling_summary(workspace_id=ws_id)
    }

@app.get("/api/rolling/outstanding")
async def get_outstanding_rolling(workspace_id: Optional[str] = None):
    """Mengambil daftar seluruh batch in-transit yang masih terbuka lintas periode."""
    batches = get_open_in_transit_batches(workspace_id=workspace_id)
    return {
        "status": "success",
        "count": len(batches),
        "batches": batches,
        "rolling_summary": get_rolling_summary(workspace_id=workspace_id)
    }

@app.get("/api/workspaces")
async def list_workspaces():
    """Mengambil daftar seluruh entitas toko/cabang beserta konfigurasi pemetaan akun (COA)."""
    workspaces = get_workspaces()
    return {
        "status": "success",
        "workspaces": workspaces
    }

@app.post("/api/workspaces")
async def create_or_update_workspace(request: Request):
    """Menyimpan atau memperbarui profil toko dan akun bagan (COA)."""
    payload = await request.json()
    ws_id = save_workspace(payload)
    ws_data = get_workspace_by_id(ws_id)
    return {
        "status": "success",
        "workspace_id": ws_id,
        "workspace": ws_data
    }

@app.post("/api/accounting/sync")
async def sync_to_accounting(request: Request):
    """
    Mengirimkan ayat jurnal penyesuaian langsung ke software akuntansi
    (Mekari Jurnal, Accurate Online, atau Xero) melalui transmisi API terstandarisasi.
    """
    global LATEST_RESULT
    payload = await request.json()
    workspace_id = payload.get("workspace_id", "ws-default")
    run_id = payload.get("run_id") or (LATEST_RESULT.get("run_id") if LATEST_RESULT else "RUN-ACTIVE")
    provider = payload.get("provider", AccountingProvider.MEKARI_JURNAL)
    
    entries = payload.get("journal_entries")
    if not entries and LATEST_RESULT:
        entries = generate_journal_entries_data(LATEST_RESULT)
        
    if not entries:
        return {
            "status": "error",
            "message": "Tidak ada baris jurnal penyesuaian yang tersedia untuk disinkronkan."
        }
        
    ws_profile = get_workspace_by_id(workspace_id)
    coa_mapping = ws_profile.get("coa_mapping") if ws_profile else None
    
    result = dispatch_accounting_sync(
        workspace_id=workspace_id,
        run_id=run_id,
        journal_entries=entries,
        provider=provider,
        coa_mapping=coa_mapping
    )
    return result

@app.get("/api/accounting/logs")
async def list_accounting_logs(workspace_id: Optional[str] = None):
    """Mengambil riwayat log audit sinkronisasi API akuntansi."""
    logs = get_accounting_sync_logs(workspace_id=workspace_id, limit=50)
    return {
        "status": "success",
        "count": len(logs),
        "logs": logs
    }

@app.get("/api/export/excel")
async def export_excel():
    """Mengunduh laporan Excel multi-tab hasil rekonsiliasi."""
    global LATEST_RESULT
    if not LATEST_RESULT:
        # Jalankan default demo jika belum ada data di memory
        await run_demo()
        
    excel_io = generate_reconciliation_excel(LATEST_RESULT)
    return StreamingResponse(
        excel_io,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Laporan_Rekonsiliasi_Dua_Arah.xlsx"}
    )

@app.get("/api/export/journal")
async def export_journal():
    """Mengunduh CSV jurnal penyesuaian siap impor software akuntansi."""
    global LATEST_RESULT
    if not LATEST_RESULT:
        await run_demo()
        
    csv_str = generate_journal_csv(LATEST_RESULT)
    return StreamingResponse(
        io.BytesIO(csv_str.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Jurnal_Penyesuaian_Rekonsiliasi.csv"}
    )

@app.get("/api/docs/pdf")
async def download_system_documentation():
    """Mengunduh dokumen resmi dokumentasi teknis & panduan operasional ReconAuto.ID dalam format PDF."""
    pdf_path = os.path.join(os.path.dirname(__file__), "Dokumentasi_Lengkap_ReconAuto_ID.pdf")
    if not os.path.exists(pdf_path):
        from generate_docs_pdf import build_pdf
        build_pdf(pdf_path)
    return FileResponse(
        path=pdf_path,
        filename="Dokumentasi_Lengkap_ReconAuto_ID.pdf",
        media_type="application/pdf"
    )

@app.post("/api/dispute/preview")
async def preview_dispute(request: Request):
    """Menghasilkan draf teks surat klaim & email dispute resmi berdasarkan anomali."""
    global LATEST_RESULT
    payload = await request.json()
    discrepancy = payload.get("discrepancy", {})
    if not LATEST_RESULT:
        await run_demo()
    disp_data = generate_dispute_data(discrepancy, LATEST_RESULT)
    email_text = generate_dispute_email_text(disp_data)
    return {
        "status": "success",
        "dispute_data": disp_data,
        "email_text": email_text
    }

@app.post("/api/dispute/pdf")
async def download_dispute_pdf(request: Request):
    """Menghasilkan dan mengunduh surat klaim PDF resmi dengan kop dan tanda tangan."""
    global LATEST_RESULT
    payload = await request.json()
    discrepancy = payload.get("discrepancy", {})
    if not LATEST_RESULT:
        await run_demo()
    disp_data = generate_dispute_data(discrepancy, LATEST_RESULT)
    pdf_buf = generate_dispute_pdf(disp_data)
    safe_ref = str(disp_data.get("ref_id", "CLAIM")).replace("/", "_").replace(" ", "_")
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Surat_Klaim_Dispute_{safe_ref}.pdf"}
    )

@app.get("/api/samples/all/zip")
async def download_samples_zip():
    """Mengunduh seluruh file sampel CSV dan PDF rekening koran dalam 1 file ZIP."""
    csv_files = glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.csv"))
    pdf_files = glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.pdf"))
    sample_files = csv_files + pdf_files
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(sample_files):
            zf.write(f, arcname=os.path.basename(f))
            
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=Sample_Rekonsiliasi_Data.zip"}
    )

@app.get("/api/samples/{filename}")
async def download_sample_file(filename: str):
    """Mengunduh salah satu file sampel."""
    target_path = os.path.join(os.path.dirname(__file__), "sample_data", filename)
    if os.path.exists(target_path):
        return FileResponse(target_path, filename=filename)
    return Response(status_code=404, content="File not found")

# ==========================================================
# ENDPOINTS CHATBOT AI & CUSTOMER SERVICE
# ==========================================================

@app.get("/api/chat/cs-info")
async def get_cs_contact_info():
    """Mengembalikan informasi kontak Customer Service resmi ReconAuto.ID."""
    return {
        "status": "success",
        "cs_info": CS_INFO
    }

@app.post("/api/chat")
async def chat_with_ai(request: Request):
    """
    Endpoint pemrosesan percakapan AI bertenaga Google Gemini.
    Menerima pertanyaan seputar website, rekonsiliasi, maupun umum,
    serta mendeteksi eskalasi ke Customer Service.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
        
    message = payload.get("message", "")
    history = payload.get("history", [])
    
    result = await generate_chat_response(
        message=message,
        history=history,
        active_context={"latest_result_available": LATEST_RESULT is not None}
    )
    return result

if __name__ == "__main__":
    import uvicorn
    print("[INFO] Menjalankan ReconAuto Web Server di http://localhost:8000 ...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

