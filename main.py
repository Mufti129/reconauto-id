"""
main.py
-------
Server Web FastAPI Enterprise-Grade untuk Platform Rekonsiliasi Otomatis Multi-Sumber (Uji Dua Arah & Tiga Arah).
Dilengkapi dengan:
- Non-blocking Threadpool Execution untuk beban kerja CPU/I/O berat (Pandas, Engine, SQLite)
- Resolusi Sesi Stateless berbasis run_id & workspace_id (Mencegah Cross-Tenant Data Bleed)
- Validasi Upload Streaming (Anti-OOM / DoS) & Proteksi Path Traversal
- Validasi Skema Pydantic & Security Headers Middleware
"""

import os
import io
import glob
import zipfile
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from fastapi import FastAPI, UploadFile, File, Response, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

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
    get_latest_run,
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

logger = logging.getLogger("reconauto.api")

# Batas keamanan unggahan berkas
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_FILE_SIZE_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_FILES_PER_REQUEST = 30
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".sta", ".mt940", ".txt"}

# In-memory cache terisolasi per workspace & run_id (dengan fallback otomatis ke SQLite)
LATEST_RESULT: Optional[Dict[str, Any]] = None
_WORKSPACE_LATEST_CACHE: Dict[str, Dict[str, Any]] = {}
_RUN_CACHE_BY_ID: Dict[str, Dict[str, Any]] = {}


def _cache_run_result(result: Dict[str, Any], workspace_id: str = "ws-default") -> None:
    """Menyimpan hasil rekonsiliasi ke cache terisolasi per workspace & run_id."""
    global LATEST_RESULT
    LATEST_RESULT = result
    ws_key = workspace_id or result.get("workspace_id") or "ws-default"
    _WORKSPACE_LATEST_CACHE[ws_key] = result
    run_id = result.get("run_id")
    if run_id:
        # Batasi ukuran dictionary cache di memori (maks 25 sesi terakhir)
        if len(_RUN_CACHE_BY_ID) >= 25:
            oldest_key = next(iter(_RUN_CACHE_BY_ID))
            _RUN_CACHE_BY_ID.pop(oldest_key, None)
        _RUN_CACHE_BY_ID[run_id] = result


async def _resolve_target_run(
    run_id: Optional[str] = None,
    workspace_id: str = "ws-default"
) -> Dict[str, Any]:
    """
    Mencari data sesi rekonsiliasi secara aman (Stateless-first):
    1. Berdasarkan run_id spesifik (dari cache atau database SQLite)
    2. Berdasarkan sesi terakhir milik workspace_id terkait (dari cache atau SQLite)
    3. Fallback ke LATEST_RESULT atau eksekusi demo awal jika database masih kosong
    """
    clean_run_id = (run_id or "").strip()
    if clean_run_id and clean_run_id not in ("null", "undefined", "RUN-ACTIVE"):
        if clean_run_id in _RUN_CACHE_BY_ID:
            return _RUN_CACHE_BY_ID[clean_run_id]
        db_run = await run_in_threadpool(get_run_by_id, clean_run_id)
        if db_run:
            _cache_run_result(db_run, db_run.get("workspace_id", workspace_id))
            return db_run

    if workspace_id in _WORKSPACE_LATEST_CACHE:
        return _WORKSPACE_LATEST_CACHE[workspace_id]

    db_latest = await run_in_threadpool(get_latest_run, workspace_id)
    if db_latest:
        _cache_run_result(db_latest, workspace_id)
        return db_latest

    if LATEST_RESULT:
        return LATEST_RESULT

    await run_demo(workspace_id=workspace_id)
    return _WORKSPACE_LATEST_CACHE.get(workspace_id) or LATEST_RESULT or {}


async def _read_and_validate_upload(uf: UploadFile) -> bytes:
    """Membaca berkas upload secara bertahap (chunked) untuk mencegah serangan OOM / DoS."""
    filename = uf.filename or "unnamed.csv"
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format berkas '{filename}' ({ext}) tidak didukung. Gunakan CSV, Excel, PDF, atau MT940."
        )

    chunks: List[bytes] = []
    total_bytes = 0
    while chunk := await uf.read(64 * 1024):
        total_bytes += len(chunk)
        if total_bytes > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Ukuran berkas '{filename}' melebihi batas maksimum {MAX_UPLOAD_MB} MB."
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ==========================================
# PYDANTIC REQUEST SCHEMAS
# ==========================================

class WorkspaceUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    name: str = Field(default="Toko Baru", min_length=1, max_length=200)
    tax_id: Optional[str] = "-"
    default_bank_name: Optional[str] = "Bank BCA"
    default_account_num: Optional[str] = "-"
    coa_mapping: Dict[str, str] = Field(default_factory=dict)


class AccountingSyncRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    workspace_id: str = "ws-default"
    run_id: Optional[str] = None
    provider: str = AccountingProvider.MEKARI_JURNAL
    journal_entries: Optional[List[Dict[str, Any]]] = None


class DisputeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    discrepancy: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = None
    workspace_id: str = "ws-default"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    message: str = ""
    history: List[Dict[str, Any]] = Field(default_factory=list)
    run_id: Optional[str] = None
    workspace_id: str = "ws-default"


# ==========================================
# LIFESPAN & APPLICATION INITIALIZATION
# ==========================================

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Inisialisasi skema database satu kali saat server mulai berjalan."""
    await run_in_threadpool(init_db)
    yield


# Pastikan tabel siap bahkan jika modul diimpor tanpa lifespan (mis. TestClient sederhana)
init_db()

app = FastAPI(
    title="ReconAuto.ID - Platform Rekonsiliasi Otomatis Multi-Sumber",
    version="1.1.0",
    lifespan=lifespan
)

# Konfigurasi CORS yang aman sesuai spesifikasi W3C
_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=(_allowed_origins != ["*"]),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Menambahkan header keamanan standar OWASP pada setiap respons HTTP."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# Registrasi Router NDA Digital
from nda.consent_router import router as nda_router
app.include_router(nda_router)

# Mount folder static
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==========================================
# HELPER EKSEKUSI SINKRON (UNTUK THREADPOOL)
# ==========================================

def _execute_reconciliation_pipeline(
    raw_files: List[ tuple ],
    workspace_id: str,
    source_label: str
) -> Dict[str, Any]:
    """Menjalankan parsing, rekonsiliasi 4-tier, dan penyimpanan SQLite di thread terpisah."""
    bank_rows = []
    source_txns = []
    cod_settlements = []

    for filename, content in raw_files:
        channel, data = parse_file(content, filename=filename)
        if "BANK" in channel.value:
            bank_rows.extend(data)
        elif "LOGISTICS" in channel.value:
            cod_settlements.extend(data)
        else:
            source_txns.extend(data)

    if not bank_rows and not source_txns and not cod_settlements:
        return {"error": "Format file tidak dikenali atau tidak ada data yang valid."}

    open_batches = get_open_in_transit_batches(workspace_id=workspace_id)
    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(
        bank_rows=bank_rows,
        source_transactions=source_txns,
        prior_unresolved_batches=open_batches,
        cod_settlements=cod_settlements
    )

    run_id = save_reconciliation_run(result, {
        "source": source_label,
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

    journals = generate_journal_entries_data(result)
    rolling_summary = get_rolling_summary(workspace_id=workspace_id)

    return {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "result": result,
        "journals": journals,
        "rolling_summary": rolling_summary
    }


# ==========================================
# 1. ENDPOINTS REKONSILIASI DUA ARAH & MULTI-SUMBER
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    def _read_html() -> str:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return await run_in_threadpool(_read_html)


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
    def _load_sample_files() -> List[tuple]:
        sample_files = glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.csv"))
        loaded = []
        for f_path in sorted(sample_files):
            with open(f_path, "rb") as fp:
                loaded.append((os.path.basename(f_path), fp.read()))
        return loaded

    raw_files = await run_in_threadpool(_load_sample_files)
    if not raw_files:
        return {"status": "error", "message": "File sample_data/*.csv tidak ditemukan. Jalankan data_generator.py terlebih dahulu."}

    pipeline_out = await run_in_threadpool(
        _execute_reconciliation_pipeline,
        raw_files,
        workspace_id,
        "Simulasi 1-Klik Multi-Sumber & Multi-Bank (8 File)"
    )
    if "error" in pipeline_out:
        return {"status": "error", "message": pipeline_out["error"]}

    _cache_run_result(pipeline_out["result"], workspace_id)

    return {
        "status": "success",
        "run_id": pipeline_out["run_id"],
        "workspace_id": workspace_id,
        "data": pipeline_out["result"],
        "journals": pipeline_out["journals"],
        "rolling_summary": pipeline_out["rolling_summary"]
    }


@app.get("/api/sample-data/download")
async def download_sample_data_zip():
    """Mengemas seluruh berkas sampel dataset simulasi demo ke dalam file ZIP untuk diunduh nasabah."""
    def _build_zip() -> bytes:
        zip_buffer = io.BytesIO()
        sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
        readme_content = """========================================================================
PANDUAN FILE SAMPEL DATASET SIMULASI REKONSILIASI — ReconAuto.ID v1.1.0
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
        return zip_buffer.getvalue()

    zip_bytes = await run_in_threadpool(_build_zip)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="Sampel_Data_Demo_ReconAutoID.zip"',
            "Cache-Control": "no-cache"
        }
    )


@app.post("/api/reconcile")
async def reconcile_files(request: Request, files: List[UploadFile] = File(...)):
    """Menerima berkas upload pengguna dari berbagai kanal dan melakukan rekonsiliasi dua arah."""
    if not files:
        return {"status": "error", "message": "Tidak ada file yang diunggah."}
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_FILES_PER_REQUEST} file per unggahan.")

    workspace_id = request.query_params.get("workspace_id", "ws-default")
    raw_files = [(uf.filename or "upload.csv", await _read_and_validate_upload(uf)) for uf in files]

    pipeline_out = await run_in_threadpool(
        _execute_reconciliation_pipeline,
        raw_files,
        workspace_id,
        f"Upload Mandiri ({len(files)} file)"
    )
    if "error" in pipeline_out:
        return {"status": "error", "message": pipeline_out["error"]}

    _cache_run_result(pipeline_out["result"], workspace_id)

    return {
        "status": "success",
        "run_id": pipeline_out["run_id"],
        "workspace_id": workspace_id,
        "data": pipeline_out["result"],
        "journals": pipeline_out["journals"],
        "rolling_summary": pipeline_out["rolling_summary"]
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
    workspace_id = request.query_params.get("workspace_id", "ws-default")

    raw_courier = [(uf.filename or "cod.csv", await _read_and_validate_upload(uf)) for uf in courier_files]
    raw_bank = [(uf.filename or "bank.csv", await _read_and_validate_upload(uf)) for uf in (bank_files or [])]
    raw_sales = [(uf.filename or "sales.csv", await _read_and_validate_upload(uf)) for uf in (sales_files or [])]

    def _run_cod_sync():
        cod_settlements, bank_rows, source_txns = [], [], []
        for fname, content in raw_courier:
            _, data = parse_file(content, filename=fname)
            cod_settlements.extend(data)
        for fname, content in raw_bank:
            ch, data = parse_file(content, filename=fname)
            if "BANK" in ch.value:
                bank_rows.extend(data)
        for fname, content in raw_sales:
            ch, data = parse_file(content, filename=fname)
            if "BANK" not in ch.value and "LOGISTICS" not in ch.value:
                source_txns.extend(data)

        engine = BidirectionalReconciliationEngine()
        result = engine.reconcile(
            bank_rows=bank_rows,
            source_transactions=source_txns,
            cod_settlements=cod_settlements
        )
        run_id = save_reconciliation_run(result, {
            "source": f"Audit COD Ekspedisi ({len(raw_courier)} file kurir)",
            "workspace_id": workspace_id
        })
        result["run_id"] = run_id
        result["workspace_id"] = workspace_id
        return run_id, result

    run_id, result = await run_in_threadpool(_run_cod_sync)
    _cache_run_result(result, workspace_id)

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
    workspace_id = request.query_params.get("workspace_id", "ws-default")
    all_uploads = list(bank_files) + list(source_files or [])
    if len(all_uploads) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_FILES_PER_REQUEST} file per unggahan.")

    raw_files = [(uf.filename or "file.csv", await _read_and_validate_upload(uf)) for uf in all_uploads]

    pipeline_out = await run_in_threadpool(
        _execute_reconciliation_pipeline,
        raw_files,
        workspace_id,
        f"Konsolidasi Multi-Bank ({len(bank_files)} rekening koran)"
    )
    if "error" in pipeline_out:
        return {"status": "error", "message": pipeline_out["error"]}

    _cache_run_result(pipeline_out["result"], workspace_id)

    return {
        "status": "success",
        "run_id": pipeline_out["run_id"],
        "workspace_id": workspace_id,
        "data": pipeline_out["result"],
        "journals": pipeline_out["journals"],
        "rolling_summary": pipeline_out["rolling_summary"]
    }


@app.get("/api/history")
async def get_history(workspace_id: Optional[str] = None):
    """Mengambil daftar riwayat sesi rekonsiliasi dari database SQLite."""
    def _fetch():
        return (
            get_reconciliation_runs(limit=50, workspace_id=workspace_id),
            get_rolling_summary(workspace_id=workspace_id)
        )
    runs, summary = await run_in_threadpool(_fetch)
    return {
        "status": "success",
        "runs": runs,
        "rolling_summary": summary
    }


@app.get("/api/history/{run_id}")
async def load_history_run(run_id: str):
    """Memuat data sesi rekonsiliasi lampau dari database SQLite ke tampilan aktif."""
    def _load():
        r_data = get_run_by_id(run_id)
        if not r_data:
            return None, None, None
        ws_id = r_data.get("workspace_id", "ws-default")
        jrn = generate_journal_entries_data(r_data)
        r_sum = get_rolling_summary(workspace_id=ws_id)
        return r_data, jrn, r_sum

    run_data, journals, rolling_summary = await run_in_threadpool(_load)
    if not run_data:
        return {"status": "error", "message": f"Sesi rekonsiliasi {run_id} tidak ditemukan di database."}

    ws_id = run_data.get("workspace_id", "ws-default")
    _cache_run_result(run_data, ws_id)

    return {
        "status": "success",
        "run_id": run_id,
        "workspace_id": ws_id,
        "data": run_data,
        "journals": journals,
        "rolling_summary": rolling_summary
    }


@app.get("/api/rolling/outstanding")
async def get_outstanding_rolling(workspace_id: Optional[str] = None):
    """Mengambil daftar seluruh batch in-transit yang masih terbuka lintas periode."""
    def _fetch():
        return (
            get_open_in_transit_batches(workspace_id=workspace_id),
            get_rolling_summary(workspace_id=workspace_id)
        )
    batches, rolling_summary = await run_in_threadpool(_fetch)
    return {
        "status": "success",
        "count": len(batches),
        "batches": batches,
        "rolling_summary": rolling_summary
    }


@app.get("/api/workspaces")
async def list_workspaces():
    """Mengambil daftar seluruh entitas toko/cabang beserta konfigurasi pemetaan akun (COA)."""
    workspaces = await run_in_threadpool(get_workspaces)
    return {
        "status": "success",
        "workspaces": workspaces
    }


@app.post("/api/workspaces")
async def create_or_update_workspace(req: WorkspaceUpsertRequest):
    """Menyimpan atau memperbarui profil toko dan akun bagan (COA)."""
    payload = req.model_dump()
    def _save():
        ws_id = save_workspace(payload)
        return ws_id, get_workspace_by_id(ws_id)
    ws_id, ws_data = await run_in_threadpool(_save)
    return {
        "status": "success",
        "workspace_id": ws_id,
        "workspace": ws_data
    }


@app.post("/api/accounting/sync")
async def sync_to_accounting(req: AccountingSyncRequest):
    """
    Mengirimkan ayat jurnal penyesuaian langsung ke software akuntansi
    (Mekari Jurnal, Accurate Online, atau Xero) melalui transmisi API terstandarisasi.
    """
    workspace_id = req.workspace_id or "ws-default"
    target_run = await _resolve_target_run(req.run_id, workspace_id)
    run_id = req.run_id or target_run.get("run_id") or "RUN-ACTIVE"
    provider = req.provider or AccountingProvider.MEKARI_JURNAL

    entries = req.journal_entries
    if not entries and target_run:
        entries = await run_in_threadpool(generate_journal_entries_data, target_run)

    if not entries:
        return {
            "status": "error",
            "message": "Tidak ada baris jurnal penyesuaian yang tersedia untuk disinkronkan."
        }

    def _dispatch():
        ws_profile = get_workspace_by_id(workspace_id)
        coa_mapping = ws_profile.get("coa_mapping") if ws_profile else None
        return dispatch_accounting_sync(
            workspace_id=workspace_id,
            run_id=run_id,
            journal_entries=entries,
            provider=provider,
            coa_mapping=coa_mapping
        )

    return await run_in_threadpool(_dispatch)


@app.get("/api/accounting/logs")
async def list_accounting_logs(workspace_id: Optional[str] = None):
    """Mengambil riwayat log audit sinkronisasi API akuntansi."""
    logs = await run_in_threadpool(get_accounting_sync_logs, workspace_id, 50)
    return {
        "status": "success",
        "count": len(logs),
        "logs": logs
    }


@app.get("/api/export/excel")
async def export_excel(
    run_id: Optional[str] = Query(None),
    workspace_id: str = Query("ws-default")
):
    """Mengunduh laporan Excel multi-tab hasil rekonsiliasi."""
    target_run = await _resolve_target_run(run_id, workspace_id)
    excel_io = await run_in_threadpool(generate_reconciliation_excel, target_run)
    return StreamingResponse(
        excel_io,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Laporan_Rekonsiliasi_Dua_Arah.xlsx"}
    )


@app.get("/api/export/journal")
async def export_journal(
    run_id: Optional[str] = Query(None),
    workspace_id: str = Query("ws-default")
):
    """Mengunduh CSV jurnal penyesuaian siap impor software akuntansi."""
    target_run = await _resolve_target_run(run_id, workspace_id)
    csv_str = await run_in_threadpool(generate_journal_csv, target_run)
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
        await run_in_threadpool(build_pdf, pdf_path)
    return FileResponse(
        path=pdf_path,
        filename="Dokumentasi_Lengkap_ReconAuto_ID.pdf",
        media_type="application/pdf"
    )


@app.post("/api/dispute/preview")
async def preview_dispute(req: DisputeRequest):
    """Menghasilkan draf teks surat klaim & email dispute resmi berdasarkan anomali."""
    target_run = await _resolve_target_run(req.run_id, req.workspace_id)
    def _build():
        d_data = generate_dispute_data(req.discrepancy, target_run)
        e_text = generate_dispute_email_text(d_data)
        return d_data, e_text
    disp_data, email_text = await run_in_threadpool(_build)
    return {
        "status": "success",
        "dispute_data": disp_data,
        "email_text": email_text
    }


@app.post("/api/dispute/pdf")
async def download_dispute_pdf(req: DisputeRequest):
    """Menghasilkan dan mengunduh surat klaim PDF resmi dengan kop dan tanda tangan."""
    target_run = await _resolve_target_run(req.run_id, req.workspace_id)
    def _build_pdf():
        d_data = generate_dispute_data(req.discrepancy, target_run)
        p_buf = generate_dispute_pdf(d_data)
        return d_data, p_buf
    disp_data, pdf_buf = await run_in_threadpool(_build_pdf)
    safe_ref = str(disp_data.get("ref_id", "CLAIM")).replace("/", "_").replace(" ", "_")
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Surat_Klaim_Dispute_{safe_ref}.pdf"}
    )


@app.get("/api/samples/all/zip")
async def download_samples_zip():
    """Mengunduh seluruh file sampel CSV dan PDF rekening koran dalam 1 file ZIP."""
    def _pack_zip():
        csv_files = glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.csv"))
        pdf_files = glob.glob(os.path.join(os.path.dirname(__file__), "sample_data", "*.pdf"))
        sample_files = csv_files + pdf_files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(sample_files):
                zf.write(f, arcname=os.path.basename(f))
        zip_buffer.seek(0)
        return zip_buffer

    zip_buffer = await run_in_threadpool(_pack_zip)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=Sample_Rekonsiliasi_Data.zip"}
    )


@app.get("/api/samples/{filename}")
async def download_sample_file(filename: str):
    """Mengunduh salah satu file sampel dengan proteksi ketat terhadap Path Traversal."""
    base_dir = Path(os.path.dirname(__file__), "sample_data").resolve()
    safe_name = os.path.basename(filename)
    target_path = (base_dir / safe_name).resolve()

    if not target_path.is_relative_to(base_dir) or not target_path.is_file():
        return Response(status_code=404, content="File not found")

    return FileResponse(str(target_path), filename=safe_name)


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
        raw_payload = await request.json()
        req = ChatRequest(**raw_payload) if isinstance(raw_payload, dict) else ChatRequest()
    except Exception:
        req = ChatRequest()

    has_active_result = bool(_WORKSPACE_LATEST_CACHE or LATEST_RESULT)
    result = await generate_chat_response(
        message=req.message,
        history=req.history,
        active_context={"latest_result_available": has_active_result}
    )
    return result


if __name__ == "__main__":
    import uvicorn
    print("[INFO] Menjalankan ReconAuto Web Server di http://localhost:8000 ...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
