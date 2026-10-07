"""
FastAPI router untuk modul NDA Digital ReconAuto.ID.

Endpoint:
  GET  /api/nda/document          — Ambil teks NDA terkini + hash versi
  POST /api/nda/consent           — Kirim persetujuan NDA
  GET  /api/nda/status?email=...  — Cek apakah email sudah pernah consent
  GET  /api/nda/verify/{id}       — Verifikasi keaslian record consent

Cara mendaftarkan router ini ke aplikasi utama (main.py):
    from nda.consent_router import router as nda_router
    app.include_router(nda_router)
"""

import uuid
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from .models import (
    NDAConsentRequest,
    NDAConsentRecord,
    NDADocumentResponse,
    NDAStatusResponse,
    NDAVerifyResponse,
)
from .nda_document import NDA_DOCUMENT_TEXT, NDA_DOCUMENT_HASH, NDA_DOCUMENT_VERSION
from . import storage

logger = logging.getLogger("reconauto.nda")
router = APIRouter(prefix="/api/nda", tags=["nda"])


@router.get("/document", response_model=NDADocumentResponse)
def get_nda_document() -> NDADocumentResponse:
    """Mengembalikan teks NDA terkini beserta hash dan versi.

    Frontend menampilkan teks ini di modal NDA dan mengirimkan kembali
    document_hash saat consent agar backend dapat memverifikasi bahwa
    pengguna benar-benar membaca versi dokumen yang sama.
    """
    return NDADocumentResponse(
        document_text=NDA_DOCUMENT_TEXT,
        document_version=NDA_DOCUMENT_VERSION,
        document_hash=NDA_DOCUMENT_HASH,
    )


@router.post("/consent", response_model=NDAVerifyResponse)
def submit_consent(req: NDAConsentRequest, request: Request) -> NDAVerifyResponse:
    """Menerima persetujuan NDA dari pengguna.

    Validasi:
    - checkbox_setuju harus True
    - document_hash harus cocok dengan versi NDA terkini
    - Email belum pernah consent (opsional: izinkan re-consent jika versi berubah)
    """
    # Validasi checkbox wajib dicentang
    if not req.checkbox_setuju:
        raise HTTPException(
            status_code=400,
            detail="Anda harus mencentang kotak persetujuan untuk melanjutkan.",
        )

    # Validasi hash dokumen — pastikan user membaca versi yang benar
    if req.document_hash != NDA_DOCUMENT_HASH:
        raise HTTPException(
            status_code=400,
            detail=(
                "Versi dokumen NDA tidak sesuai. Silakan muat ulang halaman "
                "untuk mendapatkan versi terbaru."
            ),
        )

    # Cek apakah email sudah pernah consent dengan versi yang sama
    existing = storage.find_by_email(req.email)
    if existing and existing.document_hash == NDA_DOCUMENT_HASH:
        return NDAVerifyResponse(
            valid=True,
            consent_record=existing,
            message="Anda sudah pernah menyetujui NDA versi ini sebelumnya.",
        )

    # Buat record consent baru
    now_utc = datetime.now(ZoneInfo("UTC"))
    now_wib = now_utc.astimezone(ZoneInfo("Asia/Jakarta"))

    consent_id = str(uuid.uuid4())

    record = NDAConsentRecord(
        consent_id=consent_id,
        nama_lengkap=req.nama_lengkap,
        email=req.email,
        nama_perusahaan=req.nama_perusahaan,
        jabatan=req.jabatan,
        document_version=NDA_DOCUMENT_VERSION,
        document_hash=NDA_DOCUMENT_HASH,
        signature_data=req.signature_data,
        timestamp_utc=now_utc.isoformat(),
        timestamp_wib=now_wib.isoformat(),
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
    )

    # Simpan ke storage
    storage.save_consent(record)

    logger.info(
        f"NDA consent diterima: {consent_id} | {req.nama_lengkap} "
        f"<{req.email}> | IP: {record.ip_address}"
    )

    return NDAVerifyResponse(
        valid=True,
        consent_record=record,
        message="Terima kasih. Persetujuan NDA Anda telah berhasil dicatat.",
    )


@router.get("/status", response_model=NDAStatusResponse)
def check_nda_status(email: str) -> NDAStatusResponse:
    """Cek apakah email tertentu sudah menandatangani NDA terkini.

    Digunakan oleh frontend untuk menentukan apakah modal NDA perlu
    ditampilkan saat pengguna mengakses halaman upload/rekonsiliasi.
    """
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Parameter email wajib diisi.")

    record = storage.find_by_email(email.strip())

    if record and record.document_hash == NDA_DOCUMENT_HASH:
        return NDAStatusResponse(
            has_consented=True,
            consent_id=record.consent_id,
            consented_at=record.timestamp_wib,
            document_version=record.document_version,
        )

    return NDAStatusResponse(has_consented=False)


@router.get("/verify/{consent_id}", response_model=NDAVerifyResponse)
def verify_consent(consent_id: str) -> NDAVerifyResponse:
    """Verifikasi keaslian record consent berdasarkan UUID consent_id.

    Endpoint ini dapat digunakan oleh:
    - Pengguna untuk memverifikasi bahwa consent mereka tercatat
    - Auditor untuk memvalidasi audit trail
    """
    record = storage.find_by_consent_id(consent_id)

    if not record:
        return NDAVerifyResponse(
            valid=False,
            message=f"Record consent dengan ID '{consent_id}' tidak ditemukan.",
        )

    return NDAVerifyResponse(
        valid=True,
        consent_record=record,
        message="Record consent valid dan terverifikasi.",
    )


@router.get("/download/{consent_id}")
def download_nda_pdf(consent_id: str):
    """Mengunduh dokumen resmi PDF NDA yang telah ditandatangani secara digital."""
    import re
    from fastapi import Response
    from .pdf_generator import generate_nda_pdf_bytes

    if consent_id == "latest":
        consents = storage.get_all_consents()
        if not consents:
            raise HTTPException(status_code=404, detail="Belum ada dokumen NDA yang ditandatangani.")
        record = consents[0]
    else:
        record = storage.find_by_consent_id(consent_id)
        if not record:
            raise HTTPException(status_code=404, detail="Dokumen NDA tidak ditemukan.")

    pdf_bytes = generate_nda_pdf_bytes(record)
    safe_company = re.sub(r'[^A-Za-z0-9]+', '_', record.nama_perusahaan or "Klien").strip('_')
    safe_date = record.timestamp_wib[:10]
    filename = f"NDA_ReconAutoID_{safe_company}_{safe_date}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        }
    )


@router.get("/download-latest")
def download_latest_nda(email: Optional[str] = None):
    """Shortcut mengunduh dokumen NDA terkini untuk dipegang bersama perusahaan & klien."""
    if email:
        record = storage.find_by_email(email)
    else:
        consents = storage.get_all_consents()
        record = consents[0] if consents else None

    if not record:
        raise HTTPException(status_code=404, detail="Belum ada dokumen NDA yang disepakati untuk diunduh.")

    return download_nda_pdf(record.consent_id)

